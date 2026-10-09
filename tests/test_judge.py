"""票04 — judge：TRACE 状态机、n=5 多数票、score.json 聚合换算。"""
import asyncio
import json
from pathlib import Path

import pytest

from rpeval.config import load_scene
from rpeval.judge import (
    JudgeClient,
    majority_vote,
    run_state_machine,
    score_case,
    write_score_json,
)

SCENE_YAML = """\
id: 学姐卡毒舌v1
card:
  name: 毒舌学姐
  description: 嘴硬心软
  scenario: 活动室
  first_mes: 哟
user_script:
  - {turn: 1, text: "（沉默）"}
  - {turn: 2, text: "帮我带份饭"}
  - {turn: 3, text: "谢啦"}
checklist:
  - {id: dai-1, text: 是否替用户说话, dimension: 代打, weight: 2}
  - {id: wen-1, text: 黑名单词命中, dimension: 文笔, weight: 1}
tier: null
"""


def _scene(tmp_path):
    d = tmp_path / "scenes"
    d.mkdir(exist_ok=True)
    f = d / "s.yaml"
    f.write_text(SCENE_YAML, encoding="utf-8")
    return load_scene(f)


def _case(turns):
    return {"scene": "学姐卡毒舌v1", "model": "deepseek-chat", "turns": turns}


def _turn(n, reply):
    return {"turn_no": n, "user": f"u{n}", "model_reply": reply, "judge": None,
            "meta": {"latency_ms": 1, "tokens": {}, "cost_cny": 0}}


class FakeJudge:
    """按 (item_id, 采样序号) 返回预设 verdict 序列。"""

    def __init__(self, responses: dict[str, list[str]]):
        self.responses = responses
        self.calls: list[tuple[str, str]] = []  # (item_id, 对话摘要)

    async def judge_one(self, dialogue: str, item) -> dict:
        seq = self.responses[item.id]
        idx = sum(1 for c in self.calls if c[0] == item.id)
        self.calls.append((item.id, dialogue))
        v = seq[min(idx, len(seq) - 1)]
        if v == "pass":
            return {"verdict": "pass", "evidence_turn": 2, "evidence_quote": "我帮你带"}
        if v == "fail":
            return {"verdict": "fail", "evidence_turn": 2, "evidence_quote": "我帮你带"}
        return {"verdict": "unknown", "evidence_turn": None, "evidence_quote": ""}


def test_state_machine_failed_irreversible(tmp_path):
    scene = _scene(tmp_path)
    judge = FakeJudge({"dai-1": ["pass", "pass", "pass", "pass", "pass"],
                       "wen-1": ["fail", "fail", "fail", "pass", "pass"]})
    case = _case([_turn(1, "r1"), _turn(2, "我帮你带"), _turn(3, "r3")])
    result = asyncio.run(run_state_machine(scene, case, judge, n=5))
    dai = next(r for r in result if r["id"] == "dai-1")
    wen = next(r for r in result if r["id"] == "wen-1")
    assert dai["state"] == "verified"
    assert wen["state"] == "failed"
    assert wen["evidence_quote"] == "我帮你带"
    # failed 不可逆：把同一结果再喂一轮"pass"也不翻案
    again = asyncio.run(run_state_machine(scene, case, FakeJudge({"dai-1": ["pass"]*5, "wen-1": ["pass"]*5}),
                                          n=5, prior=result))
    assert next(r for r in again if r["id"] == "wen-1")["state"] == "failed"


def test_majority_vote_ties_and_ignores_unknown():
    assert majority_vote(["pass", "pass", "fail", "unknown", "pass"]) == "pass"
    assert majority_vote(["pass", "fail", "unknown", "unknown", "unknown"]) is None  # 平票
    assert majority_vote(["unknown"] * 5) is None


def test_n_samples_majority_applied(tmp_path):
    scene = _scene(tmp_path)
    # dai-1 三次 fail 两次 pass → 多数 fail
    judge = FakeJudge({"dai-1": ["fail", "fail", "pass", "fail", "pass"],
                       "wen-1": ["pass"] * 5})
    case = _case([_turn(1, "r1"), _turn(2, "我帮你带")])
    result = asyncio.run(run_state_machine(scene, case, judge, n=5))
    assert next(r for r in result if r["id"] == "dai-1")["state"] == "failed"
    assert len(judge.calls) == 10  # 2 条 × 5 采样


def test_dimension_score_weight_conversion(tmp_path):
    scene = _scene(tmp_path)
    # dai-1(w=2) verified, wen-1(w=1) failed → 代打 10/10, 文笔 0/10
    judge = FakeJudge({"dai-1": ["pass"] * 5, "wen-1": ["fail"] * 5})
    case = _case([_turn(1, "r1"), _turn(2, "x")])
    result = asyncio.run(run_state_machine(scene, case, judge, n=5))
    dims = score_case(scene, result)
    assert dims["代打"]["score"] == 10.0
    assert dims["文笔"]["score"] == 0.0
    # 混合权重：dai verified, wen verified → 都 10
    # 另一例：两条 checklist 权重 2+1 同维度时 verified 权重和/总权重和*10
    assert dims["代打"]["details"]["verified"] == ["dai-1"]
    assert dims["文笔"]["details"]["failed"] == ["wen-1"]


