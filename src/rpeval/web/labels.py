"""显示层白话映射（I1）。

**一个事实只住一个家**：代码值与数据文件用原 key（`score.json` / `dialogue.jsonl` 契约冻结），
**界面上显示的文字一律从这里取**。四个页面共用一个映射，改一处全同步。

为什么单独立一个模块：界面上的缩写曾经散在 `evidence.py` / `theme.py` / `console.py` / `charts.py`
四处，改一个漏三个。收成一个接口（label / tone）比在四个文件里改字符串深得多——
新增一类反应时，只有这里需要动，且 `tests/test_labels.py` 的覆盖测试会先红。
"""
from __future__ import annotations

from rpeval.judge import REACTIONS

# 视觉规范：樱粉=警报（出戏/崩/真给了），钢蓝=正常。
# 这是图标配色的唯一来源，console 与 evidence 都从这里取，避免两边打架。
ALERT_REACTIONS = frozenset({"OOC refuse", "break", "harmful comply"})

# 六类反应码 → 界面白话名（键是代码值，永不改名）
REACTION_LABELS: dict[str, str] = {
    "in-char comply": "好好配合",
    "in-char refuse": "用角色的话拒绝",
    "soft deflect": "打太极",
    "OOC refuse": "出戏拒绝",
    "break": "崩了",
    "harmful comply": "真给了",
}

# 审查阶梯指标 key → 界面白话名
METRIC_LABELS: dict[str, str] = {
    "崩档点": "第几关开始出戏",
    "破甲等级": "第几关松口",
    "OOR": "该答不答",
    "BUR": "不该答却答",
    "BSR": "底线守没守住",
    "rated": "给不给推荐",
    "reactions": "本轮反应分布",
}

# 取证状态词 → 界面白话名（榜单页细节锤点会直接列出这些键）
STATE_LABELS: dict[str, str] = {
    "verified": "通过",
    "failed": "挂",
    "pending": "待判",
}

# 以比例存储、界面按百分比显示的指标
RATIO_METRICS = frozenset({"OOR", "BUR", "BSR"})

DASH = "—"


def reaction_label(code: str | None) -> str:
    """反应码 → 界面白话名。

    降级策略：空值给破折号；**未知码原样透出**——宁可让人看见一个新词，
    也不要伪装成某个已知白话名而把问题藏起来。
    """
    if not code:
        return DASH
    key = str(code).strip()
    return REACTION_LABELS.get(key, key)


def reaction_tone(code: str | None) -> str:
    """反应码 → 配色类（`sakura` 警报 / `steel` 正常）。未知码按正常处理。"""
    return "sakura" if code in ALERT_REACTIONS else "steel"


def metric_label(key: str | None) -> str:
    """指标 / 状态键 → 界面白话名。未知 key 原样透出。"""
    if not key:
        return ""
    k = str(key)
    return METRIC_LABELS.get(k, STATE_LABELS.get(k, k))


def metric_value(key: str | None, value: object) -> str:
    """指标值 → 界面文字。

    - 比例类指标（该答不答 / 不该答却答 / 底线守没守住）→ 百分比
    - 列表 → 顿号连接
    - 空值 → 破折号
    """
    if value is None:
        return DASH
    if key in RATIO_METRICS and isinstance(value, (int, float)):
        return f"{float(value) * 100:.0f}%"
    if isinstance(value, list):
        return "、".join(str(x) for x in value) if value else DASH
    return str(value)


def reaction_counts_text(counts: object) -> str:
    """反应计数映射 → 白话摘要，如 `好好配合×1、真给了×2`。

    没有这一步，`{"in-char comply": 1}` 会被 `str()` 成原始英文码丢到界面上——
    真数据（runs/）回归时就是这么暴露出来的。
    """
    if not isinstance(counts, dict):
        return str(counts)
    return "、".join(f"{reaction_label(k)}×{v}" for k, v in counts.items()) or DASH


def all_display_values() -> list[str]:
    """本模块产出的全部界面文字（供"界面无缩写"的验收测试取用）。"""
    return (list(REACTION_LABELS.values()) + list(METRIC_LABELS.values())
            + list(STATE_LABELS.values()))


__all__ = [
    "REACTIONS",
    "ALERT_REACTIONS",
    "REACTION_LABELS",
    "METRIC_LABELS",
    "STATE_LABELS",
    "RATIO_METRICS",
    "reaction_label",
    "reaction_tone",
    "metric_label",
    "metric_value",
    "reaction_counts_text",
    "all_display_values",
]
