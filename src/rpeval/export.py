"""I4 — 导出脚本包：把一次 run 的数据重排成"写视频脚本要什么"。

**这个模块只做视图，不重算指标。** 原始数据已经齐全——`score.json` 里有维度分、结论、
逐条取证（含票数与原文引用），`dialogue.jsonl` 里有逐轮原文与反应判定。缺的从来不是数据，
是**按"写稿需要什么"重排一次**。重算会引入第二份真相（指标口径分叉），所以这里一律读现成的。

对外只有两个入口：`build_script_pack`（→ dict）与 `render_markdown`（→ 文本）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rpeval.agg import leaderboard as _leaderboard
from rpeval.config import Scene

SCHEMA_VERSION = 1

# 口径自述里的"已知局限"。**这张单子必须随工具成长而变短**——
# 它是下游 AI 别说错话的唯一保障，写死了就是撒谎。
KNOWN_LIMITS: tuple[str, ...] = (
    "每 case 只跑 1 次，未重复采样；反应判定为单次判定、无投票——判分噪声没有被平均掉",
    "未含「资料（世界书）」与「预设」层：发给模型的提示词只有角色/简介/场景三行",
    "未含「破甲」（写不写狠）与「写到一半停」相关指标",
    "judge 与被测模型同族只在启动时告警，不阻断运行",
)

# 相关素材（视频里"夸"用的）：角色内拒绝是理想行为
KEEPER_REACTIONS = ("in-char refuse",)

_TONE_RANK = {"bad": 2, "mid": 1, "ok": 0}


def _load_models_cfg(root: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """读 models.yaml 取 judge 与被测池的元信息（模型名/温度）。缺失则降级为 None/[]。"""
    p = Path(root) / "models.yaml"
    if not p.is_file():
        return None, []
    try:
        from rpeval.config import load_models
        cfg = load_models(p)
    except Exception:
        return None, []
    judge = {"model_id": cfg.judge.model_id, "temperature": cfg.judge.temperature}
    pool = [{"model_id": m.model_id, "label": m.label or m.model_id,
             "temperature": m.temperature, "max_tokens": m.max_tokens}
            for m in cfg.models]
    return judge, pool


def _checklist_kinds(scenes: list[Scene]) -> dict[tuple[str, str], bool]:
    """(题卡 id, 检查项 id) → 是否程序化判定（带 check）。"""
    out: dict[tuple[str, str], bool] = {}
    for s in scenes:
        for item in s.checklist:
            out[(s.id, item.id)] = item.check is not None
    return out


def _what_was_tested(root: Path, cases: list[dict[str, Any]], score_cases: list[dict[str, Any]],
                     scenes: list[Scene], redact: bool) -> dict[str, Any]:
    """口径自述：这次到底测了什么、怎么测的、没测什么。"""
    kinds = _checklist_kinds(scenes)
    total = prog = 0
    for sc in score_cases:
        for cid in (sc.get("checklist") or {}):
            total += 1
            if kinds.get((sc.get("scene", ""), cid), False):
                prog += 1
    dims: list[str] = []
    for sc in score_cases:
        for d in (sc.get("dimensions") or {}):
            if d not in dims:
                dims.append(d)
    judge, pool = _load_models_cfg(root)
    return {
        "dimensions": dims,
        "scenes": sorted({c.get("scene", "") for c in cases if c.get("scene")}),
        "models": sorted({c.get("model", "") for c in cases if c.get("model")}),
        "checklist_total": total,
        "checklist_programmatic": prog,
        "checklist_llm": total - prog,
        "samples_per_case": 1,   # 尚无重复采样；改了采样机制这里必须一起改
        "judge": judge,
        "tested_models": pool,
        "known_limits": list(KNOWN_LIMITS),
        "redacted": redact,
    }


def _hammers(score_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """锤点表：每一处失败 = 一行，带齐"点回原文"的四件套（模型/题卡/轮次/证据）。"""
    out: list[dict[str, Any]] = []
    for sc in score_cases:
        tone = (sc.get("verdict") or {}).get("tone", "mid")
        for cid, item in (sc.get("checklist") or {}).items():
            if item.get("state") != "failed":
                continue
            out.append({
                "model": sc.get("model", ""),
                "scene": sc.get("scene", ""),
                "item": cid,
                "turn": item.get("evidence_turn"),
                "claim": item.get("goal") or item.get("text") or cid,
                "dimension": item.get("dimension", ""),
                "quote": str(item.get("evidence_quote", ""))[:80],
                "votes": item.get("votes", []),
                "tone": tone,
            })
    out.sort(key=lambda h: (-_TONE_RANK.get(h["tone"], 1), h["scene"], h["model"]))
    return out


def _highlights(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """正面素材：角色内拒绝的理想片段——视频里"夸"要有配对，不能全是翻车。"""
    from rpeval.web.labels import reaction_label
    out = []
    for c in cases:
        for t in c.get("turns", []):
            r = (t.get("judge") or {}).get("reaction")
            if r not in KEEPER_REACTIONS:
                continue
            quote = str((t.get("judge") or {}).get("reaction_evidence")
                        or (t.get("judge") or {}).get("evidence_quote") or t.get("model_reply", ""))
            out.append({"model": c.get("model", ""), "scene": c.get("scene", ""),
                        "turn": t.get("turn_no"), "reaction": r,
                        "reaction_label": reaction_label(r), "quote": quote[:120]})
    return out


def _scene_matrix(cases: list[dict[str, Any]], score_cases: list[dict[str, Any]]) -> dict[str, Any]:
    """题卡 × 模型对照：哪张题真能分高下，哪张全员满分（=无效题）。"""
    scenes = sorted({c.get("scene", "") for c in cases if c.get("scene")})
    models = sorted({c.get("model", "") for c in cases if c.get("model")})
    by_key = {(sc.get("scene"), sc.get("model")): sc for sc in score_cases}
    cells: dict[str, dict[str, Any]] = {}
    discriminating: list[str] = []
    for s in scenes:
        cells[s] = {}
        totals: list[float] = []
        for m in models:
            sc = by_key.get((s, m))
            if sc is None:
                cells[s][m] = None       # 该模型没跑这张题
                continue
            v = sc.get("verdict") or {}
            cells[s][m] = {"total": sc.get("total"), "tone": v.get("tone", "mid"),
                           "rated": sc.get("rated", True)}
            if isinstance(sc.get("total"), (int, float)):
                totals.append(float(sc["total"]))
        if len(totals) >= 2 and (max(totals) - min(totals)) >= 3.0:
            discriminating.append(s)
    return {"scenes": scenes, "models": models, "cells": cells, "discriminating": discriminating}


def _credibility(score_cases: list[dict[str, Any]]) -> dict[str, Any]:
    """可信度：票数一致性 + 人工抽检（没做就如实说没有，不许编）。"""
    items = 0
    unanimous = 0
    for sc in score_cases:
        for item in (sc.get("checklist") or {}).values():
            votes = [v for v in (item.get("votes") or []) if v in ("pass", "fail")]
            if not votes:
                continue
            items += 1
            if len(set(votes)) == 1:
                unanimous += 1
    return {"items": items, "unanimous": unanimous,
            "unanimous_rate": round(unanimous / items, 3) if items else None,
            "human_recheck": None}


def _redact_case(case: dict[str, Any], tier: str | None) -> dict[str, Any]:
    """脱敏：私有档（tier 非空）的用户话术是红线内容，导出必须打码。

    `payload` / `payload_desc` 永不出现——它们的值可能直接就是私有钓句本身。
    """
    if not tier:
        return case
    out = dict(case)
    out["turns"] = []
    for t in case.get("turns", []):
        t2 = dict(t)
        t2["user"] = f"【私有档 {tier} · 已打码】"
        out["turns"].append(t2)
    return out


def build_script_pack(root: Path, run_id: str, scenes: list[Scene], *,
                      now: str | None = None, redact: bool = True) -> dict[str, Any] | None:
    """一次 run → 脚本数据包。run 不存在返回 None。"""
    from datetime import datetime

    from rpeval.web.evidence import run_detail

    detail = run_detail(Path(root), run_id, list(scenes))
    if detail is None:
        return None

    run_dir = Path(root) / "runs" / run_id
    sj = run_dir / "score.json"
    score_cases: list[dict[str, Any]] = []
    if sj.is_file():
        import json
        try:
            score_cases = json.loads(sj.read_text(encoding="utf-8")).get("cases", [])
        except ValueError:
            score_cases = []

    cases = detail["cases"]
    if redact:
        cases = [_redact_case(c, c.get("tier")) for c in cases]

    try:
        lb = _leaderboard(run_dir)["models"]
    except (FileNotFoundError, ValueError, KeyError):
        lb = []

    turns = sum(len(c.get("turns", [])) for c in detail["cases"])
    cost = sum(float((t.get("meta") or {}).get("cost_cny") or 0)
               for c in detail["cases"] for t in c.get("turns", []))
    judge, pool = _load_models_cfg(root)

    return {
        "schema_version": SCHEMA_VERSION,
        "run": run_id,
        "generated_at": now or datetime.now().isoformat(timespec="seconds"),
        "what_was_tested": _what_was_tested(Path(root), detail["cases"], score_cases, scenes, redact),
        "leaderboard": lb,
        "hammers": _hammers(score_cases),
        "highlights": _highlights(cases),
        "scene_matrix": _scene_matrix(detail["cases"], score_cases),
        "credibility": _credibility(score_cases),
        "meta": {
            "cases": len(cases),
            "turns": turns,
            "scenes": len({c.get("scene") for c in detail["cases"]}),
            "models": sorted({c.get("model", "") for c in detail["cases"] if c.get("model")}),
            "judge": judge,
            "tested_models": pool,
            "cost_cny": round(cost, 6),
        },
    }
