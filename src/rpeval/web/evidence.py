"""票09 — 证据浏览器：读 dialogue.jsonl + score.json 合并为视图 JSON，渲染逐轮取证页。"""
from __future__ import annotations

import html as _html
import json
from pathlib import Path
from typing import Any

from rpeval.config import Scene


def list_runs(root: Path) -> list[str]:
    d = Path(root) / "runs"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir() and (p / "dialogue.jsonl").is_file())


def run_detail(root: Path, run_id: str, scenes: list[Scene]) -> dict[str, Any] | None:
    """合并 dialogue.jsonl（逐轮）+ score.json（总分/checklist/tier/崩档点）。"""
    run_dir = Path(root) / "runs" / run_id
    dj, sj = run_dir / "dialogue.jsonl", run_dir / "score.json"
    if not dj.is_file():
        return None
    cases = []
    for line in dj.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    score_by = {}
    if sj.is_file():
        for c in json.loads(sj.read_text(encoding="utf-8")).get("cases", []):
            score_by[(c["scene"], c["model"])] = c
    tier_of = {s.id: s.tier for s in scenes}
    out = []
    for c in cases:
        sc = score_by.get((c["scene"], c["model"]), {})
        dims = sc.get("dimensions", {})
        stress = dims.get("审查", {}).get("details", {})
        out.append({
            "scene": c["scene"],
            "model": c["model"],
            "total": sc.get("total"),
            "rated": sc.get("rated", True),
            "verdict": sc.get("verdict"),
            "tier": tier_of.get(c["scene"]),
            "collapse": stress.get("崩档点"),
            "jb_level": stress.get("破甲等级"),
            "turns": c.get("turns", []),
            "checklist": sc.get("checklist", {}),
            "dimensions": dims,
        })
    return {"run_id": run_id, "cases": out}


def render_run_list(runs: list[str]) -> str:
    """run 列表页：控制台导航入口，链接到各 run 的证据视图。"""
    from rpeval.web.theme import _STYLE, render_nav

    if not runs:
        body = "<div class='hint'>还没有 run——去控制台勾模型/题卡开跑</div><a class='btn' href='/console'>去控制台 →</a>"
    else:
        body = "".join(
            f"<div class='grp'><a href='/view/{r}' style='color:var(--steel);font-size:12px'>{r}</a></div>"
            for r in runs)
    return f"""\
<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>rp-eval · 证据浏览器</title>
<style>
{_STYLE}
.panel {{ max-width: 60vw; text-align: left; }}
.grp {{ margin: 10px 0; }}
.hint {{ font-size: 10px; color: rgba(251,253,253,.55); margin-bottom: 16px; }}
</style></head>
<body>
{render_nav("/evidence")}
  <div class="panel">
    <h1>EVIDENCE<span class="accent">·</span>RUNS</h1>
    {body}
  </div>
  <div class="scanlines"></div>
</body></html>
"""


_BADGE_CLASS = {  # 六类反应 → 配色类（樱粉=警报，钢蓝=正常）
    "in-char comply": "steel", "in-char refuse": "steel", "soft deflect": "steel",
    "OOC refuse": "sakura", "break": "sakura", "harmful comply": "sakura",
}


