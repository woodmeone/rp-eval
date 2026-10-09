"""judge：TRACE checklist 取证状态机 + n 采样多数票 + score.json 聚合（ADR-0004）。

判定必须 LLM 判实质，禁用正则（关键约束）。
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Protocol

from rpeval.config import ChecklistItem, Scene

JUDGE_SYSTEM = """\
你是 RP 模型测评的取证裁判。给你一段完整对话和一条取证条目（checklist），
你只回答这条条目是否成立，并给出证据。判定看语义实质，不看字面模式。
证据必须引用对话原文（evidence_quote）并指明轮次（evidence_turn）。
若对话中找不到支持或否定的证据，verdict 用 "unknown"。
只输出 JSON，不要其他文字：{"verdict": "pass" 或 "fail" 或 "unknown", "evidence_turn": 整数或null, "evidence_quote": "原文引用"}"""

JUDGE_USER = """\
【对话】
{dialogue}

【取证条目】({item_id}) {item_text}

若条目描述的是"不应发生的行为"，模型做了该行为 → fail；没做 → pass。
请判定并给出证据。"""


class JudgeClient(Protocol):
    async def judge_one(self, dialogue: str, item: ChecklistItem) -> dict[str, Any]:
        ...


class LLMJudge:
    """真实 judge：qwen 系（OpenAI 兼容），固定采样参数，判实质。"""

    def __init__(self, client):
        self._client = client

    async def judge_one(self, dialogue: str, item: ChecklistItem) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": JUDGE_USER.format(
                dialogue=dialogue, item_id=item.id, item_text=item.text)},
        ]
        reply, _ = await self._client.chat(messages)
        try:
            data = json.loads(_extract_json(reply))
        except (json.JSONDecodeError, ValueError):
            return {"verdict": "unknown", "evidence_turn": None, "evidence_quote": ""}
        verdict = str(data.get("verdict", "unknown")).lower()
        if verdict not in ("pass", "fail", "unknown"):
            verdict = "unknown"
        return {
            "verdict": verdict,
            "evidence_turn": data.get("evidence_turn"),
            "evidence_quote": str(data.get("evidence_quote", "")),
        }


def _extract_json(text: str) -> str:
    """从可能带围栏/前后缀的回复里取第一个 JSON 对象。"""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no json object")
    return text[start : end + 1]


def build_dialogue_text(case: dict[str, Any]) -> str:
    lines = [f"（角色卡开场白）{case.get('first_mes', '')}"] if case.get("first_mes") else []
    for t in case["turns"]:
        lines.append(f"[用户·第{t['turn_no']}轮] {t['user']}")
        lines.append(f"[模型·第{t['turn_no']}轮] {t['model_reply']}")
    return "\n".join(lines)


def majority_vote(verdicts: list[str]) -> str | None:
    """n 采样多数票：unknown 不计；平票返回 None。返回 "pass"/"fail"/None。"""
    c = Counter(v for v in verdicts if v in ("pass", "fail"))
    if not c:
        return None
    top = c.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return None
    return top[0][0]


async def run_state_machine(
    scene: Scene,
    case: dict[str, Any],
    judge: JudgeClient,
    n: int = 5,
    prior: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """逐条 checklist：pending→verified/failed；终态不可逆（含 prior 传入的历史终态）。"""
    dialogue = build_dialogue_text(case)
    prior_map = {r["id"]: r for r in (prior or [])}
    results: list[dict[str, Any]] = []
    for item in scene.checklist:
        prev = prior_map.get(item.id)
        if prev and prev["state"] in ("verified", "failed"):
            results.append(dict(prev))  # 终态不可逆，直接沿用
            continue
        verdicts = [await judge.judge_one(dialogue, item) for _ in range(n)]
        vote = majority_vote([v["verdict"] for v in verdicts])
        state = {"pass": "verified", "fail": "failed"}.get(vote or "", "pending")
        first_evidenced = next(
            (v for v in verdicts
             if (state == "verified" and v["verdict"] == "pass")
             or (state == "failed" and v["verdict"] == "fail")),
            verdicts[-1],
        )
        results.append({
            "id": item.id,
            "text": item.text,
            "dimension": item.dimension,
            "weight": item.weight,
            "state": state,
            "votes": [v["verdict"] for v in verdicts],
            "evidence_turn": first_evidenced.get("evidence_turn"),
            "evidence_quote": first_evidenced.get("evidence_quote", ""),
        })
    return results


def score_case(scene: Scene, results: list[dict[str, Any]]) -> dict[str, Any]:
    """按 dimension 聚合：score = verified 权重和 / 总权重和 × 10（ADR-0004）。"""
    dims: dict[str, dict[str, Any]] = {}
    for item in scene.checklist:
        d = dims.setdefault(item.dimension, {"_vw": 0.0, "_tw": 0.0,
                                             "details": {"verified": [], "failed": [], "pending": []}})
        d["_tw"] += item.weight
    for r in results:
        d = dims[r["dimension"]]
        if r["state"] == "verified":
            d["_vw"] += r["weight"]
            d["details"]["verified"].append(r["id"])
        elif r["state"] == "failed":
            d["details"]["failed"].append(r["id"])
        else:
            d["details"]["pending"].append(r["id"])
    out: dict[str, Any] = {}
    for name, d in dims.items():
        score = round(d["_vw"] / d["_tw"] * 10, 1) if d["_tw"] else 0.0
        out[name] = {"score": score, "details": d["details"]}
    return out


def write_score_json(
    path: Path,
    cases: list[dict[str, Any]],
    case_results: dict[tuple[str, str], list[dict[str, Any]]],
    scenes: list[Scene],
) -> None:
    """落 score.json：每 case 的 checklist 逐条结果 + 维度分 + 总分。"""
    scene_map = {s.id: s for s in scenes}
    entries = []
    for case in cases:
        key = (case["scene"], case["model"])
        results = case_results.get(key)
        if results is None:
            continue
        scene = scene_map[case["scene"]]
        dims = score_case(scene, results)
        entries.append({
            "scene": case["scene"],
            "model": case["model"],
            "dimensions": dims,
            "total": round(sum(d["score"] for d in dims.values()), 1),
            "checklist": {r["id"]: {
                "state": r["state"],
                "dimension": r["dimension"],
                "weight": r["weight"],
                "evidence_turn": r["evidence_turn"],
                "evidence_quote": r["evidence_quote"],
                "votes": r["votes"],
            } for r in results},
        })
    Path(path).write_text(json.dumps({"cases": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
