"""设置体系：预置模型商注册表 + 前端保存 models.yaml/.env + .env 加载。

设计原则（ADR-0002 合规红线）：API key 永不写进 models.yaml，只落 .env（已 gitignore）；
GET /api/settings 只回 key_set 布尔，绝不回显明文。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# 预置模型商：id / 中文名 / OpenAI 兼容 base_url / 默认 model_id / key_env / 申请 key 的官网
PROVIDERS: list[dict[str, str]] = [
    {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com/v1",
     "default_model_id": "deepseek-chat", "key_env": "RPEVAL_DEEPSEEK_KEY",
     "key_url": "https://platform.deepseek.com/api_keys"},
    {"id": "qwen", "name": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "default_model_id": "qwen-plus", "key_env": "RPEVAL_QWEN_KEY",
     "key_url": "https://bailian.console.aliyun.com/?apiKey=1"},
    {"id": "kimi", "name": "Kimi / Moonshot", "base_url": "https://api.moonshot.cn/v1",
     "default_model_id": "moonshot-v1-8k", "key_env": "RPEVAL_KIMI_KEY",
     "key_url": "https://platform.moonshot.cn/console/api-keys"},
    {"id": "doubao", "name": "豆包 / 火山方舟", "base_url": "https://ark.cn-beijing.volces.com/api/v3",
     "default_model_id": "doubao-pro-32k", "key_env": "RPEVAL_DOUBAO_KEY",
     "key_url": "https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey"},
    {"id": "glm", "name": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4",
     "default_model_id": "glm-4-plus", "key_env": "RPEVAL_GLM_KEY",
     "key_url": "https://bigmodel.cn/usercenter/proj-mgmt/apikeys"},
    {"id": "openai", "name": "OpenAI / GPT", "base_url": "https://api.openai.com/v1",
     "default_model_id": "gpt-4o-mini", "key_env": "RPEVAL_OPENAI_KEY",
     "key_url": "https://platform.openai.com/api-keys"},
    {"id": "siliconflow", "name": "硅基流动 SiliconFlow", "base_url": "https://api.siliconflow.cn/v1",
     "default_model_id": "deepseek-ai/DeepSeek-V3", "key_env": "RPEVAL_SILICONFLOW_KEY",
     "key_url": "https://cloud.siliconflow.cn/account/ak"},
    {"id": "openrouter", "name": "OpenRouter（聚合）", "base_url": "https://openrouter.ai/api/v1",
     "default_model_id": "anthropic/claude-3.5-sonnet", "key_env": "RPEVAL_OPENROUTER_KEY",
     "key_url": "https://openrouter.ai/settings/keys"},
]

_BY_ID = {p["id"]: p for p in PROVIDERS}


def provider_of(pid: str) -> dict[str, str] | None:
    return _BY_ID.get(pid)


def _env_path(root: Path) -> Path:
    return Path(root) / ".env"


def load_dotenv(root: Path) -> None:
    """读 .env 注入 os.environ，仅补齐缺失项（真实环境变量优先）。"""
    p = _env_path(root)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _read_env_map(root: Path) -> dict[str, str]:
    p = _env_path(root)
    out: dict[str, str] = {}
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _write_env_map(root: Path, updates: dict[str, str]) -> None:
    """合并写 .env：保留未涉及的行，更新/追加 updates 中的键。"""
    existing: list[str] = []
    seen: set[str] = set()
    p = _env_path(root)
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.partition("=")[0].strip()
                if k in updates:
                    existing.append(f"{k}={updates[k]}")
                    seen.add(k)
                    continue
            existing.append(line)
    for k, v in updates.items():
        if k not in seen:
            existing.append(f"{k}={v}")
    p.write_text("\n".join(existing) + "\n", encoding="utf-8")


def _entry_from(item: dict[str, Any], role: str) -> dict[str, Any]:
    """把一个前端条目转成 models.yaml 的模型段；custom 需自带 base_url。"""
    pid = str(item.get("provider", ""))
    prov = provider_of(pid)
    if prov is None:  # 自定义 / 中转站
        base_url = str(item.get("base_url", "")).strip()
        key_env = str(item.get("key_env", "")).strip() or f"RPEVAL_{pid.upper()}_KEY"
        model_id = str(item.get("model_id", "")).strip()
    else:
        base_url = str(item.get("base_url") or prov["base_url"]).strip()
        key_env = prov["key_env"]
        model_id = str(item.get("model_id") or prov["default_model_id"]).strip()
    entry = {
        "model_id": model_id,
        "provider": pid or "custom",
        "base_url": base_url,
        "key_env": key_env,
    }
    label = str(item.get("label", "")).strip() or (prov["name"] if prov else pid)
    if label:
        entry["label"] = label
    return entry


def save_settings(root: Path, body: dict[str, Any]) -> None:
    """写 models.yaml（不含 key）+ .env（仅非空 key）。judge 必填，models 至少一条。"""
    root = Path(root)
    judge_item = body.get("judge") or {}
    models_items = body.get("models") or []
    if not judge_item.get("provider"):
        raise ValueError("必须配置 judge 模型")
    if not models_items:
        raise ValueError("至少配置一个被测模型")

    judge = _entry_from(judge_item, "judge")
    models = [_entry_from(m, "model") for m in models_items]

    # key 落 .env（空值表示"保持原样"，不覆盖）
    updates: dict[str, str] = {}
    for item, entry in [(judge_item, judge)] + [(m, e) for m, e in zip(models_items, models)]:
        key = str(item.get("api_key", "")).strip()
        if key:
            updates[entry["key_env"]] = key
    if updates:
        _write_env_map(root, updates)

    doc = {"judge": judge, "models": models}
    (root / "models.yaml").write_text(
        "# 由 rp-eval 设置页生成（改配置不改代码；key 存 .env，本文件可开源）\n"
        + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8")


def settings_view(root: Path) -> dict[str, Any]:
    """GET /api/settings 的响应：预置商 + 当前配置（key 只回布尔，不回明文）。"""
    root = Path(root)
    env = _read_env_map(root)
    mp = root / "models.yaml"
    judge: dict[str, Any] = {}
    models: list[dict[str, Any]] = []
    if mp.is_file():
        try:
            raw = yaml.safe_load(mp.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            raw = {}
        def _mask(e: dict[str, Any]) -> dict[str, Any]:
            ke = e.get("key_env", "")
            return {
                "provider": e.get("provider", ""),
                "model_id": e.get("model_id", ""),
                "base_url": e.get("base_url", ""),
                "label": e.get("label", ""),
                "key_env": ke,
                "key_set": bool(env.get(ke) or os.environ.get(ke)),
            }
        if isinstance(raw.get("judge"), dict):
            judge = _mask(raw["judge"])
        for m in raw.get("models") or []:
            if isinstance(m, dict):
                models.append(_mask(m))
    return {
        "providers": PROVIDERS,
        "judge": judge,
        "models": models,
        "configured": bool(judge and models),
    }
