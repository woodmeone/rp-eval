"""票01 — 终端彩色打印 listening on。"""
import io
import contextlib

from rpeval.cli import _print_listening


def test_print_listening_shows_url_with_color():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _print_listening("http://127.0.0.1:54321")
    out = buf.getvalue()
    assert "listening on" in out
    assert "http://127.0.0.1:54321" in out
    assert "\033[" in out  # ANSI 彩色
