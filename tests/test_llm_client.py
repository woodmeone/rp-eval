"""票03 — OpenAICompatClient：请求构造全来自 ModelCfg，响应解析 reply+usage。"""
import asyncio
import json

import httpx
import pytest

from rpeval.config import ModelCfg
from rpeval.llm import OpenAICompatClient


def _cfg(**kw):
    base = dict(model_id="glm-4-plus", provider="zhipu", base_url="https://open.bigmodel.cn/api/paas/v4",
                key_env="RPEVAL_TEST_KEY", temperature=0.3, max_tokens=512)
    base.update(kw)
    return ModelCfg(**base)


def make_client(cfg, captured):
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        body = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": f"echo:{body['model']}"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        })
    return OpenAICompatClient(cfg, transport=httpx.MockTransport(handler))


def test_request_uses_cfg_fields(monkeypatch):
    monkeypatch.setenv("RPEVAL_TEST_KEY", "sk-test")
    captured: list[httpx.Request] = []

    async def go():
        client = make_client(_cfg(), captured)
        try:
            return await client.chat([{"role": "user", "content": "hi"}])
        finally:
            await client.aclose()

    reply, usage = asyncio.run(go())
    req = captured[0]
    assert req.url.path.endswith("/chat/completions")
    assert req.headers["Authorization"] == "Bearer sk-test"
    body = json.loads(req.content)
    assert body["model"] == "glm-4-plus"
    assert body["temperature"] == 0.3
    assert body["max_tokens"] == 512
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert reply == "echo:glm-4-plus"
    assert usage == {"prompt_tokens": 11, "completion_tokens": 7}


def test_missing_key_raises_friendly(monkeypatch):
    monkeypatch.delenv("RPEVAL_TEST_KEY", raising=False)

    async def go():
        client = make_client(_cfg(), [])
        try:
            await client.chat([{"role": "user", "content": "hi"}])
        finally:
            await client.aclose()

    with pytest.raises(RuntimeError, match="RPEVAL_TEST_KEY"):
        asyncio.run(go())
