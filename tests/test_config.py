"""票02 — load_models / load_scenes / 同族校验。"""
from pathlib import Path

import pytest

from rpeval.config import ConfigError, family_warnings, load_models, load_scenes

VALID_MODELS = """\
judge:
  model_id: qwen-plus
  provider: qwen
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  key_env: RPEVAL_QWEN_KEY
  temperature: 0.0
models:
  - model_id: deepseek-chat
    provider: deepseek
    base_url: https://api.deepseek.com/v1
    key_env: RPEVAL_DEEPSEEK_KEY
    label: DeepSeek
  - model_id: claude-sonnet-4
    provider: anthropic
    base_url: https://api.anthropic.com/v1
    key_env: RPEVAL_CLAUDE_KEY
    label: Claude
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_load_models_returns_judge_and_pool(tmp_path: Path):
    cfg = load_models(_write(tmp_path, "models.yaml", VALID_MODELS))
    assert cfg.judge.model_id == "qwen-plus"
    assert cfg.judge.temperature == 0.0
    assert [m.model_id for m in cfg.models] == ["deepseek-chat", "claude-sonnet-4"]
    assert cfg.models[0].label == "DeepSeek"


def test_load_models_missing_key_env_field_names_model(tmp_path: Path):
    bad = VALID_MODELS.replace("    key_env: RPEVAL_DEEPSEEK_KEY\n", "")
    with pytest.raises(ConfigError) as e:
        load_models(_write(tmp_path, "models.yaml", bad))
    msg = str(e.value)
    assert "models.yaml" in msg
    assert "key_env" in msg
    assert "deepseek-chat" in msg


def test_load_models_missing_required_field(tmp_path: Path):
    bad = VALID_MODELS.replace("  provider: qwen\n", "")
    with pytest.raises(ConfigError) as e:
        load_models(_write(tmp_path, "models.yaml", bad))
    assert "provider" in str(e.value)
    assert "judge" in str(e.value)


def test_load_models_broken_yaml_reports_file(tmp_path: Path):
    with pytest.raises(ConfigError) as e:
        load_models(_write(tmp_path, "models.yaml", "judge: [unclosed"))
    assert "models.yaml" in str(e.value)


SCENE_GOOD = """\
id: 学姐卡毒舌v1
card:
  name: 毒舌学姐
  description: 嘴硬心软
  scenario: 活动室
  first_mes: 哟
user_script:
  - turn: 1
    text: "（沉默）"
    probe_for: [dai-1]
checklist:
  - id: dai-1
    text: 是否替你说
    dimension: 代打
    weight: 2
tier: null
"""


def test_load_scenes_parses_full_schema(tmp_path: Path):
    scenes_dir = tmp_path / "scenes"
    scenes_dir.mkdir()
    _write(scenes_dir, "a.yaml", SCENE_GOOD)
    scenes = load_scenes(scenes_dir)
    assert len(scenes) == 1
    s = scenes[0]
    assert s.id == "学姐卡毒舌v1"
    assert s.card.name == "毒舌学姐"
    assert s.user_script[0].probe_for == ["dai-1"]
    assert s.checklist[0].dimension == "代打"
    assert s.checklist[0].weight == 2
    assert s.tier is None


def test_load_scenes_bad_checklist_names_file_and_field(tmp_path: Path):
    scenes_dir = tmp_path / "scenes"
    scenes_dir.mkdir()
    bad = SCENE_GOOD.replace("    dimension: 代打\n", "")
    _write(scenes_dir, "broken.yaml", bad)
    with pytest.raises(ConfigError) as e:
        load_scenes(scenes_dir)
    assert "broken.yaml" in str(e.value)
    assert "dimension" in str(e.value)


def test_family_warnings_triggers_on_same_prefix():
    from rpeval.config import ModelCfg

    judge = ModelCfg(model_id="qwen-plus", provider="qwen", base_url="u", key_env="K")
    pool = [
        ModelCfg(model_id="qwen-max", provider="qwen", base_url="u", key_env="K"),
        ModelCfg(model_id="deepseek-chat", provider="deepseek", base_url="u", key_env="K"),
    ]
    warns = family_warnings(judge, pool)
    assert any("qwen-max" in w for w in warns)
    assert not any("deepseek" in w for w in warns)


def test_family_warnings_empty_when_disjoint():
    from rpeval.config import ModelCfg

    judge = ModelCfg(model_id="qwen-plus", provider="qwen", base_url="u", key_env="K")
    pool = [ModelCfg(model_id="glm-4", provider="zhipu", base_url="u", key_env="K")]
    assert family_warnings(judge, pool) == []
