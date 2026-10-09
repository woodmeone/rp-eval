"""像素主题：账号视频同款界面语言（四色+双层网格+扫描线+像素字体）。

render_index() 渲染首页；配置摘要区展示"配置即数据"（模型数/题卡数/维度分布/同族警告）。
"""
from __future__ import annotations

from collections import Counter

from rpeval.config import ModelsConfig, Scene, family_warnings

_STYLE = """\
  :root {
    --ink: #0b0c15;      /* 深黑 */
    --paper: #fbfdfd;    /* 纸白 */
    --sakura: #e8a0bf;   /* 樱粉 = 警报 */
    --steel: #bac2f7;    /* 钢蓝 = 正常 */
    --pixel-font: "Press Start 2P", "Courier New", monospace;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    background: var(--ink);
    color: var(--paper);
    font-family: var(--pixel-font);
    display: grid;
    place-items: center;
    overflow: hidden;
    position: relative;
  }
  /* 双层网格：细格 8px + 粗格 64px */
  body::before {
    content: "";
    position: fixed; inset: 0;
    background:
      repeating-linear-gradient(0deg, rgba(186,194,247,.05) 0 1px, transparent 1px 8px),
      repeating-linear-gradient(90deg, rgba(186,194,247,.05) 0 1px, transparent 1px 8px),
      repeating-linear-gradient(0deg, rgba(186,194,247,.10) 0 1px, transparent 1px 64px),
      repeating-linear-gradient(90deg, rgba(186,194,247,.10) 0 1px, transparent 1px 64px);
    pointer-events: none;
  }
  /* scanline 扫描线 */
  .scanlines {
    position: fixed; inset: 0;
    background: repeating-linear-gradient(0deg, rgba(11,12,21,.35) 0 2px, transparent 2px 4px);
    mix-blend-mode: multiply;
    pointer-events: none;
    z-index: 2;
  }
  .panel {
    position: relative; z-index: 1;
    border: 2px solid var(--steel);
    box-shadow: 0 0 0 4px var(--ink), 0 0 0 6px rgba(186,194,247,.35);
    padding: 40px 56px;
    text-align: center;
    image-rendering: pixelated;
    max-width: 80vw;
  }
  h1 { font-size: 28px; letter-spacing: 4px; color: var(--steel); }
  h1 .accent { color: var(--sakura); }
  .ready { margin-top: 20px; font-size: 14px; color: var(--paper); }
  .ready .dot {
    display: inline-block; width: 10px; height: 10px;
    background: var(--steel); margin-right: 10px;
    animation: blink 1.2s steps(2) infinite;
  }
  .summary { margin-top: 24px; text-align: left; font-size: 11px; line-height: 2; }
  .summary h2 { font-size: 12px; color: var(--steel); margin-bottom: 6px; }
  .summary .warn { color: var(--sakura); }
  .hint { margin-top: 16px; font-size: 10px; color: rgba(251,253,253,.55); }
  @keyframes blink { 50% { background: var(--sakura); } }

  /* ===== 全局导航条（dark-tech：mono 标签 + 状态灯 + active 辉光） ===== */
  .nav-bar {
    position: fixed; top: 0; left: 0; right: 0; z-index: 5;
    display: flex; align-items: center; gap: 4px;
    padding: 0 20px; height: 44px;
    background: rgba(11,12,21,.92);
    border-bottom: 1px solid rgba(186,194,247,.35);
    backdrop-filter: blur(4px);
  }
  .nav-bar .brand { font-size: 11px; color: var(--paper); letter-spacing: 2px; margin-right: 18px; }
  .nav-bar .brand .accent { color: var(--sakura); }
  .nav-bar a {
    font-size: 10px; color: rgba(251,253,253,.6); text-decoration: none;
    padding: 6px 12px; border: 1px solid transparent;
    transition: color .15s steps(3), border-color .15s steps(3), background .15s steps(3);
  }
  .nav-bar a:hover { color: var(--paper); border-color: rgba(186,194,247,.5); }
  .nav-bar a.active {
    color: var(--ink); background: var(--steel);
    box-shadow: 0 0 10px rgba(186,194,247,.45);
  }
  .nav-bar a.warn-link { color: var(--sakura); }
  .nav-bar .lamp { margin-left: auto; font-size: 9px; color: rgba(251,253,253,.5); }
  .nav-bar .lamp .dot { display:inline-block; width:8px; height:8px; background: var(--steel); margin-right:6px; animation: blink 1.2s steps(2) infinite; }

  /* 内容区给导航条让位 */
  body { align-content: start; padding-top: 44px; overflow: auto; }

  /* ===== 微交互（dark-tech：hover 边框变亮 + 入场淡入） ===== */
  .panel { animation: rise .25s steps(6) both; }
  @keyframes rise { from { opacity: 0; transform: translateY(8px); } }
  button, .btn { transition: transform .12s steps(2), box-shadow .12s steps(2), filter .12s steps(2); }
  button:hover, .btn:hover { filter: brightness(1.15); box-shadow: 0 0 12px rgba(186,194,247,.4); }
  button:active, .btn:active { transform: translateY(2px); }
  input, select {
    font-family: var(--pixel-font); background: rgba(20,23,36,.8); color: var(--paper);
    border: 1px solid rgba(186,194,247,.4); padding: 8px 10px; font-size: 10px;
  }
  input:focus, select:focus { outline: none; border-color: var(--steel); box-shadow: 0 0 8px rgba(186,194,247,.4); }
  .card { animation: rise .2s steps(5) both; }
  .btn { display: inline-block; font-family: var(--pixel-font); font-size: 10px; color: var(--ink);
    background: var(--steel); padding: 8px 16px; text-decoration: none; border: none; cursor: pointer; }
  .btn.primary { background: var(--sakura); }
"""