def render_view(detail: dict[str, Any]) -> str:
    """纯前端渲染：左列 case 列表（总分角标），右列逐轮对话 + 徽章 + 证据高亮 + checklist 时间线。"""
    from rpeval.web.theme import _STYLE, _CONSOLE_STYLE, render_nav  # 复用像素主题

    esc = _html.escape
    cases = detail.get("cases", [])
    # 左列按场景分组：组头 = 场景名 + 模型数 + 破甲/失守计数
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for i, c in enumerate(cases):
        groups.setdefault(c["scene"], []).append((i, c))
    nav_parts = []
    for scene, items in groups.items():
        n_bad = sum(1 for _, c in items if (c.get("verdict") or {}).get("tone") == "bad")
        head = (f"<div class='scene-h'>{esc(scene)}<span class='scene-n'>{len(items)}模型"
                + (f"·<b class='scene-bad'>破甲{n_bad}</b>" if n_bad else "") + "</span></div>")
        rows = "".join(
            f"<div class='case-item{' active' if i == 0 else ''}' data-i='{i}' "
            f"data-tone='{(c.get('verdict') or {}).get('tone','mid')}'>"
            f"<span>{esc(c['model'])}</span>"
            f"<span class='score'>{c['total'] if c['total'] is not None else '—'}</span>"
            f"<span class='v-dot {(c.get('verdict') or {}).get('tone','mid')}'></span></div>"
            for i, c in items)
        nav_parts.append(f"<div class='scene-grp'>{head}{rows}</div>")
    nav_items = "".join(nav_parts)
    tone_counts = {"ok": 0, "mid": 0, "bad": 0}
    for c in cases:
        tone_counts[(c.get("verdict") or {}).get("tone", "mid")] += 1
    case_filter = (
        "<div class='vfilter'>"
        f"<button class='vf active' data-f='all'>全部 {len(cases)}</button>"
        f"<button class='vf vf-ok' data-f='ok'>守住 {tone_counts['ok']}</button>"
        f"<button class='vf vf-mid' data-f='mid'>部分 {tone_counts['mid']}</button>"
        f"<button class='vf vf-bad' data-f='bad'>破甲/失守 {tone_counts['bad']}</button>"
        "</div>")

    def dims_block(c: dict[str, Any]) -> str:
        """维度得分面板：每个维度测了什么、得几分（0-10）、几条过/几条挂。"""
        dims = c.get("dimensions") or {}
        if not dims:
            return ""
        rows = []
        for name, dv in sorted(dims.items(), key=lambda kv: -kv[1].get("score", 0)):
            det = dv.get("details", {})
            if isinstance(det, dict) and "OOR" in det:  # 审查阶梯：展示阶梯指标
                def _p(v):
                    return "—" if v is None else f"{v * 100:.0f}%"
                jb = "" if det.get("破甲等级") is None else f" · 破甲于{det['破甲等级']}"
                extra = (f"<span class='dm-cnt'>出戏 {_p(det.get('OOR'))} · "
                         f"破防 {_p(det.get('BUR'))} · 底线 {_p(det.get('BSR'))}{jb}</span>")
            elif isinstance(det, dict) and "verified" in det:
                n_ok, n_bad = len(det.get("verified", [])), len(det.get("failed", []))
                extra = f"<span class='dm-cnt'>{n_ok}✓ {n_bad}✗</span>"
            else:
                extra = ""
            score = dv.get("score", 0)
            pct = max(0.0, min(100.0, score / 10 * 100))
            cls = "ok" if score >= 7 else ("mid" if score >= 4 else "bad")
            rows.append(
                f"<div class='dm'><span class='dm-n'>{esc(name)}</span>"
                f"<span class='dm-bar'><i class='{cls}' style='width:{pct:.0f}%'></i></span>"
                f"<span class='dm-s {cls}'>{score}</span>{extra}</div>")
        total = c.get("total")
        rated = "" if c.get("rated", True) else "<span class='dm-rated'>✗ 红线未守住·不给推荐</span>"
        return (f"<div class='dims'><div class='dims-h'>维度得分"
                f"<span class='dims-t'>总分 {total if total is not None else '—'} / {len(dims)*10}</span>{rated}</div>"
                f"{''.join(rows)}</div>")

    def verdict_block(c: dict[str, Any]) -> str:
        """高亮结论横幅：一句话判定（tone 配色）+ 测了什么 + 证明了什么。"""
        v = c.get("verdict")
        if not v:
            return ""
        tone = v.get("tone", "mid")
        return (f"<div class='verdict v-{tone}'>"
                f"<div class='v-head'>{esc(str(v.get('headline','')))}</div>"
                f"<div class='v-row'><span class='v-tag'>测了什么</span>{esc(str(v.get('tested','')))}</div>"
                f"<div class='v-row'><span class='v-tag'>证明了什么</span>{esc(str(v.get('proves','')))}</div>"
                f"</div>")

    def turn_block(c: dict[str, Any]) -> str:
        parts = [verdict_block(c), dims_block(c)]
        if c.get("tier"):
            col = f" · 崩档点 {esc(str(c['collapse']))}" if c.get("collapse") else ""
            jb = f" · 破甲于 {esc(str(c['jb_level']))}" if c.get("jb_level") else ""
            parts.append(f"<div class='tier-tag'>压力档 {esc(c['tier'])}{col}{jb}</div>")
        for t in c["turns"]:
            j = t.get("judge") or {}
            r = j.get("reaction")
            badge = ""
            if r:
                badge = f"<span class='badge {_BADGE_CLASS.get(r, 'steel')}'>{esc(r)}</span>"
            quote = j.get("reaction_evidence") or j.get("evidence_quote") or ""
            hl = f"<span class='hl'>{esc(str(quote))}</span>" if quote else ""
            reply = str(t.get("model_reply", ""))
            long_cls = " long" if len(reply) > 220 else ""
            parts.append(
                f"<div class='turn'><div class='u'>用户：{esc(str(t.get('user','')))}</div>"
                f"<div class='m'>模型：<span class='rpl{long_cls}'>{esc(reply)}</span>{badge}{hl}</div></div>")
        if c.get("checklist"):
            parts.append("<div class='cl'><h3>checklist 取证 · 测了什么 → 证明了什么"
                         "<label class='cl-only'><input type='checkbox' class='cl-toggle'> 只看问题项</label></h3>")
            for cid, item in c["checklist"].items():
                st = item.get("state")
                mark = {"verified": "✓", "failed": "✗", "pending": "…"}.get(st, "…")
                goal = item.get("goal") or item.get("text") or ""
                quote = str(item.get("evidence_quote", ""))
                et = item.get("evidence_turn")
                proves = (f"<span class='cl-turn'>第{et}轮</span>"
                          f"<i class='cl-quote'>{esc(quote[:160])}</i>" if quote else "<i class='cl-quote'>—</i>")
                parts.append(
                    f"<div class='cl-row {st}'>"
                    f"<div class='cl-top'><b>{esc(cid)}</b> {mark} "
                    f"[{esc(item.get('dimension',''))} w{item.get('weight','')}]</div>"
                    f"<div class='cl-what'><span class='cl-tag'>测</span>{esc(goal)}</div>"
                    f"<div class='cl-what'><span class='cl-tag'>证</span>{proves}</div>"
                    f"</div>")
            parts.append("</div>")
        return "".join(parts)

    panes = "".join(f"<div class='pane' data-i='{i}'{' style=\"display:none\"' if i else ''}>{turn_block(c)}</div>"
                    for i, c in enumerate(cases))

    return f"""\
<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>rp-eval · 证据浏览器 {esc(detail.get('run_id',''))}</title>
<style>
{_STYLE}
{_CONSOLE_STYLE}
.case {{ display:grid; grid-template-columns:300px 1fr; gap:20px; width:94vw; }}
.case-item {{ padding:8px; border-left:3px solid var(--steel); margin-bottom:6px; cursor:pointer; font-size:10px; }}
.case-item.active {{ background:rgba(186,194,247,.12); border-left-color:var(--sakura); }}
.case-item .score {{ float:right; color:var(--sakura); }}
.turn {{ margin-bottom:12px; font-size:11px; line-height:1.9; }}
.turn .u {{ color:#8a90b8; }}
.badge {{ margin-left:8px; padding:1px 6px; font-size:9px; }}
.badge.steel {{ background:var(--steel); color:var(--ink); }}
.badge.sakura {{ background:var(--sakura); color:var(--ink); }}
.hl {{ background:rgba(232,160,191,.25); padding:0 4px; margin-left:8px; }}
.tier-tag {{ color:var(--sakura); font-size:10px; margin-bottom:8px; }}
.cl {{ margin-top:14px; }} .cl h3 {{ font-size:11px; color:var(--steel); margin-bottom:6px; }}
.cl-row {{ font-size:10px; line-height:1.7; margin-bottom:8px; padding:6px 8px; border-left:3px solid #5a5f7a; background:rgba(251,253,253,.03); }}
.cl-row.verified {{ border-left-color:var(--steel); }} .cl-row.failed {{ border-left-color:var(--sakura); }} .cl-row.pending {{ opacity:.55; }}
.cl-top b {{ color:var(--paper); }} .cl-top {{ font-size:10px; }}
.cl-what {{ margin-top:2px; }} .cl-tag {{ display:inline-block; width:16px; text-align:center; margin-right:6px; font-size:9px; color:var(--ink); background:var(--steel); }}
.cl-what .cl-tag + * {{ color:rgba(251,253,253,.8); }}
.cl-turn {{ color:var(--steel); margin-right:6px; }} .cl-quote {{ color:rgba(251,253,253,.65); }}
.verdict {{ border:2px solid var(--steel); padding:10px 12px; margin-bottom:12px; background:rgba(186,194,247,.07); }}
.verdict.v-ok {{ border-color:var(--steel); background:rgba(186,194,247,.10); }}
.verdict.v-mid {{ border-color:#e8c46f; background:rgba(232,196,111,.08); }}
.verdict.v-bad {{ border-color:var(--sakura); background:rgba(232,160,191,.10); }}
.v-head {{ font-size:13px; letter-spacing:1px; margin-bottom:6px; color:var(--paper); }}
.verdict.v-bad .v-head {{ color:var(--sakura); }} .verdict.v-ok .v-head {{ color:var(--steel); }} .verdict.v-mid .v-head {{ color:#e8c46f; }}
.v-row {{ font-size:10px; line-height:1.8; color:rgba(251,253,253,.75); }}
.v-tag {{ display:inline-block; width:56px; text-align:center; margin-right:8px; font-size:9px; color:var(--ink); background:var(--steel); }}
.v-dot {{ display:inline-block; width:8px; height:8px; margin-left:6px; background:#e8c46f; }}
.v-dot.ok {{ background:var(--steel); }} .v-dot.bad {{ background:var(--sakura); }}
.dims {{ border:2px solid var(--steel); padding:10px 12px; margin-bottom:14px; background:rgba(186,194,247,.06); }}
.dims-h {{ font-size:11px; color:var(--steel); letter-spacing:2px; margin-bottom:8px; }}
.dims-t {{ margin-left:12px; color:var(--paper); }}
.dm-rated {{ margin-left:12px; color:var(--sakura); }}
.dm {{ display:flex; align-items:center; gap:8px; font-size:10px; margin:4px 0; }}
.dm-n {{ width:64px; color:var(--paper); flex:none; }}
.dm-bar {{ flex:1; height:8px; background:rgba(251,253,253,.08); position:relative; }}
.dm-bar i {{ position:absolute; left:0; top:0; bottom:0; display:block; }}
.dm-bar i.ok {{ background:var(--steel); }} .dm-bar i.mid {{ background:#e8c46f; }} .dm-bar i.bad {{ background:var(--sakura); }}
.dm-s {{ width:34px; text-align:right; flex:none; }}
.dm-s.ok {{ color:var(--steel); }} .dm-s.mid {{ color:#e8c46f; }} .dm-s.bad {{ color:var(--sakura); }}
.dm-cnt {{ color:rgba(251,253,253,.55); flex:none; }}
.vfilter {{ display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px; }}
.vf {{ font-size:9px; padding:3px 8px; border:2px solid #5a5f7a; background:transparent; color:rgba(251,253,253,.6); cursor:pointer; font-family:inherit; }}
.vf.active {{ border-color:var(--steel); color:var(--ink); background:var(--steel); }}
.vf.vf-ok.active {{ border-color:var(--steel); background:var(--steel); }}
.vf.vf-mid.active {{ border-color:#e8c46f; background:#e8c46f; }}
.vf.vf-bad.active {{ border-color:var(--sakura); background:var(--sakura); }}
.rpl.long {{ display:inline-block; max-height:4.2em; overflow:hidden; cursor:pointer; vertical-align:bottom; position:relative; }}
.rpl.long.expanded {{ max-height:none; }}
.cl-only {{ float:right; font-size:9px; font-weight:normal; color:rgba(251,253,253,.55); cursor:pointer; }}
.cl-only input {{ vertical-align:middle; margin-right:2px; }}
.scene-grp {{ margin-bottom:10px; }}
.scene-h {{ font-size:10px; color:var(--steel); letter-spacing:1px; padding:4px 0 4px 8px; border-bottom:1px dashed rgba(186,194,247,.35); margin-bottom:4px; }}
.scene-n {{ float:right; color:rgba(251,253,253,.45); font-size:9px; }}
.scene-bad {{ color:var(--sakura); }}
.case-item {{ padding-left:14px; }}
</style></head>
<body>{render_nav("/evidence")}<div class="case">
  <div>
    <h2 style="font-size:12px;color:var(--paper);margin:10px 0">证据浏览器 · {esc(detail.get('run_id',''))}</h2>
    {case_filter}
    {nav_items}</div>
  <div>{panes}</div>
</div><div class="scanlines"></div>
<script>
document.querySelectorAll('.case-item').forEach(el=>el.addEventListener('click',()=>{{
  document.querySelectorAll('.case-item').forEach(x=>x.classList.remove('active'));
  el.classList.add('active');
  const i=el.dataset.i;
  document.querySelectorAll('.pane').forEach(p=>p.style.display = p.dataset.i===i?'block':'none');
}}));
// 结论筛选：按 tone 隐藏左列 case，并把可见的第一个 pane 切出来
function applyFilter(f){{
  let firstVisible=null;
  document.querySelectorAll('.case-item').forEach(el=>{{
    const show = (f==='all') || el.dataset.tone===f;
    el.style.display = show?'':'none';
    if(show && firstVisible===null) firstVisible=el.dataset.i;
  }});
  // 组内无可见 case 时连组头一起隐藏
  document.querySelectorAll('.scene-grp').forEach(g=>{{
    const any=[...g.querySelectorAll('.case-item')].some(el=>el.style.display!=='none');
    g.style.display = any?'':'none';
  }});
  document.querySelectorAll('.pane').forEach(p=>p.style.display='none');
  if(firstVisible!==null){{
    document.querySelectorAll('.case-item').forEach(x=>x.classList.remove('active'));
    const el=document.querySelector(".case-item[data-i='"+firstVisible+"']");
    if(el) el.classList.add('active');
    const pane=document.querySelector(".pane[data-i='"+firstVisible+"']");
    if(pane) pane.style.display='block';
  }}
}}
document.querySelectorAll('.vf').forEach(b=>b.addEventListener('click',()=>{{
  document.querySelectorAll('.vf').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  applyFilter(b.dataset.f);
}}));
// 长回复折叠：点击 .rpl.long 展开/收起
document.querySelectorAll('.turn .rpl.long').forEach(el=>{{
  el.title='点击展开/收起';
  el.addEventListener('click',()=>el.classList.toggle('expanded'));
}});
// checklist 只看问题项：勾选后隐藏 verified 行
document.querySelectorAll('.cl-toggle').forEach(cb=>cb.addEventListener('change',()=>{{
  const cl=cb.closest('.cl');
  cl.querySelectorAll('.cl-row').forEach(r=>{{
    r.style.display = (cb.checked && r.classList.contains('verified'))?'none':'';
  }});
}}));
</script></body></html>
"""
