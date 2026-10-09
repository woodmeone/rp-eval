"""设置体系测试：providers 注册表 / models.yaml+.env 保存 / .env 加载 / /api/settings 端点。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from rpeval.settings import PROVIDERS, load_dotenv, save_settings, settings_view


def _body(judge_over=None, models_over=None):
    j = {"provider": "deepseek", "model_id": "deepseek-chat", "label": "DeepSeek", "api_key": "sk-j"}
    j.update(judge_over or {})
    m = {"provider": "qwen", "model_id": "qwen-plus", "label": "通义", "api_key": "sk-m"}
    return {"judge": j, "models": [dict(m), *(models_over or [])]}


# ---------- providers 注册表 ----------

def test_providers_registry_shape():
    assert len(PROVIDERS) >= 8
    by_id = {p["id"]: p for p in PROVIDERS}
    for pid in ("deepseek", "qwen", "kimi", "doubao", "glm", "openai", "siliconflow", "openrouter"):
        assert pid in by_id, f"缺预置供应商 {pid}"
    for p in PROVIDERS:
        assert p["base_url"].startswith("https://")
        assert p["key_url"].startswith("https://")
        assert p["default_model_id"]
        assert p["key_env"].startswith("RPEVAL_")


# ---------- save_settings ----------

def test_save_writes_yaml_and_env(tmp_path, monkeypatch):
    monkeypatch.delenv("RPEVAL_DEEPSEEK_KEY", raising=False)
    root = tmp_path
    save_settings(root, _body())
    cfg = yaml.safe_load((root / "models.yaml").read_text(encoding="utf-8"))
    assert cfg["judge"]["key_env"] == "RPEVAL_DEEPSEEK_KEY"
    assert cfg["judge"]["base_url"] == "https://api.deepseek.com/v1"
    assert len(cfg["models"]) == 1
    # key 绝不写进 models.yaml
    assert "sk-" not in (root / "models.yaml").read_text(encoding="utf-8")
    env_text = (root / ".env").read_text(encoding="utf-8")
    assert "RPEVAL_DEEPSEEK_KEY=sk-j" in env_text
    assert "RPEVAL_QWEN_KEY=sk-m" in env_text


def test_save_preserves_existing_keys(tmp_path):
    (tmp_path / ".env").write_text("RPEVAL_KIMI_KEY=sk-old\n", encoding="utf-8")
    save_settings(tmp_path, _body())
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "RPEVAL_KIMI_KEY=sk-old" in env_text  # 未动的 key 保留
    assert "RPEVAL_DEEPSEEK_KEY=sk-j" in env_text


def test_save_empty_key_keeps_existing(tmp_path):
    (tmp_path / ".env").write_text("RPEVAL_DEEPSEEK_KEY=sk-keep\n", encoding="utf-8")
    save_settings(tmp_path, _body({"api_key": ""}))
    assert "RPEVAL_DEEPSEEK_KEY=sk-keep" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_save_custom_provider(tmp_path):
    body = _body({"provider": "custom", "base_url": "https://my.relay/v1",
                  "model_id": "gpt-4o", "api_key": "sk-c"})
    save_settings(tmp_path, body)
    cfg = yaml.safe_load((tmp_path / "models.yaml").read_text(encoding="utf-8"))
    assert cfg["judge"]["base_url"] == "https://my.relay/v1"


# ---------- load_dotenv ----------

def test_load_dotenv_sets_missing_only(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "# comment\nRPEVAL_A_KEY=1\nRPEVAL_B_KEY=2\nBAD_LINE\n", encoding="utf-8")
    monkeypatch.setenv("RPEVAL_B_KEY", "from-real-env")
    load_dotenv(tmp_path)
    import os
    assert os.environ["RPEVAL_A_KEY"] == "1"
    assert os.environ["RPEVAL_B_KEY"] == "from-real-env"  # 真实环境变量优先


# ---------- settings_view（GET 结构，不含明文 key） ----------

def test_settings_view_no_plain_key(tmp_path):
    save_settings(tmp_path, _body())
    view = settings_view(tmp_path)
    assert len(view["providers"]) >= 8
    assert view["judge"]["key_env"] == "RPEVAL_DEEPSEEK_KEY"
    assert view["judge"]["key_set"] is True
    dumped = json.dumps(view, ensure_ascii=False)
    assert "sk-j" not in dumped and "sk-m" not in dumped  # 明文 key 绝不回显
    assert "api_key" not in json.dumps(view["judge"]) and "api_key" not in json.dumps(view["models"])


# ---------- HTTP 端点 ----------

@pytest.fixture()
def client(tmp_path):
    from rpeval.web.app import create_app
    app = create_app(config_dir=tmp_path)
    with TestClient(app) as c:
        yield c


def test_get_api_settings_empty(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert len(data["providers"]) >= 8
    assert data["configured"] is False


def test_post_api_settings_roundtrip(client):
    r = client.post("/api/settings", json=_body())
    assert r.status_code == 200
    assert r.json()["ok"] is True
    g = client.get("/api/settings").json()
    assert g["configured"] is True
    assert g["judge"]["model_id"] == "deepseek-chat"
    assert len(g["models"]) == 1
    # 保存后首页配置摘要立即反映
    idx = client.get("/").text
    assert "模型 1" in idx


def test_settings_page_has_nav_and_form(client):
    html = client.get("/settings").text
    assert "class=\"nav-bar\"" in html
    assert "id=\"provider\"" in html or "provider" in html
    assert "保存配置" in html
