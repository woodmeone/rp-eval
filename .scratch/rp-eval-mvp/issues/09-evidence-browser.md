# 票09 — 证据浏览器页

## 用户故事
作为 UP 主/观众视角，我点开任一 run，逐轮看到模型回复旁挂着 judge 六类标签、证据原文高亮、checklist 状态时间线——"测评过程清晰"的静态证明。

## 端到端验收
- [x] 路由 /view/<run_id>：左列 case 列表（模型×场景，含总分角标），右列逐轮对话流
- [x] 轮次卡片：user 台词 / 模型回复 / judge 徽章（六类配色）/ evidence_quote 樱粉底高亮
- [x] checklist 时间线：每条目一行点带 pending→verified/failed，failed 红叉不可逆视觉
- [x] 审查 case：tier 标签（L0–L6）+ 崩档点行内标注
- [x] 纯前端渲染读 dialogue.jsonl/score.json（API 提供 JSON），无数据库
- [x] 单测：API 端点返回结构

## 范围外
盲测页、榜单页。

## 真相影响
PROJECT.md web 变现状。
