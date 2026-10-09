"""票08 — 控制台：SSE 事件序列化、轮次卡片、终端彩色打印、run 互斥与回放。"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
from pathlib import Path
from typing import Any

# 警报类反应（樱粉徽章）：出戏/破防/有害
ALERT_REACTIONS = frozenset({"OOC refuse", "break", "harmful comply"})


def format_sse(event: str, data: Any) -> str:
    """SSE 帧：event 行 + data 行（中文原样，双换行结尾）。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def build_turn_card(model: str, turn: dict[str, Any]) -> dict[str, Any]:
    """一轮 → 卡片 [轮次|模型代号|反应徽章|证据摘要]；警报类=樱粉，正常=钢蓝。"""
    judge = turn.get("judge") or {}
    reaction = judge.get("reaction")
    badge = "sakura" if reaction in ALERT_REACTIONS else "steel"
    quote = str(judge.get("evidence_quote") or judge.get("reaction_evidence") or "")
    return {
        "model": model,
        "turn_no": turn.get("turn_no"),
        "reaction": reaction,
        "badge": badge,
        "evidence": quote[:80],
        "cost_cny": (turn.get("meta") or {}).get("cost_cny", 0),
    }


_SAKURA_RGB = (232, 160, 191)
_STEEL_RGB = (186, 194, 247)


def print_turn_card(card: dict[str, Any]) -> None:
    """终端彩色打印同一事件流：樱粉=警报，钢蓝=正常。"""
    r, g, b = _SAKURA_RGB if card["badge"] == "sakura" else _STEEL_RGB
    label = card["reaction"] or "—"
    print(f"\033[38;2;{r};{g};{b}m"
          f"[第{card['turn_no']}轮|{card['model']}|{label}] {card['evidence']}\033[0m")


class RunManager:
    """一次仅一个 run（互斥）；已完成卡片进 history，SSE 端点轮询 history+done 实现实时流与重连回放。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._busy = False
        self._done = False
        self._history: list[dict[str, Any]] = []
        self._total_cases = 0
        self._done_cases = 0

    # --- 互斥 ---
    def acquire(self) -> bool:
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            self._done = False
            return True

    def release(self) -> None:
        with self._lock:
            self._busy = False

    @property
    def is_busy(self) -> bool:
        return self._busy

    @property
    def done(self) -> bool:
        return self._done

    def mark_done(self) -> None:
        self._done = True

    # --- 进度 ---
    def set_plan(self, total_cases: int) -> None:
        self._total_cases = max(1, total_cases)
        self._done_cases = 0

    def mark_case_done(self) -> None:
        self._done_cases += 1

    @property
    def progress(self) -> float:
        return min(1.0, self._done_cases / max(1, self._total_cases))

    # --- 事件流（history 驱动，SSE 轮询）---
    def publish(self, event_type: str, data: dict[str, Any]) -> None:
        with self._lock:
            self._history.append((event_type, data))

    @property
    def history(self) -> list[tuple[str, dict[str, Any]]]:
        return list(self._history)

    def turn_cards(self) -> list[dict[str, Any]]:
        return [d for (t, d) in self._history if t == "turn"]

    def reset(self) -> None:
        with self._lock:
            self._history = []
            self._total_cases = 0
            self._done_cases = 0
            self._done = False


def replay_events(run_dir: Path) -> list[dict[str, Any]]:
    """SSE 重连补看：读 dialogue.jsonl 回放已发生轮次卡片。"""
    f = Path(run_dir) / "dialogue.jsonl"
    if not f.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError:
            continue
        for t in case.get("turns", []):
            out.append(build_turn_card(case["model"], t))
    return out
