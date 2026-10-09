# 票02 — 题卡/模型 YAML 加载与校验

## 用户故事
作为 UP 主，我改 models.yaml 加一个模型、写一个 scenes/*.yaml 加一道题，工具就能认，不碰代码。

## 端到端验收
- [x] load_models()：provider/base_url/key_env/model_id/采样参数；key_env 缺失时报友好错误
- [x] load_scenes()：card 字段 + user_script + checklist(id/text/dimension/weight) + tier；schema 校验失败指明文件+字段
- [x] 同族校验：judge 模型名与被测池同族（前缀匹配）→ 启动打警告（ADR-0003）
- [x] 首页加"配置摘要"区：列出已加载模型数/题卡数/维度分布（录屏可见配置即数据）
- [x] 单测：坏 YAML 的报错定位、同族警告触发

## 范围外
调用任何 API。

## 真相影响
CONTEXT.md 无新增；PROJECT.md config 模块变现状。
