"""票08 — 控制台端点集成：/console 渲染、/api/start 互斥、/api/history 回放、SSE 流。"""
import asyncio
import json
import time

import pytest
from starlette.testclient import TestClient

from rpeval.web.app import create_app

MODELS = """\
judge:
  model_id: qwen-plus
  provider: qwen
  base_url: https://x/v1
  key_env: K_J
models:
  - model_id: deepseek-chat
    label: DeepSeek
    provider: deepseek
    base_url: https://x/v1
    key_env: K_D
"""

SCENE = """\
id: s1
card: {name: 学姐, description: d, scenario: sc, first_mes: hi}
user_script:
  - {turn: 1, text: "x"}
checklist:
  - {id: c1, text: 是否替用户说话, dimension: 代打, weight: 1}
tier: null
"""


class FakeClient:
    """按 system 提示词路由：judge 取证/压力体检返回 JSON，被测模型返回台词。"""

    def __init__(self, cfg):
        self.cfg = cfg

    async def chat(self, history):
        sys = history[0]["content"]
        if "取证裁判" in sys:
            return json.dumps({"verdict": "pass", "evidence_turn": 1, "evidence_quote": "q"}), {}
        if "压力体检" in sys:
            return json.dumps({"reaction": "in-char comply", "evidence_quote": "q"}), {}
        return "好的", {"prompt_tokens": 10, "completion_tokens": 5}


@pytest.fixture()
def client(tmp_path):
    (tmp_path / "models.yaml").write_text(MODELS, encoding="utf-8")
    d = tmp_path / "scenes"
    d.mkdir()
    (d / "s1.yaml").write_text(SCENE, encoding="utf-8")
    app = create_app(tmp_path, client_factory=FakeClient)
    return TestClient(app)


def test_console_page_renders_picks(client):
    r = client.get("/console")
    assert r.status_code == 200
    assert "开始测评" in r.text
    assert "deepseek-chat" in r.text
    assert "s1" in r.text


def test_start_returns_202_then_free(client):
    r = client.post("/api/start", json={"models": ["deepseek-chat"], "scenes": ["s1"]})
    assert r.status_code == 202
    # 等 run 完成（fake client 秒回）
    deadline = time.time() + 5
    while client.get("/api/busy").json()["busy"] and time.time() < deadline:
        time.sleep(0.05)
    assert not client.get("/api/busy").json()["busy"]


def test_history_after_run_has_turn_cards(client):
    client.post("/api/start", json={"models": ["deepseek-chat"], "scenes": ["s1"]})
    deadline = time.time() + 5
    while client.get("/api/busy").json()["busy"] and time.time() < deadline:
        time.sleep(0.05)
    hist = client.get("/api/history").json()
    assert len(hist) == 1
    assert hist[0]["model"] == "deepseek-chat"
    assert hist[0]["turn_no"] == 1


def test_start_rejects_unknown_selection(client):
    r = client.post("/api/start", json={"models": ["nope"], "scenes": ["s1"]})
    assert r.status_code in (400, 422)


def test_sse_stream_delivers_events(client):
    client.post("/api/start", json={"models": ["deepseek-chat"], "scenes": ["s1"]})
    with client.stream("GET", "/api/stream") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = "".join(chunk for chunk in resp.iter_text())
    assert "event: turn" in body or "event: done" in body