_NAV_ITEMS = [
    ("/", "首页"),
    ("/settings", "设置"),
    ("/console", "控制台"),
    ("/evidence", "证据"),
    ("/leaderboard", "榜单"),
    ("/blind", "盲测"),
]


def render_nav(active: str) -> str:
    """全局导航条 HTML：六页统一入口，当前页高亮（active 辉光）。"""
    links = "".join(
        f"<a href=\"{href}\" class=\"{'active' if href == active else ''}\">{name}</a>"
        for href, name in _NAV_ITEMS)
    return ("<nav class=\"nav-bar\"><span class=\"brand\">RP<span class=\"accent\">·</span>EVAL</span>"
            f"{links}<span class=\"lamp\"><span class=\"dot\"></span>LOCAL</span></nav>")


def render_index(
    models: ModelsConfig | None,
    scenes: list[Scene],
    config_dir_note: str = "",
) -> str:
    parts: list[str] = []
    configured = models is not None and len(scenes) > 0
    if models is None:
        parts.append(f"<div class='warn'>{config_dir_note or '尚未配置模型'}</div>")
    else:
        warns = family_warnings(models.judge, models.models)
        dims = Counter(item.dimension for s in scenes for item in s.checklist)
        dim_text = " / ".join(f"{d} {c}" for d, c in sorted(dims.items())) or "—"
        parts.append(
            f"<div>模型 {len(models.models)} · 题卡 {len(scenes)} · judge {models.judge.model_id}</div>"
            f"<div>维度分布：{dim_text}</div>"
        )
        for w in warns:
            parts.append(f'<div class="warn">{w}</div>')
    summary = "\n".join(parts)

    # 三步引导（空状态=引导入口：每步给明确动作）
    step1 = "<span class='ok'>✓</span> 模型与密钥已配置" if models else "<a class='btn' href='/settings'>去配置 →</a>"
    step2 = "<span class='ok'>✓</span> 已有题卡" if scenes else "<a class='btn' href='/settings#scenes'>添加题卡 →</a>"
    step3 = "<a class='btn primary' href='/console'>开始测评 →</a>" if configured else "<span class='dim'>先完成前两步</span>"
    return f"""\
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>rp-eval · RP 模型横评</title>
<style>
{_STYLE}
  .steps {{ margin-top: 28px; text-align: left; font-size: 11px; }}
  .steps .row {{ display: flex; align-items: center; gap: 14px; margin: 12px 0; }}
  .steps .no {{ color: var(--sakura); font-size: 14px; min-width: 22px; }}
  .steps .desc {{ flex: 1; }}
  .ok {{ color: var(--steel); }}
  .dim {{ color: rgba(251,253,253,.4); }}
</style>
</head>
<body>
{render_nav("/")}
  <div class="panel">
    <h1>RP<span class="accent">·</span>EVAL</h1>
    <div class="ready"><span class="dot"></span>本地横评服务已就绪</div>
    <div class="steps">
      <div class="row"><span class="no">①</span><span class="desc">第一步 · 配置模型与密钥</span>{step1}</div>
      <div class="row"><span class="no">②</span><span class="desc">第二步 · 准备测评题卡</span>{step2}</div>
      <div class="row"><span class="no">③</span><span class="desc">第三步 · 控制台开跑</span>{step3}</div>
    </div>
    <div class="summary"><h2>当前配置</h2>{summary}</div>
  </div>
  <div class="scanlines"></div>
</body>
</html>
"""


