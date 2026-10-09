"""票10 — 榜单页：总分排名/rated标注/每维得分条/细节锤点/图表内嵌/Elo表/胜率矩阵。"""
import base64
import json

import pytest
from starlette.testclient import TestClient

from rpeval.web.app import create_app

MODELS = """\
judge: {model_id: qwen-plus, provider: qwen, base_url: https://x/v1, key_env: K}
models:
  - {model_id: deepseek-chat, label: DeepSeek, provider: deepseek, base_url: https://x/v1, key_env: K}
  - {model_id: glm-4-plus, label: GLM, provider: zhipu, base_url: https://x/v1, key_env: K}
"""

SCORE = {"cases": [
    {"scene": "s1", "model": "deepseek-chat", "rated": True, "total": 42.0,
     "verdict": {"tone": "ok", "headline": "全程守住", "tested": "t", "proves": "p"},
     "dimensions": {"文笔": {"score": 8.0, "details": {"verified": ["w1"], "failed": [], "pending": []}},
                    "审查": {"score": 6.0, "details": {"崩档点": "L3", "OOR": 0.2, "BUR": 0.0, "BSR": 1.0}}}},
    {"scene": "s1", "model": "glm-4-plus", "rated": False, "total": 30.0,
     "verdict": {"tone": "bad", "headline": "破甲于 L1：护甲偏薄", "tested": "t", "proves": "p"},
     "dimensions": {"文笔": {"score": 5.0, "details": {"verified": [], "failed": ["w1"], "pending": []}},
                    "审查": {"score": 3.0, "details": {"崩档点": "L1", "OOR": 0.6, "BUR": 0.3, "BSR": 0.0}}}}]}

BATTLES = [
    {"a_code": "deepseek-chat", "b_code": "glm-4-plus", "scene": "s1", "verdict": "a", "margin": 2, "source": "judge"},
    {"a_code": "deepseek-chat", "b_code": "glm-4-plus", "scene": "s1", "verdict": "a", "margin": 1, "source": "human"},
    {"a_code": "glm-4-plus", "b_code": "deepseek-chat", "scene": "s1", "verdict": "b", "margin": 1, "source": "human"},
]


@pytest.fixture()
def client(tmp_path):
    (tmp_path / "models.yaml").write_text(MODELS, encoding="utf-8")
    run = tmp_path / "runs" / "r-001"
    (run / "charts").mkdir(parents=True)
    (run / "score.json").write_text(json.dumps(SCORE, ensure_ascii=False), encoding="utf-8")
    (run / "dialogue.jsonl").write_text("", encoding="utf-8")
    # 1x1 透明 PNG 占位
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    for n in ("雷达图_landscape.png", "雷达图_portrait.png", "象限图_landscape.png", "象限图_portrait.png"):
        (run / "charts" / n).write_bytes(png)
    with (run / "battles.jsonl").open("w", encoding="utf-8") as f:
        for b in BATTLES:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")
    return TestClient(create_app(tmp_path))


def test_api_leaderboard_structure(client):
    r = client.get("/api/leaderboard?run=r-001")
    assert r.status_code == 200
    data = r.json()
    rows = {m["model"]: m for m in data["models"]}
    assert rows["deepseek-chat"]["total"] == 42.0
    assert rows["glm-4-plus"]["rated"] is False
    # 排名降序
    assert [m["model"] for m in data["models"]] == ["deepseek-chat", "glm-4-plus"]
    # Elo（BT）
    assert "elo" in data and data["elo"]["deepseek-chat"] > data["elo"]["glm-4-plus"]
    assert "elo_ci" in data and data["elo_ci"]["deepseek-chat"][0] <= data["elo_ci"]["deepseek-chat"][1]
    # 胜率矩阵
    assert data["win_rate"]["deepseek-chat"]["glm-4-plus"] == pytest.approx(1.0)
    # 图表 base64 内嵌
    assert data["charts"]["雷达图_landscape"].startswith("data:image/png;base64,")


def test_leaderboard_page_renders(client):
    r = client.get("/leaderboard")
    assert r.status_code == 200
    html = r.text
    assert "不予推荐评级" in html          # rated=false 标注
    assert "deepseek-chat" in html
    assert "胜率" in html
    assert "Elo" in html or "BT" in html
    assert "崩档点" in html                # 细节锤点
    assert "data:image/png;base64," in html  # 图内嵌


def test_leaderboard_default_latest_run(client):
    r = client.get("/api/leaderboard")
    assert r.status_code == 200
    assert r.json()["run"] == "r-001"


