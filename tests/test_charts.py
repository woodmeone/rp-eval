"""票07 — 雷达图 + 象限图 PNG（matplotlib，像素四色主题，横/竖两套尺寸）。"""
import json
import struct

import pytest

from rpeval.charts import render_run_charts, SIZES


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    w, h = struct.unpack(">II", data[16:24])
    return w, h


SCORE = {
    "cases": [
        {"scene": "s1", "model": "m1", "rated": True, "total": 42.0,
         "dimensions": {
             "文笔": {"score": 8.0, "details": {}},
             "入戏": {"score": 7.0, "details": {}},
             "审查": {"score": 6.0, "details": {"崩档点": "L3", "OOR": 0.2, "BUR": 0.0, "BSR": 1.0}},
             "舔狗": {"score": 5.0, "details": {}},
             "代打": {"score": 9.0, "details": {}},
             "记忆": {"score": 7.0, "details": {}}}},
        {"scene": "s2", "model": "m2", "rated": False, "total": 20.0,
         "dimensions": {
             "文笔": {"score": 4.0, "details": {}},
             "审查": {"score": 2.0, "details": {"崩档点": "L1", "OOR": 0.8, "BUR": 0.5, "BSR": 0.0}},
             "入戏": {"score": 3.0, "details": {}},
             "舔狗": {"score": 6.0, "details": {}},
             "代打": {"score": 2.0, "details": {}},
             "记忆": {"score": 3.0, "details": {}}}},
    ]
}


def _write_score(tmp_path, data=SCORE):
    (tmp_path / "score.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_render_run_charts_outputs_four_pngs(tmp_path):
    run = _write_score(tmp_path)
    paths = render_run_charts(run)
    names = sorted(p.name for p in paths)
    assert len(paths) == 4  # 雷达×2尺寸 + 象限×2尺寸
    assert any("雷达图" in n for n in names) and any("象限图" in n for n in names)
    for p in paths:
        assert p.is_file() and p.parent.name == "charts"


def test_chart_sizes_landscape_and_portrait(tmp_path):
    run = _write_score(tmp_path)
    paths = render_run_charts(run)
    radar = [p for p in paths if "雷达图" in p.name]
    dims = sorted(_png_size(p) for p in radar)
    assert (1920, 1080) in dims
    assert (1080, 1920) in dims
    assert set(SIZES) == {"landscape", "portrait"}


def test_write_score_json_triggers_charts(tmp_path):
    """票07 验收：跑完 score.json 后自动出图（write_score_json 末端触发）。"""
    from rpeval.config import load_scene
    from rpeval.judge import write_score_json

    yaml_text = """\
id: s1
card: {name: 学姐, description: d, scenario: sc, first_mes: hi}
user_script:
  - {turn: 1, text: "x"}
checklist:
  - {id: c1, text: t, dimension: 审查, weight: 1}
tier: L3
"""
    d = tmp_path / "scenes"
    d.mkdir()
    (d / "s1.yaml").write_text(yaml_text, encoding="utf-8")
    scene = load_scene(d / "s1.yaml")
    case = {"scene": "s1", "model": "m1",
            "turns": [{"turn_no": 1, "user": "x", "model_reply": "r",
                       "judge": {"reaction": "in-char comply"}, "meta": {}}]}
    results = [{"id": "c1", "text": "t", "dimension": "审查", "weight": 1,
                "state": "verified", "votes": ["pass"], "evidence_turn": 1, "evidence_quote": "q"}]
    write_score_json(tmp_path / "score.json", [case], {("s1", "m1"): results}, [scene])
    charts = tmp_path / "charts"
    assert charts.is_dir()
    assert len(list(charts.glob("雷达图*.png"))) == 2
    assert len(list(charts.glob("象限图*.png"))) == 2


def test_no_stress_data_quadrant_skips_gracefully(tmp_path):
    """无审查 details（非阶梯 run）：雷达照出，象限不崩。"""
    data = {"cases": [{"scene": "s", "model": "m", "rated": True, "total": 5.0,
                       "dimensions": {"文笔": {"score": 5.0, "details": {}}}}]}
    run = _write_score(tmp_path, data)
    paths = render_run_charts(run)
    assert any("雷达图" in p.name for p in paths)
    assert not any("象限图" in p.name for p in paths)


def test_radar_handles_missing_dimensions(tmp_path):
    """模型缺某维度：按 0 补全，不崩。"""
    data = {"cases": [
        {"scene": "s", "model": "m1", "rated": True, "total": 10.0,
         "dimensions": {"文笔": {"score": 8.0, "details": {}},
                        "审查": {"score": 6.0, "details": {"OOR": 0.1, "BUR": 0.1, "BSR": 1.0}}}},
        {"scene": "s", "model": "m2", "rated": True, "total": 4.0,
         "dimensions": {"文笔": {"score": 4.0, "details": {}}}}]}
    run = _write_score(tmp_path, data)
    paths = render_run_charts(run)
    assert paths and all(p.stat().st_size > 1000 for p in paths)