_CONSOLE_STYLE = """\
  .console { display: grid; grid-template-columns: 320px 1fr; gap: 24px; width: 92vw; max-width: 1200px; }
  .col-left, .col-right { border: 2px solid var(--steel); background: rgba(11,12,21,.6); padding: 20px; }
  .col-left h2, .col-right h2 { font-size: 13px; color: var(--steel); margin-bottom: 12px; }
  .grp { margin-bottom: 14px; }
  .grp .dim { font-size: 10px; color: var(--sakura); margin-bottom: 6px; }
  label { display: block; font-size: 10px; line-height: 1.9; cursor: pointer; }
  input[type=checkbox] { accent-color: var(--sakura); margin-right: 8px; }
  .cost { font-size: 11px; color: var(--paper); margin: 14px 0; }
  .cost b { color: var(--steel); }
  button#go { width: 100%; font-family: var(--pixel-font); font-size: 13px; padding: 12px;
    background: var(--sakura); color: var(--ink); border: none; cursor: pointer; }
  button#go:disabled { background: rgba(186,194,247,.3); color: rgba(251,253,253,.4); cursor: not-allowed; }
  .bar { height: 10px; border: 1px solid var(--steel); margin-bottom: 16px; }
  .bar > i { display: block; height: 100%; width: 0; background: var(--steel); transition: width .3s steps(10); }
  #stream { max-height: 60vh; overflow-y: auto; }
  .card { border-left: 4px solid var(--steel); padding: 8px 12px; margin-bottom: 8px; font-size: 10px; line-height: 1.8; }
  .card.sakura { border-left-color: var(--sakura); }
  .card .tag { color: var(--steel); }
  .card.sakura .tag { color: var(--sakura); }
  .card .badge { padding: 1px 6px; margin: 0 6px; }
  .card.steel .badge { background: var(--steel); color: var(--ink); }
  .card.sakura .badge { background: var(--sakura); color: var(--ink); }
  .nav a { color: var(--steel); font-size: 10px; margin-right: 16px; text-decoration: none; }
"""


