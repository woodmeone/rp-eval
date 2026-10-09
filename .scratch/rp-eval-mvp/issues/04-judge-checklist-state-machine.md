# 票04 — judge：checklist 取证状态机单轮判分

## 用户故事
作为 UP 主，跑完后每题的 checklist 逐条有 pass/fail + 证据轮次 + 引用原文，我能在 JSON 里核对。

## 端到端验收
- [ ] TRACE 状态机：pending→verified/failed，failed 不可逆；逐轮快照
- [ ] judge prompt（中文，qwen，判实质禁正则）：给整段对话+单条 checklist，输出 {verdict, evidence_turn, evidence_quote}
- [ ] n=5 采样多数票（可配置 n），固定采样参数
- [ ] score.json：checklist 逐条结果 + 按 dimension 聚合（0–10 换算规则=权重和，见 ADR-0004）
- [ ] 单测：mock judge 响应验证状态机不可逆、多数票、换算

## 范围外
六类反应（票05）、成对比较（票10）、前端。

## 真相影响
CONTEXT.md 已有术语；PROJECT.md judge 变现状。
