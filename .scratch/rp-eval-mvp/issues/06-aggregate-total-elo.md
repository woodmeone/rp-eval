# 票06 — 聚合：总分 + Elo + 胜率矩阵

## 用户故事
作为 UP 主，跑完（含手动 battle 记票）后 leaderboard/elo.json 有带 CI 的榜单和胜率矩阵。

## 端到端验收
- [ ] 六维 0–10 + 总分 60 制汇总表（JSON）
- [ ] arena-rank 接入：battles.jsonl → PairDataset → BT ratings + 95% CI + 胜率矩阵
- [ ] battles.jsonl 读写：{a_code,b_code,scene,verdict,margin}，verdict 含 judge 自动产+人工追加两种来源标记
- [ ] judge 成对比较：A/B 与 B/A 双向取平均防位置偏差（EQ-Bench 策略），长度截断防 length bias
- [ ] 单测：mock battles 数据验证 BT 输出形状与双向平均逻辑

## 范围外
图表、前端。

## 真相影响
PROJECT.md aggregate 变现状。