def test_score_json_written(tmp_path):
    scene = _scene(tmp_path)
    judge = FakeJudge({"dai-1": ["pass"] * 5, "wen-1": ["fail"] * 5})
    case = _case([_turn(1, "r1"), _turn(2, "x")])
    result = asyncio.run(run_state_machine(scene, case, judge, n=5))
    out = tmp_path / "score.json"
    write_score_json(out, [case], {("学姐卡毒舌v1", "deepseek-chat"): result}, [scene])
    data = json.loads(out.read_text(encoding="utf-8"))
    entry = data["cases"][0]
    assert entry["model"] == "deepseek-chat"
    assert entry["dimensions"]["代打"]["score"] == 10.0
    assert entry["total"] == 10.0  # 只有代打 verified
    assert entry["checklist"]["wen-1"]["state"] == "failed"


def test_judge_prompt_contains_dialogue_and_item(tmp_path):
    scene = _scene(tmp_path)
    captured: dict[str, str] = {}

    class SpyJudge(FakeJudge):
        async def judge_one(self, dialogue, item):
            captured.setdefault("dialogues", []).append(dialogue)
            captured.setdefault("items", []).append(item.text)
            return await super().judge_one(dialogue, item)

    judge = SpyJudge({"dai-1": ["pass"] * 5, "wen-1": ["pass"] * 5})
    case = _case([_turn(1, "你好呀学姐"), _turn(2, "我帮你带")])
    asyncio.run(run_state_machine(scene, case, judge, n=1))
    assert "你好呀学姐" in captured["dialogues"][0]
    assert "我帮你带" in captured["dialogues"][0]
    assert "是否替用户说话" in captured["items"]
    assert "黑名单词命中" in captured["items"]


# ---------- 程序化校验（check 字段，不走 LLM） ----------

from rpeval.judge import run_checks  # noqa: E402

CHECK_SCENE_YAML = """\
id: 格式-校验v1
card:
  name: 助手
  description: 按格式输出
  scenario: 整理
  first_mes: 好
user_script:
  - {turn: 1, text: "输出JSON"}
  - {turn: 2, text: "总结"}
  - {turn: 3, text: "排序"}
  - {turn: 4, text: "HTML"}
checklist:
  - {id: c1, text: JSON, dimension: 格式, weight: 2, check: "json@1"}
  - {id: c2, text: 字数, dimension: 格式, weight: 2, check: "len@2:15"}
  - {id: c3, text: 无数字, dimension: 格式, weight: 1, check: "regex@2:not:[0-9]"}
  - {id: c4, text: 模板抓取, dimension: 格式, weight: 2, check: "regex@3:count=3:\\\\[[^\\\\[\\\\]]+\\\\]"}
  - {id: c5, text: HTML配平, dimension: 格式, weight: 2, check: "html@4"}
tier: null
"""


def _check_scene(tmp_path):
    d = tmp_path / "scenes"
    d.mkdir(exist_ok=True)
    f = d / "c.yaml"
    f.write_text(CHECK_SCENE_YAML, encoding="utf-8")
    return load_scene(f)


def test_run_checks_json_len_regex_html(tmp_path):
    scene = _check_scene(tmp_path)
    case = _case([
        _turn(1, '[{"name":"张三","age":28,"city":"北京"}]'),
        _turn(2, "这句子刚好十五个汉字不超"),
        _turn(3, "[张三][李四][王五]"),
        _turn(4, "<html><head><style>a{}</style></head><body><div><h1>t</h1><p>x</p></div></body></html>"),
    ])
    r = run_checks(scene, case)
    assert r["c1"]["state"] == "verified"          # 合法 JSON
    assert r["c2"]["state"] == "failed"            # 汉字数 12≠15
    assert r["c3"]["state"] == "verified"          # 无数字
    assert r["c4"]["state"] == "verified"          # 抓到 3 组
    assert r["c5"]["state"] == "verified"          # 标签配平


def test_run_checks_detects_broken(tmp_path):
    scene = _check_scene(tmp_path)
    case = _case([
        _turn(1, "这不是JSON{{{"),
        _turn(2, "好的没问题123"),
        _turn(3, "[张三][李四]"),
        _turn(4, "<div><p>没闭合</div></p>"),
    ])
    r = run_checks(scene, case)
    assert r["c1"]["state"] == "failed"
    assert r["c3"]["state"] == "failed"            # 含数字
    assert r["c4"]["state"] == "failed"            # 只抓到2组
    assert r["c5"]["state"] == "failed"            # 交叉嵌套


def test_run_checks_missing_turn_pending(tmp_path):
    scene = _check_scene(tmp_path)
    case = _case([_turn(1, "[]")])
    r = run_checks(scene, case)
    assert r["c2"]["state"] == "pending"           # 第2轮不存在


def test_state_machine_check_skips_llm(tmp_path):
    """带 check 的条目走程序化校验：judge 一次都不被调用，votes=['check']。"""
    scene = _check_scene(tmp_path)
    judge = FakeJudge({i: ["pass"] * 5 for i in ("c1", "c2", "c3", "c4", "c5")})
    case = _case([
        _turn(1, "[]"), _turn(2, "这句子刚好十五个汉字不超"), _turn(3, "[a][b][c]"),
        _turn(4, "<div>x</div>"),
    ])
    result = asyncio.run(run_state_machine(scene, case, judge, n=5))
    assert judge.calls == []                        # 全部走校验，零 LLM
    assert all(r["votes"] == ["check"] for r in result)
    assert {r["id"]: r["state"] for r in result} == {
        "c1": "verified", "c2": "failed", "c3": "verified", "c4": "verified", "c5": "verified"}