def render_console(models: ModelsConfig | None, scenes: list[Scene]) -> str:
    """控制台页：左列勾模型/题卡（按维度分组）+ 预估成本；右列 SSE 实时流。"""
    if models is None:
        model_boxes = "<div class='cost'>还没有可用模型。<a class='btn' href='/settings'>去设置页配置 →</a></div>"
    else:
        model_boxes = "".join(
            f"<label><input type='checkbox' class='pick-model' value='{m.model_id}'>{m.label or m.model_id}</label>"
            for m in models.models)
    # 题卡按维度分组（一卡可属多维→归到首个 checklist 维度）
    from collections import defaultdict
    groups: dict[str, list[Scene]] = defaultdict(list)
    for s in scenes:
        dim = s.checklist[0].dimension if s.checklist else "其他"
        groups[dim].append(s)
    scene_boxes = "".join(
        f"<div class='grp'><div class='dim'>{dim}</div>"
        + "".join(f"<label><input type='checkbox' class='pick-scene' value='{s.id}'>{s.id}</label>" for s in ss)
        + "</div>"
        for dim, ss in sorted(groups.items()))
    if not scenes:
        scene_boxes = "<div class='cost'>还没有题卡——在项目 <b>scenes/</b> 目录放 YAML 题卡（运行 <b>rp-eval init</b> 生成示例）。</div>"
    return f"""\
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>rp-eval · 控制台</title>
<style>
{_STYLE}
{_CONSOLE_STYLE}
</style>
</head>
<body>
{render_nav("/console")}
  <div class="console">
    <div class="col-left">
      <h2>被测模型</h2>
      <div id="models">{model_boxes}</div>
      <h2 style="margin-top:18px">题卡（按维度）</h2>
      <div id="scenes">{scene_boxes}</div>
      <div class="cost">预估成本：<b id="cost">¥0.00</b>（题数×模型数×均价）</div>
      <button id="go">开始测评</button>
    </div>
    <div class="col-right">
      <h2>实时判定流</h2>
      <div class="bar"><i id="prog"></i></div>
      <div id="stream"></div>
    </div>
  </div>
  <div class="scanlines"></div>
<script>
const ALERT = new Set(["OOC refuse","break","harmful comply"]);
const go = document.getElementById("go");
const stream = document.getElementById("stream");
const prog = document.getElementById("prog");
function picked(sel) {{ return [...document.querySelectorAll(sel+":checked")].map(e=>e.value); }}
function updateCost() {{
  const nm = picked(".pick-model").length, ns = picked(".pick-scene").length;
  document.getElementById("cost").textContent = "¥" + (nm*ns*0.02).toFixed(2);
}}
document.querySelectorAll("input").forEach(e=>e.addEventListener("change", updateCost));
updateCost();
function addCard(c) {{
  const div = document.createElement("div");
  const alert = ALERT.has(c.reaction);
  div.className = "card " + (alert ? "sakura" : "steel");
  div.innerHTML = `<span class="tag">第${{c.turn_no}}轮 · ${{c.model}}</span>`
    + `<span class="badge">${{c.reaction || "—"}}</span>`
    + `<span>${{c.evidence || ""}}</span>`;
  stream.prepend(div);
}}
function addMsg(text, cls) {{
  const div = document.createElement("div");
  div.className = "card " + (cls || "steel");
  div.innerHTML = text;
  stream.prepend(div);
}}
go.addEventListener("click", async () => {{
  const models = picked(".pick-model"), scenes = picked(".pick-scene");
  if (!models.length || !scenes.length) {{ addMsg("请先勾选至少一个模型和一张题卡", "sakura"); return; }}
  go.disabled = true; stream.innerHTML = "";
  const r = await fetch("/api/start", {{method:"POST", headers:{{"content-type":"application/json"}},
    body: JSON.stringify({{models, scenes}})}});
  if (r.status === 409) {{ addMsg("已有 run 在跑，请等待", "sakura"); go.disabled=false; return; }}
  if (!r.ok) {{ const j = await r.json().catch(()=>({{}})); addMsg("启动失败：" + (j.error||r.status), "sakura"); go.disabled=false; return; }}
  addMsg("测评已启动，等待首轮判定…");
  const es = new EventSource("/api/stream");
  es.addEventListener("turn", e => addCard(JSON.parse(e.data)));
  es.addEventListener("progress", e => {{ prog.style.width = (JSON.parse(e.data).p*100)+"%"; }});
  es.addEventListener("error", e => {{ try {{ const j = JSON.parse(e.data); addMsg("运行失败：" + j.message + ' <a class="btn" href="/settings">检查密钥 →</a>', "sakura"); }} catch(err){{}} }});
  es.addEventListener("done", e => {{ es.close(); go.disabled=false; }});
}});
// 重连补看已发生轮次
(async () => {{ try {{ const h = await (await fetch("/api/history")).json(); h.forEach(addCard); }} catch(e){{}} }})();
</script>
</body>
</html>
"""


