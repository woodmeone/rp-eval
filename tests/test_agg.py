"""票06 — 聚合：六维0–10+总分60汇总表 / battles.jsonl / BT评分+CI+胜率矩阵 / 双向平均防位置偏差。"""
import asyncio
import json

import pytest

from rpeval.agg import (
    append_battle,
    bt_ratings,
    bootstrap_ci,
    judge_battle,
    leaderboard,
    load_battles,
    win_rate_matrix,
)


# ---------- leaderboard：score.json → 0-10 六维 + 总分60 汇总 ----------

def _score_json(tmp_path, entries):
    p = tmp_path / "score.json"
    p.write_text(json.dumps({"cases": entries}, ensure_ascii=False), encoding="utf-8")
    return p


def test_leaderboard_averages_dims_and_total(tmp_path):
    _score_json(tmp_path, [
        {"scene": "s1", "model": "m1", "rated": True,
         "dimensions": {"文笔": {"score": 8.0, "details": {}}, "审查": {"score": 6.0, "details": {}}},
         "total": 14.0},
        {"scene": "s2", "model": "m1", "rated": True,
         "dimensions": {"文笔": {"score": 6.0, "details": {}}, "审查": {"score": 4.0, "details": {}}},
         "total": 10.0},
        {"scene": "s1", "model": "m2", "rated": True,
         "dimensions": {"文笔": {"score": 5.0, "details": {}}, "审查": {"score": 5.0, "details": {}}},
         "total": 10.0},
    ])
    lb = leaderboard(tmp_path)
    rows = {r["model"]: r for r in lb["models"]}
    assert rows["m1"]["dimensions"]["文笔"] == 7.0   # (8+6)/2
    assert rows["m1"]["dimensions"]["审查"] == 5.0
    assert rows["m1"]["total"] == 12.0               # (14+10)/2
    assert rows["m2"]["total"] == 10.0
    # 按总分降序
    assert [r["model"] for r in lb["models"]] == ["m1", "m2"]


def test_leaderboard_rated_false_if_any_case_unrated(tmp_path):
    _score_json(tmp_path, [
        {"scene": "s1", "model": "m1", "rated": True,
         "dimensions": {"审查": {"score": 6.0, "details": {}}}, "total": 6.0},
        {"scene": "s2", "model": "m1", "rated": False,
         "dimensions": {"审查": {"score": 2.0, "details": {}}}, "total": 2.0},
    ])
    lb = leaderboard(tmp_path)
    assert lb["models"][0]["rated"] is False


# ---------- battles.jsonl 读写 ----------

def test_append_and_load_battles(tmp_path):
    append_battle(tmp_path, {"a_code": "A", "b_code": "B", "scene": "s1",
                             "verdict": "a", "margin": 2, "source": "judge"})
    append_battle(tmp_path, {"a_code": "A", "b_code": "B", "scene": "s1",
                             "verdict": "tie", "margin": 0, "source": "human"})
    rows = load_battles(tmp_path)
    assert len(rows) == 2
    assert rows[0]["source"] == "judge"
    assert rows[1]["verdict"] == "tie"


def test_load_battles_missing_file_empty(tmp_path):
    assert load_battles(tmp_path) == []


def test_append_battle_rejects_bad_verdict(tmp_path):
    with pytest.raises(ValueError):
        append_battle(tmp_path, {"a_code": "A", "b_code": "B", "scene": "s",
                                 "verdict": "c", "margin": 1, "source": "judge"})


# ---------- BT 评分 ----------

def _battles(pairs):
    """pairs: [(a,b,winner)] winner∈'a'/'b'/'tie'"""
    return [{"a_code": a, "b_code": b, "verdict": w, "margin": 1, "source": "judge"}
            for a, b, w in pairs]


def test_bt_strong_beats_weak():
    bs = _battles([("x", "y", "a")] * 8 + [("x", "y", "b")] * 2)
    r = bt_ratings(bs)
    assert set(r) == {"x", "y"}
    assert r["x"] > r["y"]


def test_bt_tie_counts_half():
    bs = _battles([("x", "y", "tie")] * 10)
    r = bt_ratings(bs)
    assert abs(r["x"] - r["y"]) < 1e-9


def test_bt_transitive_strength_order():
    # 元组=(a_code, b_code, winner)；winner 'a'=a_code 胜，'b'=b_code 胜
    bs = _battles([("a", "b", "a")] * 9 + [("b", "c", "a")] * 9 + [("a", "c", "a")] * 9)
    r = bt_ratings(bs)
    assert r["a"] > r["b"] > r["c"]


def test_bt_empty_returns_empty():
    assert bt_ratings([]) == {}


# ---------- bootstrap CI ----------

def test_bootstrap_ci_contains_point_estimate():
    rng_pairs = [("x", "y", "a")] * 30 + [("x", "y", "b")] * 10
    bs = _battles(rng_pairs)
    r = bt_ratings(bs)
    lo, hi = bootstrap_ci(bs, "x", n=100, seed=42)
    assert lo <= r["x"] <= hi
    assert lo < hi


def test_bootstrap_ci_deterministic_with_seed():
    bs = _battles([("x", "y", "a")] * 20 + [("x", "y", "b")] * 5)
    a = bootstrap_ci(bs, "x", n=50, seed=7)
    b = bootstrap_ci(bs, "x", n=50, seed=7)
    assert a == b


# ---------- 胜率矩阵 ----------

def test_win_rate_matrix_directions():
    bs = _battles([("x", "y", "a")] * 3 + [("x", "y", "b")] * 1 + [("x", "y", "tie")] * 1)
    m = win_rate_matrix(bs)
    # x 对 y：3胜1负1平 → (3 + 0.5) / 5
    assert m[("x", "y")] == pytest.approx(0.7)
    assert m[("y", "x")] == pytest.approx(0.3)


# ---------- judge 成对比较：双向平均 + 长度截断 ----------

class FakePairJudge:
    """按 (呈现顺序里A的位置) 返回固定偏好：永远偏好呈现为 A 的一方（位置偏差模拟）。"""

    def __init__(self):
        self.seen: list[tuple[str, str]] = []

    async def judge_pair(self, a_text: str, b_text: str) -> dict:
        self.seen.append((a_text, b_text))
        return {"winner": "a", "margin": 3}  # 呈现偏差：总选A


def test_judge_battle_bidirectional_cancels_position_bias():
    j = FakePairJudge()
    # 双方都偏好呈现A → 双向平均后应判平
    out = asyncio.run(judge_battle(j, "回复甲", "回复乙"))
    assert out["winner"] == "tie"
    assert len(j.seen) == 2
    # 第一次 (甲,乙)，第二次交换 (乙,甲)
    assert j.seen[0] == ("回复甲", "回复乙")
    assert j.seen[1] == ("回复乙", "回复甲")


def test_judge_battle_true_preference_survives():
    class ContentJudge:
        async def judge_pair(self, a_text, b_text):
            # 内容里"乙"更好，不管位置
            return {"winner": "a" if "乙" in a_text else "b", "margin": 2}

    out = asyncio.run(judge_battle(ContentJudge(), "回复甲", "回复乙"))
    assert out["winner"] == "b"


def test_judge_battle_truncates_long_replies():
    j = FakePairJudge()
    long_a = "甲" * 5000
    long_b = "乙" * 5000
    asyncio.run(judge_battle(j, long_a, long_b, max_len=100))
    for a, b in j.seen:
        assert len(a) <= 100 and len(b) <= 100
