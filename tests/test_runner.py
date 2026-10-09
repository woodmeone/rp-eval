"""票03 — runner 单测：mock client 验证轮次拼接、落盘格式、断点续跑、并发。"""
import asyncio
import json
from pathlib import Path

from rpeval.config import ModelCfg, load_scene
from rpeval.runner import build_case_async, load_done_cases, run

SCENE_YAML = """\
id: 学姐卡毒舌v1
card:
  name: 毒舌学姐
  description: 嘴硬心软
  scenario: 活动室
  first_mes: 哟，你也还没走啊？
user_script:
  - {turn: 1, text: "（沉默）", probe_for: [dai-1]}
  - {turn: 2, text: "帮我带份饭呗"}
checklist:
  - {id: dai-1, text: 是否替你说, dimension: 代打, weight: 2}
tier: null
"""


def _scene(tmp_path: Path):
    d = tmp_path / "scenes"
    d.mkdir(exist_ok=True)
    f = d / "s.yaml"
    f.write_text(SCENE_YAML, encoding="utf-8")
    return load_scene(f)


def _model(**kw):
    base = dict(model_id="deepseek-chat", provider="deepseek", base_url="https://x", key_env="K",
                price_per_1k_in=0.002, price_per_1k_out=0.008)
    base.update(kw)
    return ModelCfg(**base)


class FakeClient:
    """记录每次收到的历史，回复带轮号。"""

    def __init__(self):
        self.histories: list[list[dict[str, str]]] = []

    async def chat(self, history):
        self.histories.append([dict(m) for m in history])
        n = len(self.histories)
        return f"回复{n}", {"prompt_tokens": 100, "completion_tokens": 50}


def test_multi_turn_history_chaining(tmp_path: Path):
    scene = _scene(tmp_path)
    client = FakeClient()
    case = asyncio.run(build_case_async(scene, _model(), client))
    # 第1轮历史：system + first_mes(assistant) + user1
    h1 = client.histories[0]
    assert h1[0]["role"] == "system" and "毒舌学姐" in h1[0]["content"]
    assert h1[1] == {"role": "assistant", "content": "哟，你也还没走啊？"}
    assert h1[-1] == {"role": "user", "content": "（沉默）"}
    # 第2轮历史包含第1轮回复（模型回复进历史）
    h2 = client.histories[1]
    assert {"role": "assistant", "content": "回复1"} in h2
    assert h2[-1] == {"role": "user", "content": "帮我带份饭呗"}
    assert [t["turn_no"] for t in case["turns"]] == [1, 2]
    assert case["turns"][1]["model_reply"] == "回复2"


def test_dialogue_case_format(tmp_path: Path):
    scene = _scene(tmp_path)
    case = asyncio.run(build_case_async(scene, _model(), FakeClient()))
    assert case["scene"] == "学姐卡毒舌v1"
    assert case["model"] == "deepseek-chat"
    t = case["turns"][0]
    assert t["user"] == "（沉默）"
    assert t["judge"] is None
    assert isinstance(t["meta"]["latency_ms"], int)
    assert t["meta"]["tokens"] == {"prompt": 100, "completion": 50}
    # cost = 0.1*0.002 + 0.05*0.008 = 0.0002+0.0004=0.0006
    assert t["meta"]["cost_cny"] == 0.0006


def test_run_appends_jsonl_and_skips_done(tmp_path: Path):
    scene = _scene(tmp_path)
    run_dir = tmp_path / "runs" / "r1"
    calls: list[str] = []

    def factory(m):
        calls.append(m.model_id)
        return FakeClient()

    models = [_model(model_id="a"), _model(model_id="b")]
    cases = asyncio.run(run(scene, models, factory, run_dir))
    assert len(cases) == 2
    lines = (run_dir / "dialogue.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # 每行一 case
    assert {json.loads(l)["model"] for l in lines} == {"a", "b"}

    # 断点续跑：再来一次，0 次新调用、文件不增长
    calls.clear()
    cases2 = asyncio.run(run(scene, models, factory, run_dir))
    assert cases2 == []
    assert calls == []
    assert len((run_dir / "dialogue.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_run_models_concurrent(tmp_path: Path):
    import time

    scene = _scene(tmp_path)

    class SlowClient:
        async def chat(self, history):
            await asyncio.sleep(0.2)
            return "ok", {}

    models = [_model(model_id=f"m{i}") for i in range(3)]
    t0 = time.monotonic()
    asyncio.run(run(scene, models, lambda m: SlowClient(), tmp_path / "runs" / "rc"))
    elapsed = time.monotonic() - t0
    # 串行需 3×2×0.2=1.2s；并发应远小于（2轮串行在单模型内）
    assert elapsed < 0.9


def test_corrupted_last_line_is_ignored_for_resume(tmp_path: Path):
    run_dir = tmp_path / "runs" / "r2"
    run_dir.mkdir(parents=True)
    good = json.dumps({"scene": "s", "model": "a", "turns": []}, ensure_ascii=False)
    (run_dir / "dialogue.jsonl").write_text(good + "\n{\"scene\": \"crash", encoding="utf-8")
    assert load_done_cases(run_dir) == {("s", "a")}