def render_leaderboard(data: dict) -> str:
    """榜单页：总分排名表（rated=false 标"不予推荐评级"）→ 每维得分条 → 细节锤点 → 图表内嵌 → Elo+胜率矩阵。"""
    import html as _h
    import json
    esc = _h.escape
    rows = []
    for m in data.get("models", []):
        flag = "" if m.get("rated", True) else "<span class='norec'>不予推荐评级</span>"
        bars = "".join(
            f"<div class='dimbar'><span>{esc(d)}</span>"
            f"<i style='width:{v*10}%'></i><b>{v}</b></div>"
            for d, v in sorted(m.get("dimensions", {}).items()))
        hammers = data.get("hammers", {}).get(m["model"], {})
        hammer_html = "".join(
            f"<details><summary>{esc(dim)} 锤点</summary><pre>{esc(json.dumps(hs, ensure_ascii=False))}</pre></details>"
            for dim, hs in hammers.items()) if hammers else ""
        rows.append(
            f"<tr><td>{esc(m['model'])}{flag}</td><td class='tot'>{m['total']}</td>"
            f"<td>{bars}</td><td>{hammer_html}</td></tr>")
    elo = data.get("elo", {})
    ci = data.get("elo_ci", {})
    elo_rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{v}</td><td>[{ci.get(k,['—','—'])[0]}, {ci.get(k,['—','—'])[1]}]</td></tr>"
        for k, v in sorted(elo.items(), key=lambda kv: -kv[1]))
    wr = data.get("win_rate", {})
    models = [m["model"] for m in data.get("models", [])]
    wr_head = "".join(f"<th>{esc(x)}</th>" for x in models)
    wr_rows = "".join(
        "<tr><td>" + esc(i) + "</td>" +
        "".join(f"<td>{wr.get(i, {}).get(j, '—')}</td>" for j in models) + "</tr>"
        for i in models)
    charts = data.get("charts", {})
    chart_imgs = "".join(
        f"<img src='{src}' alt='{esc(name)}'>" for name, src in sorted(charts.items())
        if "landscape" in name)
    has_data = bool(data.get("models"))
    if not has_data:
        main = ("<div class='empty'>还没有测评数据——先跑一轮测评，榜单会自动生成。<br><br>"
                "<a class='btn primary' href='/console'>去控制台开跑 →</a></div>")
    else:
        main = f"""<table><tr><th>模型</th><th>总分/60</th><th>每维 0–10</th><th>细节锤点</th></tr>{''.join(rows)}</table>
<h2 style="color:var(--steel);margin-top:20px">Elo（BT 强度 · 95% CI）</h2>
<table><tr><th>模型</th><th>强度</th><th>CI</th></tr>{elo_rows or '<tr><td colspan=3>无 battle 数据</td></tr>'}</table>
<h2 style="color:var(--steel);margin-top:20px">胜率矩阵（行对列）</h2>
<table><tr><th></th>{wr_head}</tr>{wr_rows}</table>
<h2 style="color:var(--steel);margin-top:20px">图表</h2>{chart_imgs}"""
    return f"""\
<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>rp-eval · 榜单</title>
<style>
{_STYLE}
.lb {{ width:94vw; max-width:1200px; }}
table {{ width:100%; border-collapse:collapse; font-size:10px; }}
th, td {{ border:1px solid rgba(186,194,247,.3); padding:8px; text-align:left; vertical-align:top; }}
.norec {{ color:var(--sakura); margin-left:8px; }}
.dimbar {{ display:flex; align-items:center; gap:6px; margin:2px 0; }}
.dimbar i {{ display:block; height:8px; background:var(--steel); transition: width .6s steps(12); }}
.dimbar b {{ color:var(--paper); }}
.tot {{ color:var(--sakura); font-size:14px; }}
img {{ max-width:48%; border:2px solid var(--steel); margin:8px 0; }}
details pre {{ color:#8a90b8; font-size:9px; }}
.empty {{ text-align:center; padding:60px 20px; font-size:11px; line-height:2.2; color:rgba(251,253,253,.7); }}
</style></head><body>
{render_nav("/leaderboard")}
<div class="lb panel" style="text-align:left">
<h2 style="color:var(--steel)">榜单 · run {esc(str(data.get('run') or '—'))}</h2>
{main}
</div><div class="scanlines"></div></body></html>
"""


