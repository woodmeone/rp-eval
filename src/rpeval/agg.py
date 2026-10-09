"""票06 — 聚合：六维 0–10 + 总分 60 汇总 / battles.jsonl / Bradley-Terry 评分 + bootstrap CI + 胜率矩阵。

arena-rank 语义自实现（BT MLE via MM 迭代），不依赖外部包；judge 成对比较双向平均防位置偏差（EQ-Bench）。
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Protocol

_VERDICTS = {"a", "b", "tie"}


# ---------- score.json → leaderboard ----------

def leaderboard(run_dir: Path) -> dict[str, Any]:
    """按模型聚合各维 0–10 平均分 + 总分平均 + rated（任一 case 不达标即 False）。"""
    data = json.loads((Path(run_dir) / "score.json").read_text(encoding="utf-8"))
    acc: dict[str, dict[str, Any]] = {}
    for c in data["cases"]:
        m = acc.setdefault(c["model"], {"_dims": {}, "_total": [], "rated": True})
        if not c.get("rated", True):
            m["rated"] = False
        m["_total"].append(c.get("total", 0.0))
        for dim, dv in c.get("dimensions", {}).items():
            m["_dims"].setdefault(dim, []).append(dv.get("score", 0.0))
    models = []
    for name, m in acc.items():
        dims = {d: round(sum(v) / len(v), 2) for d, v in m["_dims"].items()}
        total = round(sum(m["_total"]) / len(m["_total"]), 2) if m["_total"] else 0.0
        models.append({"model": name, "dimensions": dims, "total": total, "rated": m["rated"]})
    models.sort(key=lambda r: r["total"], reverse=True)
    return {"models": models}


# ---------- battles.jsonl ----------

def append_battle(run_dir: Path, battle: dict[str, Any]) -> None:
    b = dict(battle)
    if b.get("verdict") not in _VERDICTS:
        raise ValueError(f"verdict 必须是 {sorted(_VERDICTS)}，得到 {b.get('verdict')!r}")
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "battles.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(b, ensure_ascii=False) + "\n")


def load_battles(run_dir: Path) -> list[dict[str, Any]]:
    f = Path(run_dir) / "battles.jsonl"
    if not f.is_file():
        return []
    rows = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


# ---------- Bradley-Terry（MM 迭代）----------

def _count(battles: list[dict[str, Any]]) -> tuple[set[str], dict[tuple[str, str], float], dict[tuple[str, str], int]]:
    """返回 players, wins[(i,j)]=i 对 j 的胜场(平局各0.5), n[(i,j)]=i,j 交手总场次(无序累加两侧)。"""
    players: set[str] = set()
    wins: dict[tuple[str, str], float] = {}
    games: dict[tuple[str, str], int] = {}
    for b in battles:
        a, c, v = b["a_code"], b["b_code"], b["verdict"]
        players.update((a, c))
        if v == "a":
            wins[(a, c)] = wins.get((a, c), 0.0) + 1.0
        elif v == "b":
            wins[(c, a)] = wins.get((c, a), 0.0) + 1.0
        else:  # tie
            wins[(a, c)] = wins.get((a, c), 0.0) + 0.5
            wins[(c, a)] = wins.get((c, a), 0.0) + 0.5
        games[(a, c)] = games.get((a, c), 0) + 1
        games[(c, a)] = games.get((c, a), 0) + 1
    return players, wins, games


def bt_ratings(battles: list[dict[str, Any]], iters: int = 200, tol: float = 1e-9,
               reg: float = 0.5) -> dict[str, float]:
    """BT 强度（几何均值归一为1）。平局计各0.5胜。

    reg：每对选手加 reg 场"伪平局"（各 reg/2 胜），保证完全压制时 MLE 存在、MM 不发散。
    """
    if not battles:
        return {}
    players, wins, games = _count(battles)
    ps = sorted(players)
    # 正则：任意 i<j 加 reg 交手、各 reg/2 胜
    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            a, b = ps[i], ps[j]
            wins[(a, b)] = wins.get((a, b), 0.0) + reg / 2
            wins[(b, a)] = wins.get((b, a), 0.0) + reg / 2
            games[(a, b)] = games.get((a, b), 0) + reg
            games[(b, a)] = games.get((b, a), 0) + reg
    s = {p: 1.0 for p in ps}
    for _ in range(iters):
        new = {}
        for i in ps:
            w_i = sum(wins.get((i, j), 0.0) for j in ps if j != i)
            denom = 0.0
            for j in ps:
                if j == i:
                    continue
                n_ij = games.get((i, j), 0)
                if n_ij:
                    denom += n_ij / (s[i] + s[j])
            new[i] = w_i / denom if denom > 0 else s[i]
        # 几何均值归一
        gm = math.exp(sum(math.log(max(v, 1e-12)) for v in new.values()) / len(new))
        for i in ps:
            new[i] /= gm
        if max(abs(new[i] - s[i]) for i in ps) < tol:
            s = new
            break
        s = new
    return s


def bootstrap_ci(battles: list[dict[str, Any]], player: str,
                 n: int = 200, seed: int | None = None,
                 alpha: float = 0.05) -> tuple[float, float]:
    """对 battles 有放回重采样，重算 BT，取分位数 95% CI。"""
    rng = random.Random(seed)
    vals: list[float] = []
    m = len(battles)
    for _ in range(n):
        sample = [battles[rng.randrange(m)] for _ in range(m)]
        r = bt_ratings(sample)
        if player in r:
            vals.append(r[player])
    if not vals:
        return (float("nan"), float("nan"))
    vals.sort()
    lo = vals[max(0, int((alpha / 2) * len(vals)) - 1)]
    hi = vals[min(len(vals) - 1, int((1 - alpha / 2) * len(vals)))]
    return (lo, hi)


def win_rate_matrix(battles: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
    """pairwise 胜率：i 对 j 的 (胜+0.5平)/交手数。"""
    players, wins, games = _count(battles)
    out: dict[tuple[str, str], float] = {}
    for i in players:
        for j in players:
            if i == j:
                continue
            g = games.get((i, j), 0)
            if g:
                out[(i, j)] = wins.get((i, j), 0.0) / g
    return out


# ---------- judge 成对比较（双向平均防位置偏差）----------

class PairJudge(Protocol):
    async def judge_pair(self, a_text: str, b_text: str) -> dict[str, Any]:
        ...


async def judge_battle(judge: PairJudge, reply_a: str, reply_b: str,
                       max_len: int = 4000) -> dict[str, Any]:
    """A/B 与 B/A 双向各判一次，映射回内容视角取平均；长回复截断防 length bias。"""
    a = reply_a[:max_len]
    b = reply_b[:max_len]
    first = await judge.judge_pair(a, b)      # 呈现: A=内容a, B=内容b
    second = await judge.judge_pair(b, a)     # 呈现: A=内容b, B=内容a
    score_a = _content_score(first, "a", swap=False) + _content_score(second, "a", swap=True)
    score_b = _content_score(first, "b", swap=False) + _content_score(second, "b", swap=True)
    margin = round((abs(first.get("margin", 0)) + abs(second.get("margin", 0))) / 2, 3)
    if score_a > score_b:
        winner = "a"
    elif score_b > score_a:
        winner = "b"
    else:
        winner = "tie"
    return {"winner": winner, "margin": margin, "score_a": score_a / 2, "score_b": score_b / 2}


def _content_score(result: dict[str, Any], content: str, swap: bool) -> float:
    """把一次判定折算成某内容的得分（胜1/平0.5/负0）。swap=True 时呈现A实为内容b。"""
    w = result.get("winner")
    presented_a = "b" if swap else "a"   # 呈现槽位A对应的真实内容
    if w == "tie":
        return 0.5
    if w not in ("a", "b"):
        return 0.5
    chosen = presented_a if w == "a" else ("a" if swap else "b")
    return 1.0 if chosen == content else 0.0
