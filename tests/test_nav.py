"""全局导航与可用性测试：六页统一导航条 + active 高亮 + 空状态引导。"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from rpeval.web.theme import render_nav

PAGES = ["/", "/console", "/evidence", "/leaderboard", "/blind", "/settings"]


def test_render_nav_marks_active():
    html = render_nav("/console")
    assert "nav-bar" in html
    assert "active" in html
    # 六个入口全在
    for href in PAGES:
        assert f"href='{href}'" in html or f'href="{href}"' in html


@pytest.fixture()
def client(tmp_path):
    from rpeval.web.app import create_app
    app = create_app(config_dir=tmp_path)
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("path", PAGES)
def test_every_page_has_nav_bar(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert 'class="nav-bar"' in r.text, f"{path} 缺导航条"


def test_index_has_step_guide(client):
    html = client.get("/").text
    assert "第一步" in html and "第二步" in html and "第三步" in html
    # 未配置时首页给出去设置的动作（空状态=引导入口）
    assert "/settings" in html


def test_console_empty_state_links_settings(client):
    html = client.get("/console").text
    assert "/settings" in html
