"""FastAPI 应用工厂。"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from rpeval.web.theme import INDEX_HTML


def create_app() -> FastAPI:
    app = FastAPI(title="rp-eval", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    return app
