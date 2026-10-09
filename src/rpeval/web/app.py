"""FastAPI 应用工厂：首页渲染像素主题 + 配置摘要。"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from rpeval.config import ConfigError, load_models, load_scenes
from rpeval.web.theme import render_index


def create_app(config_dir: Path | None = None) -> FastAPI:
    root = Path(config_dir) if config_dir else Path.cwd()
    app = FastAPI(title="rp-eval", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        models = None
        note = ""
        models_path = root / "models.yaml"
        if models_path.is_file():
            try:
                models = load_models(models_path)
            except ConfigError as e:
                note = f"models.yaml 校验失败：{e}"
        else:
            note = "未找到 models.yaml（运行 rp-eval init 生成模板）"
        scenes: list = []
        scenes_dir = root / "scenes"
        if scenes_dir.is_dir():
            try:
                scenes = load_scenes(scenes_dir)
            except ConfigError as e:
                note = (note + "；" if note else "") + f"题卡校验失败：{e}"
        return render_index(models, scenes, config_dir_note=note)

    return app
