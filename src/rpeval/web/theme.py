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
"""


def render_index(
    models: ModelsConfig | None,
    scenes: list[Scene],
    config_dir_note: str = "",
) -> str:
    parts: list[str] = []
    if models is None:
        parts.append(f"<div>{config_dir_note or '未找到 models.yaml'}</div>")
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
    return f"""\
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>rp-eval · RP 模型横评</title>
<style>
{_STYLE}
</style>
</head>
<body>
  <div class="panel">
    <h1>RP<span class="accent">·</span>EVAL</h1>
    <div class="ready"><span class="dot"></span>服务已就绪</div>
    <div class="summary"><h2>配置摘要</h2>{summary}</div>
    <div class="hint">像素横评控制台 · 测评模块将逐票上线</div>
  </div>
  <div class="scanlines"></div>
</body>
</html>
"""
