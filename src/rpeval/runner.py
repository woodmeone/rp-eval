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


# ---------- I2：外壳（预设）开关 ----------
# 裸壳 = 现状（只有卡面三行 + 收尾指令）；带预设 = 再把题卡的 preset 文本压在最前。
# 两个壳可以在同一 run 里各跑一遍，榜单页给出差值——这是"预设到底值多少分"的可测量版本。
SHELL_RAW = ""
SHELL_PRESET = "preset"
SHELLS = (SHELL_RAW, SHELL_PRESET)


def _system_prompt(scene: Scene, *, shell: str = SHELL_RAW) -> str:
    """装配系统提示词：预设 → 卡面 → 背景资料 → 收尾指令。

    顺序是刻意的：**预设压最前**（它是"怎么说话"的总纲），**资料贴着收尾指令**
    （位置越靠后，模型越不容易把它当背景噪音）。这条顺序写进 CONTEXT.md，见 ADR-0005。

    旧题卡（无 lore / 无 preset）拼出来与改动前**逐字节一致**——这是回归底线：
    加字段不许悄悄改变任何既有 run 的输入。
    """
    parts: list[str] = []
    if shell == SHELL_PRESET and scene.preset:
        parts.append(scene.preset)
    parts.append(
        f"角色：{scene.card.name}\n简介：{scene.card.description}\n场景：{scene.card.scenario}"
    )
    if scene.lore:
        parts.append(f"【背景资料】\n{scene.lore}")
    parts.append("请以角色身份进行 RP 对话。")
    return "\n".join(parts)


async def build_case_async(
    scene: Scene,
    model: ModelCfg,
    client: ChatClient,
    on_turn: Any | None = None,
    *,
    shell: str = SHELL_RAW,
) -> dict[str, Any]:
    """按 user_script 逐轮调用：模型回复进历史，下一轮台词按脚本喂。

    `shell` 决定用哪个外壳（裸壳 / 带预设），并落进 case 以便区分同题两遍的结果。
    """
    import time

    history: list[dict[str, str]] = [
            {"role": "system", "content": _system_prompt(scene, shell=shell)},
            {"role": "assistant", "content": scene.card.first_mes},
        ]
    turns: list[dict[str, Any]] = []
    for step in scene.user_script:
        user_text = _render_turn(step, scene)
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
    return {"scene": scene.id, "model": model.model_id, "shell": shell, "turns": turns}


def _render_turn(step, scene: Scene | None = None) -> str:
    """普通轮=台词原文；长文注入轮=filler×repeat，needle 按 depth 插进第 k 节。

    {payload} 占位：turn.payload 优先，缺省用 scene.payload（钓句载荷私有注入）。"""
    pay = step.payload or (scene.payload if scene is not None else "")
    text = step.text.replace("{payload}", pay)
    ld = step.long_doc
    if ld is None:
        return text
    needle = ld.needle.replace("{payload}", pay)
    parts = [ld.filler] * ld.repeat
    k = max(0, min(ld.repeat, int(ld.repeat * ld.depth)))
    parts.insert(k, needle)
    body = "\n".join(f"（第{i + 1}节）{p}" for i, p in enumerate(parts))
    return text + "\n" + body


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
