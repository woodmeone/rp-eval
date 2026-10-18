"""I1 — 显示层白话映射（一个事实只住一个家）。

对抗式自检：本文件测的不是"能不能显示白话"，而是**"有没有漏掉任何一个代码值"**。
将来 judge 加第七类反应、ladder_metrics 加新指标，这里的覆盖测试会先红——
而不是等到用户打开界面才发现又冒出一个看不懂的词。
"""
import re

from rpeval.judge import REACTIONS, ladder_metrics
from rpeval.web import labels
from rpeval.web.console import ALERT_REACTIONS

# 界面禁止出现的缩写（I1 验收标准第 1 条）
BANNED = ("OOR", "BUR", "BSR", "rated", "checklist", "verdict", "shell", "payload")


# ---------- 覆盖性：代码值一个都不能漏 ----------

def test_every_reaction_code_has_plain_label():
    missing = [r for r in REACTIONS if labels.reaction_label(r) == r]
    assert missing == [], f"这些反应码没有白话名：{missing}"


def test_every_ladder_metric_has_plain_label():
    """从真函数取 key，不手抄一份——源头加指标时这里先红。"""
    raw = [k for k in ladder_metrics([], []) if labels.metric_label(k) == k]
    assert raw == [], f"这些阶梯指标没有白话名：{raw}"


# ---------- 质量：白话名本身要干净、唯一 ----------

def test_plain_labels_are_distinct():
    seen: dict[str, str] = {}
    for r in REACTIONS:
        lab = labels.reaction_label(r)
        assert lab not in seen, f"白话名重复：{lab}（{seen.get(lab)} 与 {r}）"
        seen[lab] = r


def test_no_plain_label_contains_banned_token():
    values = list(labels.REACTION_LABELS.values()) + list(labels.METRIC_LABELS.values())
    for v in values:
        for b in BANNED:
            assert b not in v, f"白话名里混进了缩写 {b}：{v}"


def test_no_plain_label_is_ascii_english():
    """白话名必须真的是中文，不能把 in-char refuse 换个写法糊弄过去。"""
    values = list(labels.REACTION_LABELS.values()) + list(labels.METRIC_LABELS.values())
    for v in values:
        assert re.search(r"[\u4e00-\u9fff]", v), f"不是中文白话名：{v}"


# ---------- 同源：配色与警报集合不许两边打架 ----------

def test_reaction_tone_matches_documented_alert_set():
    """视觉规范写死：出戏拒绝 / 崩了 / 真给了 = 樱粉警报，其余钢蓝。

    这里故意写死一份期望，而不是去 import 同源集合——否则就是自我印证。
    """
    sakura = {"OOC refuse", "break", "harmful comply"}
    for r in REACTIONS:
        assert labels.reaction_tone(r) == ("sakura" if r in sakura else "steel")
    assert ALERT_REACTIONS == frozenset(sakura)  # console 那边取的也是同一份


# ---------- 降级：未知值要看得见，不能悄悄吞掉 ----------

def test_unknown_reaction_degrades_visibly():
    assert labels.reaction_label(None) == "—"
    assert labels.reaction_label("") == "—"
    # 未知码原样透出（便于发现），而不是伪装成某一个已知白话名
    assert labels.reaction_label("brand-new") == "brand-new"
    assert labels.reaction_tone(None) == "steel"
    assert labels.reaction_tone("brand-new") == "steel"


def test_unknown_metric_degrades_visibly():
    assert labels.metric_label("新指标") == "新指标"
    assert labels.metric_label(None) == ""
