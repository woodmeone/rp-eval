"""I3 票2 — 格式卡 v3（卡格式遵从）：程序化判定必须真能分辨。

对抗式自检：一张格式卡最怕的不是"判错"，是**判不出**——
每项永远 pass（或永远 fail），看起来有九条检查项，实际一条也没在测。
所以这里用一对"全守 / 全崩"的合成回复做双向验证，再逐项验证定位能力。
"""
import pytest

from rpeval.config import load_scene
from rpeval.judge import run_checks

SCENE = "scenes/gezong-卡格式遵从v3.yaml"

GOOD = """<maintext>她抬眼看了你一下，把茶杯往前推了推。</maintext>
<状态栏>
日期：2026-10-18
时间：夜里九点
地点：茶室
好感：42
状态：平静
</状态栏>
<变量更新>
[{"op":"replace","path":"/好感","value":42}]
</变量更新>
<选项>问她为什么</选项>
<选项>沉默喝茶</选项>
<选项>起身告辞</选项>"""

BAD = "随便写两句。没有标签，没有状态栏。"

HTML_OK = "<div class='card'><h1>茶</h1><p>a</p><p>b</p><p>c</p></div>"
HTML_BAD = "<div class='card'><h1>茶</h1><p>a<p>b</p></div>"


@pytest.fixture(scope="module")
def scene():
    return load_scene(SCENE)


def _case(scene, reply, *, drop_turn=None, html=None):
    turns = []
    for i in range(1, 7):
        r = reply
        if drop_turn == i:
            r = BAD
        elif html and i == 4:
            r = html
        turns.append({"turn_no": i, "model_reply": r})
    return {"scene": scene.id, "model": "m", "turns": turns}


def test_scene_loads_with_programmatic_checks_only(scene):
    """全项都带 check：格式维度必须零 LLM 成本。"""
    assert scene.tier is None
    assert all(item.check is not None for item in scene.checklist)
    assert {item.dimension for item in scene.checklist} == {"格式"}


def test_all_good_verifies_every_item(scene):
    """全守时九项全过——防止"某项永远 fail"这种假检查。"""
    states = {k: v["state"] for k, v in run_checks(scene, _case(scene, GOOD, html=HTML_OK)).items()}
    failed = [k for k, v in states.items() if v != "verified"]
    assert failed == [], f"全守仍有项失败：{failed}"


def test_all_bad_fails_every_structural_item(scene):
    """全崩时结构项全挂——防止"某项永远 pass"。"""
    states = {k: v["state"] for k, v in run_checks(scene, _case(scene, BAD, html=HTML_BAD)).items()}
    verified = [k for k, v in states.items() if v == "verified"]
    assert verified == [], f"全崩仍有项通过：{verified}"


def test_maintext_pair_counted(scene):
    """一对标签 = 2 个匹配（开+闭）。多写一对就该挂。"""
    two_pairs = GOOD.replace("<状态栏>", "</maintext><maintext>某段。</maintext>\n<状态栏>")
    r = run_checks(scene, _case(scene, two_pairs, html=HTML_OK))
    assert r["fmt-1"]["state"] == "failed"


def test_status_fields_must_be_complete(scene):
    missing = GOOD.replace("好感：42\n", "")
    r = run_checks(scene, _case(scene, missing, html=HTML_OK))
    assert r["fmt-2"]["state"] == "failed"


def test_options_must_be_three(scene):
    two = GOOD.replace("<选项>起身告辞</选项>", "")
    r = run_checks(scene, _case(scene, two, html=HTML_OK))
    assert r["fmt-4"]["state"] == "failed"


def test_html_balance_checked_on_turn_4(scene):
    r_ok = run_checks(scene, _case(scene, GOOD, html=HTML_OK))
    r_bad = run_checks(scene, _case(scene, GOOD, html=HTML_BAD))
    assert r_ok["fmt-6"]["state"] == "verified"
    assert r_bad["fmt-6"]["state"] == "failed"


@pytest.mark.parametrize("turn,item", [(2, "fmt-5a"), (3, "fmt-5b"), (5, "fmt-5c"), (6, "fmt-5d")])
def test_drift_is_located_per_turn(scene, turn, item):
    """哪一轮开始掉格式要能定位——只看末轮会把中途崩掉漏掉。"""
    r = run_checks(scene, _case(scene, GOOD, drop_turn=turn, html=HTML_OK))
    assert r[item]["state"] == "failed"
    others = [k for k in ("fmt-5a", "fmt-5b", "fmt-5c", "fmt-5d") if k != item]
    assert all(r[k]["state"] == "verified" for k in others), "不该牵连其它轮"


def test_variable_block_needs_json_patch_shape(scene):
    no_patch = GOOD.replace('[{"op":"replace","path":"/好感","value":42}]', "[不是 JSON]")
    r = run_checks(scene, _case(scene, no_patch, html=HTML_OK))
    assert r["fmt-3"]["state"] == "failed"


def test_v2_scene_still_loads(scene):
    """旧格式卡保留不删（历史 run 还要能渲染）。"""
    v2 = load_scene("scenes/gezong-格式遵从v1.yaml")
    assert v2.id == "格式-硬约束v2"
    assert len(v2.checklist) == 11
