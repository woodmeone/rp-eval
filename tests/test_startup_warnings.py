"""票02 — 启动时终端打印同族警告。"""
import contextlib
import io
from pathlib import Path

from rpeval.cli import _print_startup_warnings

MODELS = """\
judge: {model_id: qwen-plus, provider: qwen, base_url: https://x, key_env: K1}
models:
  - {model_id: qwen-max, provider: qwen, base_url: https://x, key_env: K2}
  - {model_id: glm-4, provider: zhipu, base_url: https://x, key_env: K3}
"""


def test_startup_prints_family_warning(tmp_path: Path):
    (tmp_path / "models.yaml").write_text(MODELS, encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _print_startup_warnings(tmp_path)
    out = buf.getvalue()
    assert "同族" in out
    assert "qwen-max" in out
    assert "glm-4" not in out


def test_startup_silent_without_models_yaml(tmp_path: Path):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _print_startup_warnings(tmp_path)
    assert buf.getvalue() == ""


def test_startup_prints_validation_error(tmp_path: Path):
    (tmp_path / "models.yaml").write_text("judge: [broken", encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _print_startup_warnings(tmp_path)
    assert "校验失败" in buf.getvalue()
