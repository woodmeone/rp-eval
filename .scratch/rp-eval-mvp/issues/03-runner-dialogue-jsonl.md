# 票03 — runner：按脚本喂轮次，落 dialogue.jsonl

## 用户故事
作为 UP 主，选 1 模型×1 题卡点跑，工具按 user_script 逐轮调用模型，每轮留证落盘。

## 端到端验收
- [x] OpenAI 兼容 client 调用（base_url/key/model/采样参数全来自 models.yaml）
- [x] 多轮接龙：模型回复进对话历史，下一轮 user 台词按脚本喂
- [x] dialogue.jsonl：每行一 case，turns 含 user/model_reply/meta(latency/tokens/cost_cny)，append-only
- [x] 断点续跑：同 run_id 重启跳过已完成 case
- [x] 并行：多模型同时跑（asyncio.gather），单 run 串行 case
- [x] 单测：mock OpenAI client 验证轮次拼接与落盘格式

## 范围外
判分、前端。

## 真相影响
PROJECT.md runner 变现状。
