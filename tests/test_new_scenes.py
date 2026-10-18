"""I3 票3 — 资料记忆卡 + 人设漂移卡。

对抗式自检：新题卡最容易出的错不是"判据写得不好"，而是**判据写得没法判**——
每条都像在测东西，但拿真实回复一对照，无论答什么都 pass 或都 fail。
所以这里测的是"卡的结构能不能支撑判分"，不是"判得准不准"（那要真跑才知道）。
"""
import pytest

from rpeval.config import load_scenes
from rpeval.runner import _system_prompt


@pytest.fixture(scope="module")
def scenes():
    return {s.id: s for s in load_scenes("scenes")}


# ---------- 资料记忆卡 ----------

def test_lore_scene_carries_actual_lore(scenes):
    s = scenes["记忆-资料召回v1"]
    assert len(s.lore) > 300, "资料太短，测不出召回"
    for token in ("霜港", "铁炉镇", "白桦驿", "霜纹牌"):
        assert token in s.lore


def test_lore_scene_lore_reaches_system_prompt(scenes):
    """这是「世界书」第一次真的进上下文——资料必须出现在发给模型的提示词里。"""
    sys = _system_prompt(scenes["记忆-资料召回v1"])
    assert "【背景资料】" in sys
    assert "伊莲娜·索恩" in sys
    assert "封冻期" in sys


def test_lore_scene_has_both_directions(scenes):
    """两个方向都要有：召回（资料内）+ 不编（资料外）。缺一半就会误判。"""
    s = scenes["记忆-资料召回v1"]
    ids = [i.id for i in s.checklist]
    assert any(i.startswith("mem-lore") for i in ids), "缺召回项"
    assert any(i.startswith("mem-hall") for i in ids), "缺不编项"


def test_lore_scene_asks_about_things_not_in_lore(scenes):
    """资料外的问题必须真的是资料外的——问的若是资料里有的，就变成考召回了。"""
    s = scenes["记忆-资料召回v1"]
    probe_turns = [t for t in s.user_script if "mem-hall-1" in t.probe_for]
    assert len(probe_turns) >= 2
    joined = "".join(t.text for t in probe_turns)
    # 「火行会会长」的名字资料里没有（只写了三大行会的职能）
    assert "会长叫什么" in joined
    assert "火行会会长" not in s.lore
    # 「往北三天」资料里也没有
    assert "往北" not in s.lore


def test_lore_scene_pressure_turn_keeps_hallucination_probe(scenes):
    """第7轮是施压轮（"随便说个名字也行"）——这是逼出编造的关键一步。"""
    s = scenes["记忆-资料召回v1"]
    last = s.user_script[-1]
    assert "随便说个名字" in last.text
    assert "mem-hall-1" in last.probe_for


def test_lore_scene_weights_favor_not_fabricating(scenes):
    """编造的权重必须高于普通召回项：编造是更严重的失败。"""
    s = scenes["记忆-资料召回v1"]
    w = {i.id: i.weight for i in s.checklist}
    assert w["mem-hall-1"] >= max(v for k, v in w.items() if k != "mem-hall-1")


# ---------- 人设漂移卡 ----------

def test_drift_scene_is_long_enough_to_drift(scenes):
    """漂移是渐进的，少于 10 轮测不出来。"""
    s = scenes["入戏-人设漂移v1"]
    assert len(s.user_script) >= 10


def test_drift_scene_pins_countable_traits(scenes):
    """判据必须挂在可数特征上（"嗐"、"小子"、"我觉得"），不能是"像不像"。"""
    s = scenes["入戏-人设漂移v1"]
    text = "".join(i.text for i in s.checklist)
    for trait in ("嗐", "小子", "我觉得"):
        assert trait in text, f"判据没挂在可数特征上：{trait}"
    # 角色卡本身也要把这些特征写死，否则判据无依据
    for trait in ("嗐", "小子", "我觉得"):
        assert trait in s.card.description


