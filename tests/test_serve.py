"""票01 — serve：真实起 uvicorn（空闲端口）→ 取到可访问 URL → 开浏览器。"""
import httpx

from rpeval.cli import start_server, wait_url


def test_server_binds_free_port_and_serves_index(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))

    server, thread, url = start_server()
    try:
        assert wait_url(url) == url
        r = httpx.get(url + "/", timeout=5)
        assert r.status_code == 200
        assert "服务已就绪" in r.text
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_wait_url_raises_timeout_on_dead_url():
    import pytest

    with pytest.raises(TimeoutError):
        wait_url("http://127.0.0.1:1", timeout=0.3)
