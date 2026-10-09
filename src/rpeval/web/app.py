"""FastAPI 应用工厂：首页/控制台渲染 + 配置摘要 + 票08 控制台 run 端点（SSE 实时流）+ 设置页。"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from rpeval.config import ConfigError, load_models, load_scenes
from rpeval.settings import load_dotenv, save_settings, settings_view
from rpeval.web.theme import render_index, render_console, render_settings
from rpeval.web.console import RunManager, build_turn_card, format_sse, print_turn_card


def create_app(config_dir: Path | None = None, client_factory=None) -> FastAPI:
    root = Path(config_dir) if config_dir else Path.cwd()
    load_dotenv(root)  # .env 的 key 注入环境（真实环境变量优先）
    app = FastAPI(title="rp-eval", docs_url=None, redoc_url=None)
    from rpeval.web.leaderboard import BlindStore
    state: dict = {"rm": RunManager(), "blind": BlindStore()}

    def _load():
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
        return models, scenes, note

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        models, scenes, note = _load()
        return render_index(models, scenes, config_dir_note=note)

    @app.get("/console", response_class=HTMLResponse)
    def console() -> str:
        models, scenes, _ = _load()
        return render_console(models, scenes)

    # ---------- 设置页：前端配置模型 URL/Key ----------

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page() -> str:
        return render_settings(settings_view(root))

    @app.get("/api/settings")
    def api_settings_get():
        return settings_view(root)

    @app.post("/api/settings")
    async def api_settings_save(req: Request):
        body = await req.json()
        try:
            save_settings(root, body)
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        load_dotenv(root)  # 新写入的 key 立即生效
        return {"ok": True}

    # ---------- 票10：榜单页 + 盲测 ----------

    @app.get("/api/leaderboard")
    def api_leaderboard(run: str | None = None):
        from rpeval.web.leaderboard import build_leaderboard
        return build_leaderboard(root, run)

    @app.get("/leaderboard", response_class=HTMLResponse)
    def leaderboard_page(run: str | None = None):
        from rpeval.web.leaderboard import build_leaderboard
        from rpeval.web.theme import render_leaderboard
        return render_leaderboard(build_leaderboard(root, run))

    @app.get("/blind", response_class=HTMLResponse)
    def blind_page():
        from rpeval.web.theme import render_blind
        _, scenes, _ = _load()
        return render_blind(scenes)

    @app.get("/api/blind/pair")
    def api_blind_pair(run: str | None = None, scene: str | None = None):
        from rpeval.web.leaderboard import BlindStore
        if "blind" not in state:
            state["blind"] = BlindStore()
        if run is None:
            from rpeval.web.evidence import list_runs
            runs = list_runs(root)
            if not runs:
                return JSONResponse({"error": "无 run"}, status_code=404)
            run = runs[-1]
        pair = state["blind"].make_pair(root / "runs" / run, scene or "")
        if pair is None:
            return JSONResponse({"error": "该场景不足两个模型回复"}, status_code=404)
        return pair

    @app.post("/api/blind/vote")
    async def api_blind_vote(req: Request):
        from rpeval.web.leaderboard import BlindStore
        if "blind" not in state:
            state["blind"] = BlindStore()
        body = await req.json()
        out = state["blind"].vote(body.get("pair_id", ""), body.get("verdict", ""), int(body.get("margin", 0)))
        if out is None:
            return JSONResponse({"error": "pair 不存在或已投"}, status_code=404)
        return out

    # ---------- 票09：证据浏览器 ----------

    @app.get("/api/runs")
    def api_runs():
        from rpeval.web.evidence import list_runs
        return {"runs": list_runs(root)}

    @app.get("/evidence", response_class=HTMLResponse)
    def evidence_index():
        from rpeval.web.evidence import list_runs, render_run_list
        return render_run_list(list_runs(root))

    @app.get("/api/run/{run_id}")
    def api_run_detail(run_id: str):
        from rpeval.web.evidence import run_detail
        _, scenes, _ = _load()
        detail = run_detail(root, run_id, scenes)
        if detail is None:
            return JSONResponse({"error": "run 不存在"}, status_code=404)
        return detail

    @app.get("/view/{run_id}", response_class=HTMLResponse)
    def view_run(run_id: str):
        from rpeval.web.evidence import render_view, run_detail
        _, scenes, _ = _load()
        detail = run_detail(root, run_id, scenes)
        if detail is None:
            return HTMLResponse("<h1>run 不存在</h1>", status_code=404)
        return render_view(detail)

    # ---------- 票08：run 控制 ----------

    @app.get("/api/busy")
    def api_busy():
        return {"busy": state["rm"].is_busy}

    @app.get("/api/history")
    def api_history():
        rm = state["rm"]
        return [d for (t, d) in rm.history if t == "turn"]

    @app.get("/api/stream")
    async def api_stream():
        rm = state["rm"]

        async def gen():
            idx = 0
            while True:
                events = rm.history
                while idx < len(events):
                    etype, data = events[idx]
                    yield format_sse(etype, data)
                    idx += 1
                if rm.done:
                    yield format_sse("done", {"p": rm.progress})
                    break
                yield format_sse("progress", {"p": rm.progress})
                await asyncio.sleep(0.15)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/api/start")
    async def api_start(req: Request):
        body = await req.json()
        models, scenes, _ = _load()
        if models is None:
            return JSONResponse({"error": "models.yaml 不可用"}, status_code=400)
        sel_models = [m for m in models.models if m.model_id in set(body.get("models", []))]
        sel_scenes = [s for s in scenes if s.id in set(body.get("scenes", []))]
        if not sel_models or not sel_scenes:
            return JSONResponse({"error": "勾选的模型/题卡无效"}, status_code=400)
        rm = state["rm"]
        if not rm.acquire():
            return JSONResponse({"error": "已有 run 在跑"}, status_code=409)
        rm.reset()
        rm.set_plan(len(sel_models) * len(sel_scenes))
        run_dir = root / "runs" / time.strftime("%Y%m%d-%H%M%S")
        factory = client_factory or _default_client_factory()
        task = asyncio.create_task(_execute_run(rm, factory, models, sel_models, sel_scenes, run_dir))
        task.add_done_callback(lambda t: rm.release())
        return JSONResponse({"run_dir": str(run_dir)}, status_code=202)

    async def _execute_run(rm, factory, models_cfg, sel_models, sel_scenes, run_dir):
        from rpeval.llm import OpenAICompatClient
        from rpeval.runner import build_case_async, append_case
        from rpeval.judge import LLMJudge, judge_reactions, run_state_machine, write_score_json

        judge = LLMJudge(factory(models_cfg.judge))
        all_cases: list[dict] = []
        case_results: dict[tuple[str, str], list[dict]] = {}
        try:
            for scene in sel_scenes:
                for model in sel_models:
                    client = factory(model)
                    case = await build_case_async(scene, model, client)
                    if scene.tier is not None:
                        await judge_reactions(scene, case, judge)
                    # 每完成一轮推一张卡片（审查档含反应，普通档 reaction=None 钢蓝）
                    for t in case["turns"]:
                        card = build_turn_card(model.model_id, t)
                        rm.publish("turn", card)
                        print_turn_card(card)
                    append_case(run_dir, case)
                    all_cases.append(case)
                    case_results[(scene.id, model.model_id)] = await run_state_machine(scene, case, judge)
                    rm.mark_case_done()
            write_score_json(Path(run_dir) / "score.json", all_cases, case_results, sel_scenes)
        except Exception as e:  # noqa: BLE001 — run 失败要落事件并释放锁
            rm.publish("error", {"message": str(e)})
        finally:
            rm.mark_done()

    return app


def _default_client_factory():
    from rpeval.llm import OpenAICompatClient

    return lambda cfg: OpenAICompatClient(cfg)