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


def test_load_models_parses_price_fields(tmp_path: Path):
    """回归：price_per_1k_in/out 必须被解析（否则成本读数恒为0）。"""
    priced = VALID_MODELS.replace(
        "    label: DeepSeek\n",
        "    label: DeepSeek\n    price_per_1k_in: 0.001\n    price_per_1k_out: 0.002\n")
    cfg = load_models(_write(tmp_path, "models.yaml", priced))
    assert cfg.models[0].price_per_1k_in == 0.001
    assert cfg.models[0].price_per_1k_out == 0.002
    assert cfg.models[1].price_per_1k_in == 0.0  # 未配置默认0


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


def test_load_scenes_includes_subdirectories(tmp_path: Path):
    """scenes/stress/ 等子目录题卡也要加载（审查阶梯存放处）。"""
    scenes_dir = tmp_path / "scenes"
    (scenes_dir / "stress").mkdir(parents=True)
    _write(scenes_dir, "a.yaml", SCENE_GOOD)
    tiered = SCENE_GOOD.replace("id: 学姐卡毒舌v1", "id: 审查-L0").replace("tier: null", "tier: L0")
    _write(scenes_dir / "stress", "l0.yaml", tiered)
    scenes = load_scenes(scenes_dir)
    assert {s.id for s in scenes} == {"学姐卡毒舌v1", "审查-L0"}
    by_id = {s.id: s for s in scenes}
    assert by_id["审查-L0"].tier == "L0"


SCENE_CHECK = """\
id: 格式-校验v1
card:
  name: 助手
  description: 按格式输出
  scenario: 整理
  first_mes: 好
user_script:
  - turn: 1
    text: "输出JSON"
  - turn: 2
    text: "长文档"
    long_doc:
      filler: "例会纪要若干。"
      repeat: 10
      needle: "团建密码是 蓝鲸7749。"
      depth: 0.5
checklist:
  - id: c1
    text: JSON可解析
    dimension: 格式
    weight: 2
    check: "json@1"
  - id: c2
    text: 召回针
    dimension: 长上下文
    weight: 2
    check: "regex@2:match:7749"
tier: null
"""


def test_load_scene_parses_check_and_long_doc(tmp_path: Path):
    d = tmp_path / "scenes"
    d.mkdir()
    p = _write(d, "f.yaml", SCENE_CHECK)
    from rpeval.config import load_scene
    s = load_scene(p)
    assert s.checklist[0].check.kind == "json" and s.checklist[0].check.turn == 1
    assert s.checklist[1].check.kind == "regex" and s.checklist[1].check.mode == "match"
    ld = s.user_script[1].long_doc
    assert ld is not None and ld.repeat == 10 and ld.depth == 0.5
    assert s.user_script[0].long_doc is None


@pytest.mark.parametrize("spec,field", [
    ("json", "缺 @轮次"),
    ("xml@1", "类型未知"),
    ("json@x", "轮次"),
    ("len@1", "缺参数"),
    ("len@1:abc", "字数"),
    ("regex@1:bad:pat", "模式须为"),
    ("regex@1:match:[unclosed", "无法编译"),
])
def test_parse_check_errors(tmp_path, spec, field):
    from rpeval.config import parse_check
    with pytest.raises(ConfigError) as e:
        parse_check(spec, Path("x.yaml"), "checklist[0](c1)")
    assert field in str(e.value)


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
