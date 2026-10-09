"""票08 — 控制台：SSE 事件序列化、run 互斥锁、轮次卡片、终端彩色、回放。"""
import json

import pytest

from rpeval.web.console import (
    RunManager,
    ALERT_REACTIONS,
    build_turn_card,
    format_sse,
    print_turn_card,
    replay_events,
)


def _turn(n=1, reply="r", reaction="in-char comply", quote="证据"):
    return {"turn_no": n, "user": f"u{n}", "model_reply": reply,
            "judge": {"reaction": reaction, "evidence_quote": quote},
            "meta": {"latency_ms": 10, "tokens": {}, "cost_cny": 0.01}}


# ---------- SSE 序列化 ----------

def test_format_sse_event_and_data_lines():
    s = format_sse("turn", {"a": 1, "中": "文"})
    assert s.startswith("event: turn\n")
    assert 'data: {"a": 1' in s
    assert s.endswith("\n\n")
    assert "\\u4e2d" not in s  # ensure_ascii=False，中文原样


# ---------- 轮次卡片 ----------

def test_build_turn_card_normal_steel():
    c = build_turn_card("deepseek-chat", _turn(reaction="in-char comply"))
    assert c["model"] == "deepseek-chat"
    assert c["turn_no"] == 1
    assert c["reaction"] == "in-char comply"
    assert c["badge"] == "steel"          # 正常=钢蓝
    assert c["evidence"] == "证据"


def test_build_turn_card_alert_sakura():
    for r in ALERT_REACTIONS:
        c = build_turn_card("m", _turn(reaction=r))
        assert c["badge"] == "sakura"     # 警报=樱粉


def test_build_turn_card_missing_judge():
    c = build_turn_card("m", {"turn_no": 2, "user": "u", "model_reply": "x",
                              "judge": None, "meta": {}})
    assert c["reaction"] is None
    assert c["badge"] == "steel"


# ---------- 终端彩色打印 ----------

def test_print_turn_card_contains_ansi(capsys):
    print_turn_card(build_turn_card("m", _turn(reaction="OOC refuse")))
    out = capsys.readouterr().out
    assert "\033[" in out
    assert "OOC refuse" in out
    assert "m" in out


# ---------- RunManager 互斥 ----------

def test_run_manager_mutex():
    rm = RunManager()
    assert rm.acquire() is True
    assert rm.acquire() is False   # 占用时拒绝
    rm.release()
    assert rm.acquire() is True


def test_run_manager_publish_history_polling():
    rm = RunManager()
    card = build_turn_card("m", _turn())
    rm.publish("turn", card)
    assert rm.turn_cards() == [card]
    rm.publish("reaction", build_turn_card("m", _turn(2)))
    assert len(rm.history) == 2
    assert len(rm.turn_cards()) == 1


def test_run_manager_progress_and_done():
    rm = RunManager()
    rm.set_plan(2)
    assert rm.progress == 0.0
    rm.mark_case_done()
    assert rm.progress == 0.5
    rm.mark_case_done()
    assert rm.progress == 1.0
    assert not rm.done
    rm.mark_done()
    assert rm.done


def test_run_manager_release_when_done():
    rm = RunManager()
    rm.acquire()
    assert rm.is_busy
    rm.release()
    assert not rm.is_busy


# ---------- 回放 dialogue.jsonl ----------

def test_replay_events_from_dialogue(tmp_path):
    case = {"scene": "s", "model": "m1", "turns": [_turn(1), _turn(2, reaction="break")]}
    (tmp_path / "dialogue.jsonl").write_text(json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8")
    events = replay_events(tmp_path)
    assert len(events) == 2
    assert events[0]["turn_no"] == 1
    assert events[1]["badge"] == "sakura"


def test_replay_events_missing_file(tmp_path):
    assert replay_events(tmp_path) == []
