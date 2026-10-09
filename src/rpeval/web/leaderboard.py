"""票10 — 榜单页数据 + 盲测记票：leaderboard 聚合（0-10/总分/Elo+CI/胜率/图表内嵌）与 A/B 代号盲评。"""
from __future__ import annotations

import base64
import json
import secrets
import threading
from pathlib import Path
from typing import Any

from rpeval.agg import append_battle, bootstrap_ci, bt_ratings, leaderboard, load_battles, win_rate_matrix


def _charts_b64(run_dir: Path) -> dict[str, str]:
    out = {}
    charts = run_dir / "charts"
    if not charts.is_dir():
        return out
    for p in charts.glob("*.png"):
        out[p.stem] = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    return out


def build_leaderboard(root: Path, run_id: str | None = None) -> dict[str, Any]:
    """score.json → 六维/总分 + battles.jsonl → BT Elo（95% CI）+ 胜率矩阵 + 图表 base64。"""
    from rpeval.web.evidence import list_runs
    runs = list_runs(root)
    if run_id is None:
        run_id = runs[-1] if runs else None
    if run_id is None:
        return {"run": None, "models": [], "elo": {}, "elo_ci": {}, "win_rate": {}, "charts": {}}
    run_dir = Path(root) / "runs" / run_id
    try:
        lb = leaderboard(run_dir)
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        lb = {"models": []}
    battles = load_battles(run_dir)
    elo = bt_ratings(battles)
    elo_ci = {m: bootstrap_ci(battles, m, n=100, seed=42) for m in elo} if battles else {}
    wr: dict[str, dict[str, float]] = {}
    for (i, j), v in win_rate_matrix(battles).items():
        wr.setdefault(i, {})[j] = round(v, 3)
    # 细节锤点：从 score.json 抽每维 details
    hammers: dict[str, dict[str, Any]] = {}
    sj = run_dir / "score.json"
    if sj.is_file():
        for c in json.loads(sj.read_text(encoding="utf-8")).get("cases", []):
            h = hammers.setdefault(c["model"], {})
            for dim, dv in c.get("dimensions", {}).items():
                h.setdefault(dim, []).append(dv.get("details", {}))
    return {"run": run_id, "models": lb["models"], "elo": {k: round(v, 3) for k, v in elo.items()},
            "elo_ci": {k: [round(a, 3), round(b, 3)] for k, (a, b) in elo_ci.items()},
            "win_rate": wr, "charts": _charts_b64(run_dir), "hammers": hammers}


# ---------- 盲测：代号并排 + 记票 + 揭名 ----------

class BlindStore:
    """内存 pair 映射（pair_id → 真名），投票前响应永不含真名；投一次即失效。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pairs: dict[str, dict[str, Any]] = {}

    def make_pair(self, run_dir: Path, scene_id: str) -> dict[str, Any] | None:
        """从 dialogue.jsonl 取该场景 ≥2 模型的末轮回复，随机分配代号 A/B。"""
        dj = Path(run_dir) / "dialogue.jsonl"
        if not dj.is_file():
            return None
        replies: list[tuple[str, str]] = []
        for line in dj.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
            if c.get("scene") == scene_id and c.get("turns"):
                replies.append((c["model"], c["turns"][-1]["model_reply"]))
        if len(replies) < 2:
            return None
        (ma, ta), (mb, tb) = replies[0], replies[1]
        if secrets.randbelow(2):
            ma, mb, ta, tb = mb, ma, tb, ta
        pid = secrets.token_hex(6)
        with self._lock:
            self._pairs[pid] = {"a": ma, "b": mb, "scene": scene_id, "run": str(run_dir)}
        return {"pair_id": pid, "a_text": ta, "b_text": tb}

    def vote(self, pair_id: str, verdict: str, margin: int) -> dict[str, Any] | None:
        """记票 → 追加 battles.jsonl（source=human）→ 揭名。pair 一次性。"""
        with self._lock:
            info = self._pairs.pop(pair_id, None)
        if info is None:
            return None
        append_battle(Path(info["run"]), {"a_code": info["a"], "b_code": info["b"],
                                          "scene": info["scene"], "verdict": verdict,
                                          "margin": margin, "source": "human"})
        return {"names": {"a": info["a"], "b": info["b"]}, "verdict": verdict, "margin": margin}