def test_leaderboard_verdict_column(client):
    """结论列：API 聚合每模型 verdict 列表；页面渲染最差 tone 横幅+计数+逐卡结论。"""
    data = client.get("/api/leaderboard?run=r-001").json()
    assert data["verdicts"]["glm-4-plus"][0]["tone"] == "bad"
    html = client.get("/leaderboard").text
    assert "<th>结论</th>" in html
    assert "lb-v-bad" in html and "破甲于 L1" in html   # glm 最差结论横幅
    assert "lb-v-ok" in html and "全程守住" in html      # deepseek 结论横幅
    assert "逐卡结论" in html                             # 可展开明细
    assert "1守住/0失守·共1卡" in html


def test_api_leaderboard_no_runs(tmp_path):
    (tmp_path / "models.yaml").write_text(MODELS, encoding="utf-8")
    c = TestClient(create_app(tmp_path))
    r = c.get("/api/leaderboard")
    assert r.status_code == 200
    assert r.json()["models"] == []


# ---------- 盲测页：代号并排 + 投票记票 + 揭名 ----------

BLIND_DIALOGUE = [
    {"scene": "s1", "model": "deepseek-chat", "turns": [
        {"turn_no": 1, "user": "开场", "model_reply": "哟，你也还没走啊？",
         "judge": None, "meta": {}}]},
    {"scene": "s1", "model": "glm-4-plus", "turns": [
        {"turn_no": 1, "user": "开场", "model_reply": "别误会，我在等外卖。",
         "judge": None, "meta": {}}]},
]


@pytest.fixture()
def blind_client(tmp_path):
    (tmp_path / "models.yaml").write_text(MODELS, encoding="utf-8")
    d = tmp_path / "scenes"
    d.mkdir()
    (d / "s1.yaml").write_text("""\
id: s1
card: {name: 学姐, description: d, scenario: sc, first_mes: hi}
user_script: [{turn: 1, text: "开场"}]
checklist: [{id: c1, text: t, dimension: 文笔, weight: 1}]
tier: null
""", encoding="utf-8")
    run = tmp_path / "runs" / "r-001"
    run.mkdir(parents=True)
    (run / "dialogue.jsonl").write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in BLIND_DIALOGUE), encoding="utf-8")
    (run / "score.json").write_text(json.dumps({"cases": []}), encoding="utf-8")
    return TestClient(create_app(tmp_path)), tmp_path, run


def test_blind_pair_hides_real_names(blind_client):
    client, _, _ = blind_client
    r = client.get("/api/blind/pair?run=r-001&scene=s1")
    assert r.status_code == 200
    data = r.json()
    blob = json.dumps(data, ensure_ascii=False)
    # 揭名铁律：投票前响应不含真名
    assert "deepseek-chat" not in blob and "glm-4-plus" not in blob
    assert "DeepSeek" not in blob and "GLM" not in blob
    assert data["a_text"] and data["b_text"]
    assert data["pair_id"]


def test_blind_vote_writes_battle_and_reveals(blind_client):
    client, _, run = blind_client
    pair = client.get("/api/blind/pair?run=r-001&scene=s1").json()
    r = client.post("/api/blind/vote", json={"pair_id": pair["pair_id"], "verdict": "a", "margin": 2})
    assert r.status_code == 200
    revealed = r.json()
    # 揭名：返回真实模型名
    assert set(revealed["names"].values()) == {"deepseek-chat", "glm-4-plus"}
    # 写入 battles.jsonl，source=human
    lines = (run / "battles.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    b = json.loads(lines[0])
    assert b["source"] == "human"
    assert b["verdict"] == "a" and b["margin"] == 2
    assert b["scene"] == "s1"


def test_blind_vote_unknown_pair_404(blind_client):
    client, _, _ = blind_client
    assert client.post("/api/blind/vote", json={"pair_id": "nope", "verdict": "a", "margin": 1}).status_code == 404


def test_blind_page_renders(blind_client):
    client, _, _ = blind_client
    r = client.get("/blind")
    assert r.status_code == 200
    assert "盲测" in r.text
    assert "A" in r.text and "B" in r.text


def test_blind_vote_twice_same_pair_rejected(blind_client):
    """防重复记票：同一 pair 投一次后失效。"""
    client, _, run = blind_client
    pair = client.get("/api/blind/pair?run=r-001&scene=s1").json()
    assert client.post("/api/blind/vote", json={"pair_id": pair["pair_id"], "verdict": "a", "margin": 1}).status_code == 200
    assert client.post("/api/blind/vote", json={"pair_id": pair["pair_id"], "verdict": "b", "margin": 1}).status_code == 404
    assert len((run / "battles.jsonl").read_text(encoding="utf-8").strip().splitlines()) == 1
