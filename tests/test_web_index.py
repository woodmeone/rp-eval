"""票01 — FastAPI 首页：像素主题渲染 + 服务就绪。"""
from fastapi.testclient import TestClient

from rpeval.web.app import create_app


def client():
    return TestClient(create_app())


def test_index_returns_pixel_theme_html():
    r = client().get("/")
    assert r.status_code == 200
    html = r.text
    # 四色变量
    for token in ("#0b0c15", "#fbfdfd", "#e8a0bf", "#bac2f7"):
        assert token in html
    # 双层网格 + 扫描线 + 像素字体
    assert "grid" in html.lower()
    assert "scanline" in html.lower()
    assert "pixel" in html.lower()


def test_index_shows_service_ready():
    html = client().get("/").text
    assert "服务已就绪" in html
