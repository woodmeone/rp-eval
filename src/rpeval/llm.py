"""OpenAI 兼容 chat client：base_url/key/model/采样参数全来自 ModelCfg。"""
from __future__ import annotations

import os
from typing import Any

import httpx

from rpeval.config import ModelCfg


class OpenAICompatClient:
    def __init__(self, cfg: ModelCfg, transport: httpx.AsyncBaseTransport | None = None):
        self.cfg = cfg
        self._client = httpx.AsyncClient(transport=transport) if transport else httpx.AsyncClient()

    async def chat(self, history: list[dict[str, str]]) -> tuple[str, dict[str, Any]]:
        cfg = self.cfg
        key = os.environ.get(cfg.key_env, "")
        if not key:
            raise RuntimeError(f"环境变量 {cfg.key_env} 未设置（模型 {cfg.model_id}）")
        payload = {
            "model": cfg.model_id,
            "messages": history,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
        r = await self._client.post(
            f"{cfg.base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {key}"},
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        reply = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {}) or {}
        return reply, {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }

    async def aclose(self) -> None:
        await self._client.aclose()
