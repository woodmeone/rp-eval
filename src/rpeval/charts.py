"""票07 — 图表：matplotlib 雷达图 + 象限图 PNG（像素四色主题，横/竖两套尺寸）。

runner 流程末端（write_score_json 落盘后）自动触发，无需手动命令。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

# 像素四色（与 web/theme.py 同源）
INK = "#0b0c15"
PAPER = "#fbfdfd"
SAKURA = "#e8a0bf"
STEEL = "#bac2f7"
CYCLE = [STEEL, SAKURA, "#8fa0d0", "#d08fae", "#a0c4f7", "#f7a0c4"]

SIZES = {"landscape": (1920, 1080), "portrait": (1080, 1920)}

# 维度展示顺序（CONTEXT.md 六项 + 扩展维度；雷达图只画这 8 轴）
DIM_ORDER = ["文笔", "入戏", "审查", "舔狗", "代打", "记忆", "格式", "长上下文"]


def _setup_cjk() -> None:
    """中文字体：优先微软雅黑/黑体，缺失时回退默认（图仍能出，仅中文变方框）。"""
    try:
        names = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    except Exception:
        names = set()
    for cand in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC"):
        if cand in names:
            plt.rcParams["font.sans-serif"] = [cand, "DejaVu Sans"]
            break
    plt.rcParams["axes.unicode_minus"] = False


def _dpi_for(w_px: int) -> int:
    return 160


def _fig_for(kind: str, size_key: str):
    w, h = SIZES[size_key]
    dpi = _dpi_for(w)
    fig = plt.figure(figsize=(w / dpi, h / dpi), dpi=dpi, facecolor=INK)
    return fig, w, h, dpi


def _load_models(run_dir: Path) -> list[dict[str, Any]]:
    data = json.loads((Path(run_dir) / "score.json").read_text(encoding="utf-8"))
    acc: dict[str, dict[str, float]] = {}
    rated: dict[str, bool] = {}
    for c in data["cases"]:
        m = c["model"]
        rated[m] = rated.get(m, True) and c.get("rated", True)
        d = acc.setdefault(m, {})
        for dim, dv in c.get("dimensions", {}).items():
            d.setdefault(dim, []).append(dv.get("score", 0.0))
    models = []
    for name, dims in acc.items():
        avg = {k: sum(v) / len(v) for k, v in dims.items()}
        # 审查 details 取该模型任一含阶梯 details 的 case
        stress = {}
        for c in data["cases"]:
            if c["model"] == name and "崩档点" in c.get("dimensions", {}).get("审查", {}).get("details", {}):
                stress = c["dimensions"]["审查"]["details"]
                break
        models.append({"model": name, "dims": avg, "rated": rated.get(name, True), "stress": stress})
    return models


def radar_png(models: list[dict[str, Any]], out: Path, size_key: str) -> Path:
    _setup_cjk()
    fig, w, h, dpi = _fig_for("radar", size_key)
    ax = fig.add_subplot(111, polar=True, facecolor=INK)
    labels = DIM_ORDER
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    for i, m in enumerate(models):
        vals = [m["dims"].get(d, 0.0) for d in labels]
        vals += vals[:1]
        color = CYCLE[i % len(CYCLE)]
        ax.plot(angles, vals, color=color, linewidth=2.5, label=m["model"])
        ax.fill(angles, vals, color=color, alpha=0.15)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, color=PAPER, fontsize=13)
    ax.set_ylim(0, 10)
    ax.set_yticks([2, 4, 6, 8, 10])
    ax.set_yticklabels(["2", "4", "6", "8", "10"], color="#5a5f7a", fontsize=9)
    ax.grid(color="#2a2f45", linewidth=1)
    ax.spines["polar"].set_color("#2a2f45")
    ax.tick_params(colors=PAPER)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), frameon=False,
              labelcolor=PAPER, fontsize=11)
    fig.suptitle("六维雷达 · 0–10", color=PAPER, fontsize=16, y=0.98)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=INK, dpi=dpi)
    plt.close(fig)
    return out


QUADRANT_LABELS = {  # (OOR高?, BUR高?) → 命名
    (False, False): "演得好且守得住",
    (True, False): "太老实",
    (False, True): "太野",
    (True, True): "双差",
}


def quadrant_png(models: list[dict[str, Any]], out: Path, size_key: str) -> Path | None:
    """横轴 OOR、纵轴 BUR、点大小=BSR；无任何阶梯数据则不产图（返回 None）。"""
    pts = [m for m in models if m["stress"].get("OOR") is not None
           or m["stress"].get("BUR") is not None]
    if not pts:
        return None
    _setup_cjk()
    fig, w, h, dpi = _fig_for("quadrant", size_key)
    ax = fig.add_subplot(111, facecolor=INK)
    mid_x = mid_y = 0.5
    ax.axvline(mid_x, color="#2a2f45", lw=1.5)
    ax.axhline(mid_y, color="#2a2f45", lw=1.5)
    for (ox, by), name in QUADRANT_LABELS.items():
        tx = 0.25 if not ox else 0.75
        ty = 0.25 if not by else 0.75
        ax.text(tx, ty, name, color="#5a5f7a", fontsize=13,
                ha="center", va="center")
    for i, m in enumerate(pts):
        x = m["stress"].get("OOR") or 0.0
        y = m["stress"].get("BUR") or 0.0
        bsr = m["stress"].get("BSR")
        size = 300 if bsr is None or bsr >= 1.0 else 120
        color = CYCLE[i % len(CYCLE)]
        ax.scatter(x, y, s=size, color=color, edgecolors=PAPER, linewidths=1.5, zorder=3)
        ax.annotate(m["model"], (x, y), color=PAPER, fontsize=11,
                    xytext=(6, 6), textcoords="offset points")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlabel("OOR 出戏率 →", color=PAPER, fontsize=12)
    ax.set_ylabel("BUR 破防率 →", color=PAPER, fontsize=12)
    ax.tick_params(colors="#5a5f7a")
    for spine in ax.spines.values():
        spine.set_color("#2a2f45")
    ax.set_title("审查象限 · 点大=BSR守住", color=PAPER, fontsize=16)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=INK, dpi=dpi)
    plt.close(fig)
    return out


def render_run_charts(run_dir: Path) -> list[Path]:
    """读 score.json → charts/ 下雷达图+象限图（横竖两套）。返回产出的文件列表。"""
    run_dir = Path(run_dir)
    models = _load_models(run_dir)
    charts = run_dir / "charts"
    out: list[Path] = []
    for size_key in SIZES:
        out.append(radar_png(models, charts / f"雷达图_{size_key}.png", size_key))
        q = quadrant_png(models, charts / f"象限图_{size_key}.png", size_key)
        if q is not None:
            out.append(q)
    return out
