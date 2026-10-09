"""票03 — runner：按 user_script 逐轮喂模型，落 dialogue.jsonl，断点续跑，多模型并发。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from rpeval.config import ModelCfg, Scene


class ChatClient(Protocol):
    """OpenAI 兼容的最小接口：给历史，回文本+用量。"""

    async def chat(self, history: list[dict[str, str]]) -> tuple[str, dict[str, Any]]:
        ...


async def build_case_async(
    scene: Scene,
    model: ModelCfg,
    client: ChatClient,
    on_turn: Any | None = None,
) -> dict[str, Any]:
    """按 user_script 逐轮调用：模型回复进历史，下一轮台词按脚本喂。"""
    import time

    history: list[dict[str, str]] = [
            {"role": "system", "content": _system_prompt(scene)},
            {"role": "assistant", "content": scene.card.first_mes},
        ]
    turns: list[dict[str, Any]] = []
    for step in scene.user_script:
        user_text = step.text
        history.append({"role": "user", "content": user_text})
        t0 = time.monotonic()
        reply, usage = await client.chat(history)
        latency_ms = round((time.monotonic() - t0) * 1000)
        history.append({"role": "assistant", "content": reply})
        record = {
            "turn_no": step.turn,
            "user": user_text,
            "model_reply": reply,
            "judge": None,  # 票04 填充
            "meta": {
                "latency_ms": latency_ms,
                "tokens": {
                    "prompt": usage.get("prompt_tokens", 0),
                    "completion": usage.get("completion_tokens", 0),
                },
                "cost_cny": _cost(model, usage),
            },
        }
        turns.append(record)
        if on_turn is not None:
            on_turn(record)
    return {"scene": scene.id, "model": model.model_id, "turns": turns}


def _system_prompt(scene: Scene) -> str:
    return (
        f"角色：{scene.card.name}\n简介：{scene.card.description}\n"
        f"场景：{scene.card.scenario}\n请以角色身份进行 RP 对话。"
    )


def _cost(model: ModelCfg, usage: dict[str, Any]) -> float:
    pin = usage.get("prompt_tokens", 0) or 0
    pout = usage.get("completion_tokens", 0) or 0
    return round(pin / 1000 * model.price_per_1k_in + pout / 1000 * model.price_per_1k_out, 6)


def case_key(case: dict[str, Any]) -> tuple[str, str]:
    return (case["scene"], case["model"])


def load_done_cases(run_dir: Path) -> set[tuple[str, str]]:
    """断点续跑：读已有 dialogue.jsonl，返回已完成 (scene, model) 集合。"""
    done: set[tuple[str, str]] = set()
    f = Path(run_dir) / "dialogue.jsonl"
    if not f.is_file():
        return done
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            done.add(case_key(json.loads(line)))
        except (json.JSONDecodeError, KeyError):
            continue  # 半行损坏（上次崩溃残留）忽略，重跑该 case
    return done


def append_case(run_dir: Path, case: dict[str, Any]) -> None:
    """append-only 落盘。"""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "dialogue.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(case, ensure_ascii=False) + "\n")


async def run(
    scene: Scene,
    models: list[ModelCfg],
    client_factory: Any,
    run_dir: Path,
    on_turn: Any | None = None,
) -> list[dict[str, Any]]:
    """多模型并发（asyncio.gather），单模型内 case 串行；跳过已完成 case。"""
    import asyncio

    done = load_done_cases(Path(run_dir))
    todo = [m for m in models if (scene.id, m.model_id) not in done]

    async def one(m: ModelCfg) -> dict[str, Any]:
        case = await build_case_async(scene, m, client_factory(m), on_turn)
        append_case(Path(run_dir), case)
        return case

    return list(await asyncio.gather(*(one(m) for m in todo)))