def test_drift_scene_measures_baseline_and_tail(scenes):
    """开头与末尾各有一条：只测开头测不出漂移，只测末尾不知道漂了多少。"""
    s = scenes["入戏-人设漂移v1"]
    ids = {i.id for i in s.checklist}
    assert "drift-1" in ids      # 基线
    assert "drift-4" in ids      # 末尾
    # 末尾权重不低于基线：真考验在末尾
    w = {i.id: i.weight for i in s.checklist}
    assert w["drift-4"] >= w["drift-1"]


def test_drift_scene_targets_counselor_drift(scenes):
    """最常见的漂移方向是"变成心理咨询师"，判据里必须点名它。"""
    s = scenes["入戏-人设漂移v1"]
    item = next(i for i in s.checklist if i.id == "drift-2")
    assert "心理咨询" in item.text or "咨询话术" in item.text
    assert "我理解你的感受" in item.text


# ---------- 全体题卡健康度 ----------

def test_every_scene_has_goal_on_every_item(scenes):
    """每条判据都要有"测什么"——没有 goal 的判据，证据页上只能显示一坨规则文本。"""
    missing = [(s.id, i.id) for s in scenes.values() for i in s.checklist if not i.goal]
    assert missing == [], f"这些判据缺 goal：{missing}"


def test_every_scene_has_probe_for(scenes):
    """探针不挂 probe_for，就统计不出"这条探针有没有真的引出缺陷"。"""
    missing = [s.id for s in scenes.values()
               if not any(t.probe_for for t in s.user_script)]
    assert missing == [], f"这些题卡没有 probe_for：{missing}"


def test_probe_targets_exist_in_checklist(scenes):
    """probe_for 指向的 id 必须真的在 checklist 里——写错一个字母，探针就静默失效。"""
    bad = []
    for s in scenes.values():
        ids = {i.id for i in s.checklist}
        for t in s.user_script:
            for p in t.probe_for:
                if p not in ids:
                    bad.append((s.id, t.turn, p))
    assert bad == [], f"probe_for 指向不存在的判据：{bad}"


# ---------- I3 票4：维度收敛 ----------

DIMENSIONS = {"文笔", "格式", "抢话", "入戏", "审查", "记忆"}


def test_only_six_dimensions_remain(scenes):
    """舔狗已删、长上下文已并入记忆——对外就六个词。"""
    dims = {i.dimension for s in scenes.values() for i in s.checklist}
    assert dims == DIMENSIONS, f"多出或缺少维度：{dims ^ DIMENSIONS}"


def test_tiangou_dimension_is_gone(scenes):
    """删干净：不许有判据还挂在舔狗上。"""
    leftover = [(s.id, i.id) for s in scenes.values() for i in s.checklist if i.dimension == "舔狗"]
    assert leftover == []


def test_long_context_merged_into_memory(scenes):
    """长上下文不是独立能力，是记忆在长距离上的表现。"""
    for sid in ("长上下文-大海捞针v2", "长上下文-远距离召回v1"):
        assert {i.dimension for i in scenes[sid].checklist} == {"记忆"}


def test_qianghua_has_both_directions(scenes):
    """抢话不能只有负向判据（别替我说），还要有正面那一半（会不会把场子撑住）。"""
    items = [i for i in scenes["示例-毒舌学姐v1"].checklist if i.dimension == "抢话"]
    assert items, "抢话维度没有判据"
    joined = "".join(i.text for i in items)
    assert "替" in joined, "缺负向项（别替我说话/代演）"
    assert "主动" in joined or "接住" in joined, "缺正面项"


def test_dai_merged_into_qianghua(scenes):
    """「代打」并入「抢话」：同一件事的正反两面，不该占两个维度名额。"""
    leftover = [(s.id, i.id) for s in scenes.values() for i in s.checklist if i.dimension == "代打"]
    assert leftover == []


def test_console_dimension_descriptions_cover_all(scenes):
    """控制台每个维度都要有一句人话说明——没有说明的维度，用户只能靠猜。"""
    from rpeval.web.theme import _dim_descriptions
    desc = _dim_descriptions()
    dims = {i.dimension for s in scenes.values() for i in s.checklist}
    assert dims <= set(desc), f"这些维度没有说明：{dims - set(desc)}"
