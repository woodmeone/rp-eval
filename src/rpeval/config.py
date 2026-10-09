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
    price_per_1k_in: float = 0.0
    price_per_1k_out: float = 0.0


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
class LongDoc:
    """长文注入（NIAH 式大海捞针）：filler 重复 repeat 节，needle 插在 depth 深度处。"""

    filler: str
    repeat: int
    needle: str
    depth: float = 0.5


@dataclass
class Check:
    """程序化校验（格式类确定性判分，不走 LLM）：
    kind ∈ regex/json/html/len；turn=目标轮次；
    regex 模式 mode ∈ match/not/count（count 配 n）；len 配 n（汉字数）。"""

    kind: str
    turn: int
    mode: str = "match"
    n: int = 0
    pattern: str = ""


def parse_check(spec: str, path: Path, where: str) -> Check:
    """校验 check 语法：json@2 / html@3 / len@2:15 / regex@1:count=3:pat / regex@2:not:pat / regex@1:match:pat。"""
    import re

    parts = spec.split("@", 1)
    if len(parts) != 2:
        raise ConfigError(f"{path.name}: {where} check 语法错（缺 @轮次）：{spec!r}")
    kind, rest = parts[0], parts[1]
    if kind not in ("regex", "json", "html", "len"):
        raise ConfigError(f"{path.name}: {where} check 类型未知 '{kind}'（可用 regex/json/html/len）")
    seg = rest.split(":", 1)
    try:
        turn = int(seg[0])
    except ValueError:
        raise ConfigError(f"{path.name}: {where} check 轮次不是整数：{rest!r}") from None
    if turn < 1:
        raise ConfigError(f"{path.name}: {where} check 轮次须 ≥1：{turn}")
    if kind in ("json", "html"):
        return Check(kind=kind, turn=turn)
    if len(seg) < 2:
        raise ConfigError(f"{path.name}: {where} check {kind} 缺参数：{spec!r}")
    tail = seg[1]
    if kind == "len":
        try:
            return Check(kind="len", turn=turn, n=int(tail))
        except ValueError:
            raise ConfigError(f"{path.name}: {where} check len 字数不是整数：{tail!r}") from None
    # regex：mode[:pattern]
    if tail.startswith("count="):
        head, _, pat = tail.partition(":")
        try:
            n = int(head.split("=", 1)[1])
        except ValueError:
            raise ConfigError(f"{path.name}: {where} check count 数不是整数：{head!r}") from None
    elif tail.startswith("not:") or tail.startswith("match:"):
        n, pat = 0, tail.split(":", 1)[1]
    else:
        raise ConfigError(f"{path.name}: {where} check regex 模式须为 match:/not:/count=N：{spec!r}")
    try:
        re.compile(pat)
    except re.error as e:
        raise ConfigError(f"{path.name}: {where} check 正则无法编译：{pat!r} — {e}") from e
    mode = "count" if tail.startswith("count=") else ("not" if tail.startswith("not:") else "match")
    return Check(kind="regex", turn=turn, mode=mode, n=n, pattern=pat)


@dataclass
class Turn:
    turn: int
    text: str
    probe_for: list[str] = field(default_factory=list)
    long_doc: LongDoc | None = None


@dataclass
class ChecklistItem:
    id: str
    text: str
    dimension: str
    weight: int
    check: Check | None = None


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
    for price in ("price_per_1k_in", "price_per_1k_out"):
        if isinstance(data, dict) and data.get(price) is not None:
            kwargs[price] = float(data[price])
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
        ld_raw = t.get("long_doc")
        long_doc = None
        if ld_raw is not None:
            ld_where = f"user_script[{i}](turn {turn_no}).long_doc"
            ld = {
                "filler": str(_require(ld_raw, "filler", ld_where, p)),
                "repeat": int(_require(ld_raw, "repeat", ld_where, p)),
                "needle": str(_require(ld_raw, "needle", ld_where, p)),
            }
            if ld["repeat"] < 1:
                raise ConfigError(f"{p.name}: {ld_where} repeat 须 ≥1")
            if ld_raw.get("depth") is not None:
                ld["depth"] = float(ld_raw["depth"])
            if not 0.0 <= ld.get("depth", 0.5) <= 1.0:
                raise ConfigError(f"{p.name}: {ld_where} depth 须在 0-1")
            long_doc = LongDoc(**ld)
        turns.append(Turn(turn=turn_no, text=text, probe_for=probe, long_doc=long_doc))
    cl_raw = _require(raw, "checklist", f"题卡 {sid}", p)
    if not isinstance(cl_raw, list) or not cl_raw:
        raise ConfigError(f"{p.name}: checklist 必须是非空列表")
    items: list[ChecklistItem] = []
    for i, c in enumerate(cl_raw):
        cid = str(_require(c, "id", f"checklist[{i}]", p))
        where = f"checklist[{i}]({cid})"
        spec = c.get("check")
        items.append(
            ChecklistItem(
                id=cid,
                text=str(_require(c, "text", where, p)),
                dimension=str(_require(c, "dimension", where, p)),
                weight=int(_require(c, "weight", where, p)),
                check=parse_check(str(spec), p, where) if spec is not None else None,
            )
        )
    return Scene(id=sid, card=card, user_script=turns, checklist=items, tier=raw.get("tier"))


def load_scenes(dir_path: Path) -> list[Scene]:
    """加载目录下（含子目录，如 scenes/stress/）全部 *.yaml 题卡，按 id 排序。"""
    d = Path(dir_path)
    scenes = [load_scene(f) for f in sorted(d.rglob("*.yaml"))]
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
