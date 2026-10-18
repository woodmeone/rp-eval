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
    redacted_cases = sum(1 for c in cases if c.get("tier")) if redact else 0
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
        # 打码开关开着 ≠ 真的打了码。没有私有档时不许写"已打码"，那是假口径。
        "redacted_cases": redacted_cases,
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


def _redaction_note(w: dict[str, Any]) -> str:
    """脱敏口径：开关状态与**实际打码的 case 数**要分开说。"""
    if not w["redacted"]:
        return "⚠ 已关闭脱敏——本文件含私有话术，不得外传"
    n = w.get("redacted_cases", 0)
    if n:
        return f"私有档话术已打码（{n} 个 case），私密题不出现在本文件"
    return "本 run 无私有档 case（没有 tier），无需打码"


def render_markdown(pack: dict[str, Any]) -> str:
    """脚本包 → markdown（七块）。**给 AI 与人的同一份文本**，不另做简版。"""
    from rpeval.web.labels import metric_label, metric_value

    w = pack["what_was_tested"]
    meta = pack["meta"]
    L: list[str] = []
    L.append(f"# {pack['run']} · RP 横评数据包")
    L.append(f"> 生成 {pack['generated_at']} · 口径 v{pack['schema_version']} · "
             f"judge={((w.get('judge') or {}).get('model_id')) or '—'}")
    L.append("")

    # 〇 写脚本前必读
    L.append("## 〇 写脚本前必读（这段是给 AI 的）")
    L.append(f"- **测了什么**：{'·'.join(w['dimensions']) or '—'}；共 {w['checklist_total']} 条检查项"
             f"（LLM 判 {w['checklist_llm']} 条，程序化判 {w['checklist_programmatic']} 条）")
    L.append(f"- **怎么测的**：{len(w['models'])} 个模型 × {len(w['scenes'])} 张题卡，"
             f"每 case 跑 {w['samples_per_case']} 次")
    if w.get("tested_models"):
        temps = "、".join(f"{m['model_id']}@{m['temperature']}" for m in w["tested_models"])
        L.append(f"- **采样参数**：{temps}")
    L.append(f"- **没测什么**：")
    for lim in w["known_limits"]:
        L.append(f"  - {lim}")
    L.append(f"- **脱敏**：{_redaction_note(w)}")
    L.append("")

    # 一 榜单
    L.append("## 一 榜单")
    if pack["leaderboard"]:
        dims = [d for m in pack["leaderboard"] for d in m.get("dimensions", {})]
        dim_names = list(dict.fromkeys(dims))
        L.append("| 模型 | 总分 | " + " | ".join(dim_names) + " | 备注 |")
        L.append("|---" * (3 + len(dim_names)) + "|")
        for m in pack["leaderboard"]:
            cells = " | ".join(str(m.get("dimensions", {}).get(d, "—")) for d in dim_names)
            note = "" if m.get("rated", True) else "底线没守住·不给推荐"
            L.append(f"| {m['model']} | {m.get('total')} | {cells} | {note} |")
    else:
        L.append("（无 score.json，无榜单数据）")
    L.append("")

    # 二 锤点
    L.append("## 二 锤点（可直接剪）")
    if pack["hammers"]:
        L.append("| # | 模型 | 题卡 | 轮 | 检查项 | 证据原文 | 票 |")
        L.append("|---|---|---|---|---|---|---|")
        for i, h in enumerate(pack["hammers"], 1):
            votes = "".join("✓" if v == "pass" else "✗" for v in h["votes"]) or "—"
            L.append(f"| {i} | {h['model']} | {h['scene']} | {h['turn']} | {h['claim']} | "
                     f"{h['quote']} | {votes} |")
    else:
        L.append("（本 run 无失败项）")
    L.append("")

    # 三 正面素材
    L.append("## 三 守得住的正面素材")
    if pack["highlights"]:
        L.append("| 模型 | 题卡 | 轮 | 反应 | 原文 |")
        L.append("|---|---|---|---|---|")
        for h in pack["highlights"]:
            L.append(f"| {h['model']} | {h['scene']} | {h['turn']} | {h['reaction_label']} | {h['quote']} |")
    else:
        L.append("（本 run 无「用角色的话拒绝」的理想片段）")
    L.append("")

    # 四 题卡 × 模型
    m4 = pack["scene_matrix"]
    L.append("## 四 题卡 × 模型对照")
    if m4["scenes"] and m4["models"]:
        L.append("| 题卡 | " + " | ".join(m4["models"]) + " | 拉得开? |")
        L.append("|---" * (m4["models"].__len__() + 2) + "|")
        for s in m4["scenes"]:
            cells = []
            for m in m4["models"]:
                c = m4["cells"][s][m]
                cells.append("—" if c is None else str(c["total"]))
            L.append(f"| {s} | " + " | ".join(cells) + " | "
                     + ("✅" if s in m4["discriminating"] else "") + " |")
    else:
        L.append("（无数据）")
    L.append("")

    # 五 可信度
    cr = pack["credibility"]
    L.append("## 五 可信度与边界")
    L.append(f"- 检查项 {cr['items']} 条，其中票数完全一致 {cr['unanimous']} 条"
             + (f"（一致率 {cr['unanimous_rate']}）" if cr["unanimous_rate"] is not None else ""))
    L.append("- 人工抽检：" + ("未做（judge 与人的一致率无从谈起）" if cr["human_recheck"] is None
                              else str(cr["human_recheck"])))
    for lim in w["known_limits"]:
        L.append(f"- ⚠ {lim}")
    L.append("")

    # 六 元数据
    L.append("## 六 元数据（口播用）")
    L.append(f"- run：{pack['run']} ｜ 生成：{pack['generated_at']}")
    L.append(f"- 规模：{meta['cases']} 个 case · {meta['turns']} 轮 · "
             f"{len(meta['models'])} 模型 · {meta['scenes']} 题卡")
    L.append(f"- 成本：¥{meta['cost_cny']}")
    if meta.get("tested_models"):
        L.append("- 模型池：" + "、".join(
            f"{m['model_id']}（温度 {m['temperature']}，上限 {m['max_tokens']} tokens）"
            for m in meta["tested_models"]))
    L.append("")
    return "\n".join(L)
