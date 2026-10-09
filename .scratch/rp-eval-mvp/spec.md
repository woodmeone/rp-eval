# SPEC — rp-eval MVP（EP1 成片范围）

> 状态：待用户过目 ｜ 2026-10-09 ｜ 决策依据：grilling 访谈记录（本文件"已定决策"节）+ ADR-0001~0004
> 上游设计：账号目录 videos/2026-10-08_model-eval-research/测评工具设计方案.md（架构沿用，形态按 ADR-0001 修订）

## 用户故事

作为 UP 主，我输入一条命令打开像素风测评界面，勾选模型和题卡点"开始"，
看着 judge 逐轮实时判定（录屏即素材），跑完自动出雷达图和象限图，
榜单页展示总分/每维得分/细节锤点，全程不改一行代码、不做后期剪辑加工。

## 已定决策（grilling 账本）

1. 形态：FastAPI + 自写像素风 HTML/JS + SSE；CLI 仅 `rp-eval`（起服务开浏览器）与 `rp-eval init`（生成配置模板）。
2. 页面：①控制台 ②证据浏览器 ③榜单页 进 MVP；④盲测=静态代号并排页+手动记票（无投票后端）。
3. 评分：每项 0–10 + 原始细节双轨，总分累加满分 60；Elo 并存不换算。
4. 图表：每次 run 自动出 雷达图.png + 象限图.png（matplotlib，像素四色），页面内嵌+文件可拖进剪辑。
5. judge：qwen 系便宜档；被测池 DeepSeek/Kimi/豆包/GLM/Claude。
6. 砍掉：素材导出、Playwright 截图、解说卡片、崩档曲线图、表格图、动态 agentic user、观众实时投票、CharacterJudge。
7. 位置/仓库：`d:\桌面\总\项目\rp-eval` 独立 git；scenes/stress/ 与 runs/ 永不入库。

## 数据契约

### 题卡 scenes/<id>.yaml

```yaml
id:学姐卡毒舌v1
card:            # ST V2 字段子集
  name: 毒舌学姐
  description: ...
  scenario: ...
  first_mes: ...
user_script:
  - turn: 1
    text: "（沉默）"
    probe_for: [dai-1]
checklist:
  - id: dai-1
    text: 模型是否替"你"说话
    dimension: 代打
    weight: 2          # 0-10 换算=通过项权重和/总权重和*10
tier: null             # 审查题卡填 L0..L6
```

### dialogue.jsonl（TRACE 格式，每行一 case）

```json
{"scene":"...","model":"deepseek","turns":[
  {"turn_no":1,"user":"...","model_reply":"...","judge":{"reaction":"in-char comply","evidence_turn":1,"evidence_quote":"...","todo_states":{"dai-1":"failed"}},
   "meta":{"latency_ms":812,"tokens":{...},"cost_cny":0.003}}]}
```

### score.json

```json
{"dimensions":{"文笔":{"score":7.5,"details":{"黑名单词命中":2,"翻译腔":1}},"审查":{"score":6,"details":{"崩档点":"L3","OOR":0.25,"BUR":0.0,"BSR":1.0}}},
 "total":42.5,"rated":true}
```

## 页面规格

- **控制台**：左侧勾模型/题卡（题卡按维度分组）→"开始测评"→主区 SSE 流：每轮一行卡片`[轮次|模型代号|六类反应徽章|证据摘要]`，樱粉徽章=警报，钢蓝=正常；顶部进度条；终端同步彩色打印。
- **证据浏览器**：选 run → 左列 case 列表（模型×场景），右列逐轮对话流；judge 徽章挂轮次旁，证据原文高亮（樱粉底），checklist 状态时间线（pending→verified/failed，failed 不可逆标红）。
- **榜单页**：总分排名表（60 分制，BSR 不达标行标"不予推荐评级"）→ 每维 0–10 得分条 → 细节锤点折叠区 → 雷达图+象限图内嵌 → Elo 表+胜率矩阵。
- **盲测页**：静态 A/B 并排（只见代号），下方手动记票用 battles.jsonl 追加工具（CLI `rp-eval battle` 或页面按钮写本地文件均可，实现从简）。

## 验收标准（MVP 整体）

- [ ] `uv sync` 后 `rp-eval` 一条命令起服务自动开浏览器，无其他前置
- [ ] 控制台勾选 2 模型×1 题卡能跑通，SSE 实时流逐轮出判定，中途关页面重开能续看
- [ ] 跑完自动落 dialogue.jsonl / score.json / charts/两张 PNG
- [ ] 证据浏览器能逐轮看 judge 标签+证据高亮+checklist 时间线
- [ ] 榜单页展示总分/每维分/细节锤点/Elo/两张图
- [ ] 新增一个被测模型=只改 models.yaml；新增一道题=只写一个 scenes/*.yaml
- [ ] judge 与被测模型同族时启动报警告（配置校验）
- [ ] `git status` 下 stress 目录与 runs 目录不可见（.gitignore 生效）
- [ ] 单 run 成本读数显示在控制台（API 费用累计）

## 范围外（本期不做）

- 观众投票服务端、动态 agentic user、多 run 并发、鉴权、数据库、英文界面、崩档曲线/表格图、素材导出。

## 票清单（tracer-bullet，按序实现，每票一 commit）

| 票 | 标题 | Blocked by |
|---|---|---|
| 01 | 仓库骨架+init+服务起浏览器薄片 | 无 |
| 02 | 题卡/模型 YAML 加载校验（含同族警告） | 01 |
| 03 | runner：单模型单轮→全脚本多轮，落 dialogue.jsonl | 02 |
| 04 | judge：checklist 状态机单轮判分，落 score.json | 03 |
| 05 | 六类反应+审查阶梯 OOR/BUR/BSR/崩档点 | 04 |
| 06 | 聚合：0–10 换算+总分+arena-rank Elo | 04 |
| 07 | 图表：雷达图+象限图 PNG | 06 |
| 08 | 控制台页+SSE 实时流+终端彩色打印 | 03 |
| 09 | 证据浏览器页 | 04,08 |
| 10 | 榜单页+盲测静态页+battle 记票 | 06,07 |

每票详情见 issues/NN-*.md。G1 开工每票时复述验收给用户确认。