def render_blind(scenes: list) -> str:
    """盲测页：选场景 → A/B 并排（只见代号）→ 投票 → 揭名。"""
    import html as _h
    scene_opts = "".join(f"<option value='{_h.escape(s.id)}'>{_h.escape(s.id)}</option>" for s in scenes)
    hint = "" if scenes else "<div class='warn'>还没有题卡，先去控制台跑一轮测评再来回填票数。</div>"
    return f"""\
<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>rp-eval · 盲测</title>
<style>
{_STYLE}
.blind {{ width:90vw; max-width:1000px; }}
.ab {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin:16px 0; }}
.ab .box {{ border:2px solid var(--steel); padding:16px; min-height:120px; font-size:12px; }}
.ab .box h3 {{ color:var(--sakura); margin-bottom:10px; }}
button {{ font-family:var(--pixel-font); font-size:11px; padding:10px 18px; margin:6px;
  background:var(--steel); color:var(--ink); border:none; cursor:pointer; }}
button.sakura {{ background:var(--sakura); }}
#reveal {{ margin-top:16px; color:var(--sakura); font-size:12px; }}
.warn {{ color:var(--sakura); font-size:10px; margin-top:8px; }}
</style></head><body>
{render_nav("/blind")}
<div class="blind panel" style="text-align:left">
<h2 style="color:var(--steel)">盲测 · 投票前只见代号</h2>
{hint}
<select id="scene">{scene_opts}</select>
<button id="load">换一对</button>
<div class="ab"><div class="box"><h3>A</h3><p id="a">—</p></div>
<div class="box"><h3>B</h3><p id="b">—</p></div></div>
<div>
<button data-v="a">A 赢</button><button data-v="b">B 赢</button>
<button data-v="tie" class="sakura">平</button>
幅度 <input id="margin" type="number" value="1" min="1" max="5" style="width:50px">
</div>
<div id="reveal"></div>
</div><div class="scanlines"></div>
<script>
let pid=null;
async function load() {{
  const s=document.getElementById('scene').value;
  const r=await (await fetch('/api/blind/pair?scene='+encodeURIComponent(s))).json();
  if (r.error) {{ document.getElementById('reveal').textContent=r.error; return; }}
  pid=r.pair_id;
  document.getElementById('a').textContent=r.a_text;
  document.getElementById('b').textContent=r.b_text;
  document.getElementById('reveal').textContent='';
}}
document.getElementById('load').addEventListener('click', load);
document.querySelectorAll('button[data-v]').forEach(btn=>btn.addEventListener('click', async()=>{{
  if(!pid) return;
  const r=await (await fetch('/api/blind/vote',{{method:'POST',headers:{{'content-type':'application/json'}},
    body:JSON.stringify({{pair_id:pid,verdict:btn.dataset.v,margin:+document.getElementById('margin').value}})}})).json();
  if (r.names) {{
    document.getElementById('reveal').textContent =
      '揭名 → A: '+r.names.a+' · B: '+r.names.b+'（已记入 battles.jsonl）';
    pid=null;
  }} else document.getElementById('reveal').textContent = r.error||'记票失败';
}}));
</script></body></html>
"""


_SETTINGS_STYLE = """\
  .settings { width: 92vw; max-width: 900px; text-align: left; }
  .settings h1 { font-size: 18px; margin-bottom: 6px; }
  .sec { border: 2px solid var(--steel); background: rgba(11,12,21,.6); padding: 18px 22px; margin: 16px 0; }
  .sec h2 { font-size: 12px; color: var(--steel); margin-bottom: 12px; }
  .sec .sub { font-size: 9px; color: rgba(251,253,253,.5); margin-bottom: 12px; line-height: 1.8; }
  .field { margin: 10px 0; }
  .field label { display: block; font-size: 9px; color: var(--paper); margin-bottom: 4px; }
  .field input, .field select { width: 100%; }
  .field .note { font-size: 8px; color: #8a90b8; margin-top: 3px; }
  .keyrow { display: flex; align-items: center; gap: 10px; }
  .keyrow .status { font-size: 9px; white-space: nowrap; }
  .keyrow .status.ok { color: var(--steel); }
  .keyrow .status.miss { color: var(--sakura); }
  .mrow { border: 1px dashed rgba(186,194,247,.4); padding: 12px; margin: 10px 0; position: relative; }
  .mrow .rm { position: absolute; top: 8px; right: 8px; background: transparent; color: var(--sakura);
    border: 1px solid var(--sakura); font-size: 9px; padding: 3px 8px; cursor: pointer; }
  .actions { margin: 20px 0 8px; display: flex; gap: 12px; align-items: center; }
  #save { font-size: 12px; padding: 12px 28px; background: var(--sakura); color: var(--ink); border: none; cursor: pointer; }
  #save:disabled { opacity: .4; cursor: not-allowed; }
  #toast { font-size: 10px; }
  #toast.ok { color: var(--steel); } #toast.err { color: var(--sakura); }
  a.keylink { color: var(--steel); }
"""


