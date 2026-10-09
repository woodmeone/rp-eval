"""票02 — 首页配置摘要：已加载模型数/题卡数/维度分布 + 同族警告。"""
from pathlib import Path

from fastapi.testclient import TestClient

from rpeval.web.app import create_app

MODELS = """\
judge:
  model_id: qwen-plus
  provider: qwen
  base_url: https://x
  key_env: K1
models:
  - model_id: deepseek-chat
    provider: deepseek
    base_url: https://x
    key_env: K2
  - model_id: qwen-max
    provider: qwen
    base_url: https://x
    key_env: K3
"""

SCENE = """\
id: t1
card: {name: n, description: d, scenario: s, first_mes: f}
user_script:
  - {turn: 1, text: hi}
checklist:
  - {id: c1, text: a, dimension: 代打, weight: 2}
  - {id: c2, text: b, dimension: 文笔, weight: 1}
tier: null
"""


def _cfg(tmp_path: Path) -> Path:
    (tmp_path / "scenes").mkdir(exist_ok=True)
    (tmp_path / "models.yaml").write_text(MODELS, encoding="utf-8")
    (tmp_path / "scenes" / "t1.yaml").write_text(SCENE, encoding="utf-8")
    return tmp_path


def test_index_shows_config_summary(tmp_path: Path):
    client = TestClient(create_app(config_dir=_cfg(tmp_path)))
    html = client.get("/").text
    assert "配置摘要" in html
    assert "模型 2" in html  # 被测池数量
    assert "题卡 1" in html
    assert "代打" in html and "文笔" in html  # 维度分布


def test_index_shows_family_warning(tmp_path: Path):
    html = TestClient(create_app(config_dir=_cfg(tmp_path))).get("/").text
    assert "同族" in html  # judge qwen 与 qwen-max 同族警告


def test_index_handles_missing_config(tmp_path: Path):
    html = TestClient(create_app(config_dir=tmp_path)).get("/").text
    assert "服务已就绪" in html
    assert "未找到 models.yaml" in html
