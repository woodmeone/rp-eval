"""config：models.yaml 与 scenes/*.yaml 的加载与校验（schema 错误指明文件+字段）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """配置校验失败，消息含文件名与出错字段。"""


@dataclass
class ModelCfg:
    model_id: str
    provider: str
    base_url: str
    key_env: str
    label: str = ""
    temperature: float = 0.7
    max_tokens: int = 1024


@dataclass
class ModelsConfig:
    judge: ModelCfg
    models: list[ModelCfg]


@dataclass
class Card:
    name: str
    description: str
    scenario: str
    first_mes: str


@dataclass
class Turn:
    turn: int
    text: str
    probe_for: list[str] = field(default_factory=list)


@dataclass
class ChecklistItem:
    id: str
    text: str
    dimension: str
    weight: int


@dataclass
class Scene:
    id: str
    card: Card
    user_script: list[Turn]
    checklist: list[ChecklistItem]
    tier: str | None = None


def _require(d: Any, key: str, where: str, path: Path) -> Any:
    if not isinstance(d, dict) or key not in d or d[key] is None:
        raise ConfigError(f"{path.name}: {where} 缺字段 '{key}'")
    return d[key]


def _model_from(data: Any, where: str, path: Path) -> ModelCfg:
    kwargs = {
        "model_id": str(_require(data, "model_id", where, path)),
        "provider": str(_require(data, "provider", where, path)),
        "base_url": str(_require(data, "base_url", where, path)),
        "key_env": str(_require(data, "key_env", where, path)),
    }
    for opt in ("label",):
        if isinstance(data, dict) and data.get(opt) is not None:
            kwargs[opt] = str(data[opt])
    for num in ("temperature", "max_tokens"):
        if isinstance(data, dict) and data.get(num) is not None:
            kwargs[num] = float(data[num]) if num == "temperature" else int(data[num])
    return ModelCfg(**kwargs)


def load_models(path: Path) -> ModelsConfig:
    """加载 models.yaml；schema 错误指明文件+字段，key_env 缺失报友好错误。"""
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"{Path(path).name}: YAML 解析失败 — {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{Path(path).name}: 顶层必须是映射")
    judge = _model_from(raw.get("judge"), "judge", Path(path))
    models_raw = raw.get("models")
    if not isinstance(models_raw, list) or not models_raw:
        raise ConfigError(f"{Path(path).name}: 'models' 必须是非空列表")
    pool = [_model_from(m, f"models[{i}]({m.get('model_id', '?')})", Path(path)) for i, m in enumerate(models_raw)]
    return ModelsConfig(judge=judge, models=pool)


def load_scene(path: Path) -> Scene:
    p = Path(path)
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"{p.name}: YAML 解析失败 — {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{p.name}: 顶层必须是映射")
    sid = str(_require(raw, "id", "题卡", p))
    card_raw = _require(raw, "card", f"题卡 {sid}", p)
    card = Card(
        name=str(_require(card_raw, "name", "card", p)),
        description=str(_require(card_raw, "description", "card", p)),
        scenario=str(_require(card_raw, "scenario", "card", p)),
        first_mes=str(_require(card_raw, "first_mes", "card", p)),
    )
    script_raw = _require(raw, "user_script", f"题卡 {sid}", p)
    if not isinstance(script_raw, list) or not script_raw:
        raise ConfigError(f"{p.name}: user_script 必须是非空列表")
    turns: list[Turn] = []
    for i, t in enumerate(script_raw):
        turn_no = int(_require(t, "turn", f"user_script[{i}]", p))
        text = str(_require(t, "text", f"user_script[{i}]", p))
        probe = list(t.get("probe_for") or [])
        turns.append(Turn(turn=turn_no, text=text, probe_for=probe))
    cl_raw = _require(raw, "checklist", f"题卡 {sid}", p)
    if not isinstance(cl_raw, list) or not cl_raw:
        raise ConfigError(f"{p.name}: checklist 必须是非空列表")
    items: list[ChecklistItem] = []
    for i, c in enumerate(cl_raw):
        cid = str(_require(c, "id", f"checklist[{i}]", p))
        items.append(
            ChecklistItem(
                id=cid,
                text=str(_require(c, "text", f"checklist[{i}]({cid})", p)),
                dimension=str(_require(c, "dimension", f"checklist[{i}]({cid})", p)),
                weight=int(_require(c, "weight", f"checklist[{i}]({cid})", p)),
            )
        )
    return Scene(id=sid, card=card, user_script=turns, checklist=items, tier=raw.get("tier"))


def load_scenes(dir_path: Path) -> list[Scene]:
    """加载目录下全部 *.yaml 题卡，按 id 排序。"""
    d = Path(dir_path)
    scenes = [load_scene(f) for f in sorted(d.glob("*.yaml"))]
    return sorted(scenes, key=lambda s: s.id)


def family_warnings(judge: ModelCfg, pool: list[ModelCfg]) -> list[str]:
    """judge 与被测模型同族（model_id 首段前缀相同）→ 返回警告文本（ADR-0003）。"""
    def family(model_id: str) -> str:
        return model_id.split("-")[0].lower()

    jf = family(judge.model_id)
    return [
        f"⚠ judge({judge.model_id}) 与被测模型 {m.model_id} 同族 '{jf}'，判分可能有亲缘偏差"
        for m in pool
        if family(m.model_id) == jf
    ]
