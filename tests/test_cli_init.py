"""票01 — rp-eval init：生成 models.yaml / scenes/ 示例模板，幂等不覆盖。"""
from pathlib import Path

from rpeval.cli import init


def test_init_creates_models_and_scene_templates(tmp_path: Path):
    init(target_dir=tmp_path)
    assert (tmp_path / "models.yaml").is_file()
    scenes = list((tmp_path / "scenes").glob("*.yaml"))
    assert scenes, "init 应至少生成一个示例题卡"


def test_init_is_idempotent_and_never_overwrites(tmp_path: Path):
    (tmp_path / "models.yaml").write_text("custom: keep-me\n", encoding="utf-8")
    init(target_dir=tmp_path)
    assert "keep-me" in (tmp_path / "models.yaml").read_text(encoding="utf-8")


def test_init_templates_are_valid_yaml(tmp_path: Path):
    import yaml

    init(target_dir=tmp_path)
    assert yaml.safe_load((tmp_path / "models.yaml").read_text(encoding="utf-8"))
    for scene in (tmp_path / "scenes").glob("*.yaml"):
        assert yaml.safe_load(scene.read_text(encoding="utf-8"))