def render_settings(view: dict) -> str:
    """设置页：预置供应商下拉→自动填 base_url→填 key→保存写 models.yaml+.env。

    view 来自 settings.settings_view()（不含明文 key，只含 key_set 布尔）。
    """
    import json

    providers_json = json.dumps(view.get("providers", []), ensure_ascii=False)
    cur_json = json.dumps({"judge": view.get("judge", {}), "models": view.get("models", [])},
                          ensure_ascii=False)
    return f"""\
<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>rp-eval · 设置</title>
<style>
{_STYLE}
{_SETTINGS_STYLE}
</style></head><body>
{render_nav("/settings")}
<div class="settings panel">
  <h1>设<span class="accent">·</span>置</h1>
  <div class="sub">选择模型商 → 填入 API Key → 保存。Key 只存本地 <b>.env</b>（不入库），models.yaml 可安全开源。</div>

  <div class="sec">
    <h2>JUDGE 裁判模型</h2>
    <div class="sub">负责判分。⚠ 不要与被测模型同族（如判分用 qwen，被测也别用 qwen）。</div>
    <div class="field"><label>模型商</label>
      <select id="j-provider" class="prov-sel"></select></div>
    <div class="field"><label>Base URL（OpenAI 兼容端点）</label>
      <input id="j-base" placeholder="https://..."><div class="note">选自定义可手填中转站地址</div></div>
    <div class="field"><label>Model ID</label><input id="j-model" placeholder="deepseek-chat"></div>
    <div class="field"><label>API Key</label>
      <div class="keyrow"><input id="j-key" type="password" placeholder="sk-...">
      <span id="j-key-status" class="status"></span></div>
      <div class="note" id="j-keylink"></div></div>
  </div>

  <div class="sec">
    <h2>被测模型池</h2>
    <div class="sub">参与横评的模型，至少一个。</div>
    <div id="models"></div>
    <button id="add" class="btn" type="button">+ 添加被测模型</button>
  </div>

  <div class="actions">
    <button id="save" type="button">保存配置</button>
    <span id="toast"></span>
  </div>
</div>
<div class="scanlines"></div>
<script>
const PROVIDERS = {providers_json};
const CUR = {cur_json};
const $ = s => document.querySelector(s);
function provById(id) {{ return PROVIDERS.find(p => p.id === id); }}
function fillSelect(sel, cur) {{
  sel.innerHTML = PROVIDERS.map(p => `<option value='${{p.id}}'>${{p.name}}</option>`).join('')
    + "<option value='custom'>自定义 / 中转站</option>";
  if (cur) sel.value = cur;
}}
function onProvChange(baseEl, modelEl, keyLinkEl, pid, keepBase) {{
  const p = provById(pid);
  if (p) {{
    if (!keepBase || !baseEl.value) baseEl.value = p.base_url;
    if (!modelEl.value) modelEl.value = p.default_model_id;
    keyLinkEl.innerHTML = `<a class='keylink' target='_blank' href='${{p.key_url}}'>去 ${{p.name}} 申请 Key →</a>`;
  }} else {{
    keyLinkEl.textContent = '自定义端点：确保是 OpenAI 兼容 /chat/completions';
  }}
}}
function modelRow(m) {{
  m = m || {{}};
  const div = document.createElement('div');
  div.className = 'mrow';
  div.innerHTML = `
    <button class='rm' type='button'>删除</button>
    <div class='field'><label>模型商</label><select class='prov-sel'></select></div>
    <div class='field'><label>Base URL</label><input class='base'></div>
    <div class='field'><label>Model ID</label><input class='mid'></div>
    <div class='field'><label>显示名（可选）</label><input class='label'></div>
    <div class='field'><label>API Key</label><div class='keyrow'>
      <input class='key' type='password' placeholder='sk-...'><span class='status kstat'></span></div>
      <div class='note keylink'></div></div>`;
  $('#models').appendChild(div);
  fillSelect(div.querySelector('.prov-sel'), m.provider || '');
  div.querySelector('.base').value = m.base_url || '';
  div.querySelector('.mid').value = m.model_id || '';
  div.querySelector('.label').value = m.label || '';
  const st = div.querySelector('.kstat');
  if (m.key_set) {{ st.textContent = '✓ 已保存'; st.className = 'status kstat ok'; }}
  else {{ st.textContent = '未设置'; st.className = 'status kstat miss'; }}
  const link = div.querySelector('.keylink');
  onProvChange(div.querySelector('.base'), div.querySelector('.mid'), link,
               div.querySelector('.prov-sel').value, true);
  div.querySelector('.prov-sel').addEventListener('change', e => {{
    const p = provById(e.target.value);
    if (p) {{ div.querySelector('.base').value = p.base_url; div.querySelector('.mid').value = p.default_model_id; }}
    else {{ div.querySelector('.base').value = ''; }}
    onProvChange(div.querySelector('.base'), div.querySelector('.mid'), link, e.target.value, false);
  }});
  div.querySelector('.rm').addEventListener('click', () => div.remove());
}}
// judge 初始化
fillSelect($('#j-provider'), CUR.judge.provider || '');
$('#j-base').value = CUR.judge.base_url || '';
$('#j-model').value = CUR.judge.model_id || '';
const jst = $('#j-key-status');
if (CUR.judge.key_set) {{ jst.textContent = '✓ 已保存'; jst.className = 'status ok'; }}
else {{ jst.textContent = '未设置'; jst.className = 'status miss'; }}
onProvChange($('#j-base'), $('#j-model'), $('#j-keylink'), $('#j-provider').value, true);
$('#j-provider').addEventListener('change', e => {{
  const p = provById(e.target.value);
  if (p) {{ $('#j-base').value = p.base_url; $('#j-model').value = p.default_model_id; }}
  else $('#j-base').value = '';
  onProvChange($('#j-base'), $('#j-model'), $('#j-keylink'), e.target.value, false);
}});
(CUR.models.length ? CUR.models : [null]).forEach(modelRow);
$('#add').addEventListener('click', () => modelRow(null));
$('#save').addEventListener('click', async () => {{
  const models = [...document.querySelectorAll('.mrow')].map(r => ({{
    provider: r.querySelector('.prov-sel').value,
    base_url: r.querySelector('.base').value.trim(),
    model_id: r.querySelector('.mid').value.trim(),
    label: r.querySelector('.label').value.trim(),
    api_key: r.querySelector('.key').value.trim(),
  }}));
  const body = {{
    judge: {{
      provider: $('#j-provider').value,
      base_url: $('#j-base').value.trim(),
      model_id: $('#j-model').value.trim(),
      api_key: $('#j-key').value.trim(),
    }},
    models,
  }};
  const btn = $('#save'); btn.disabled = true;
  const toast = $('#toast'); toast.textContent = '正在保存…'; toast.className = '';
  try {{
    const r = await fetch('/api/settings', {{method:'POST', headers:{{'content-type':'application/json'}},
      body: JSON.stringify(body)}});
    const j = await r.json();
    if (r.ok && j.ok) {{ toast.textContent = '完成！配置已生效。'; toast.className = 'ok'; }}
    else {{ toast.textContent = '没保存成功：' + (j.error || r.status); toast.className = 'err'; }}
  }} catch (e) {{ toast.textContent = '没保存成功：' + e; toast.className = 'err'; }}
  btn.disabled = false;
}});
</script></body></html>
"""
