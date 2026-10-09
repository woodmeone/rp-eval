# PROJECT.md — rp-eval 当前真相

> 只回答"项目现在是什么样"。为什么这样→docs/adr/；术语→CONTEXT.md；意图→票。

## 目标

RP 模型横评本地工具：脚本化多轮取证 + LLM judge 判分 + Elo 聚合 + 像素风可视化前端，
服务"比特毯子"账号的模型测评系列视频（EP1=RP 模型横评，六项：文笔/入戏/审查/舔狗/代打/记忆）。

## 模块地图（目标架构，代码未开工）

| 模块 | 代码区域 | 核心入口 | 职责 |
|---|---|---|---|
| cli | `src/rpeval/cli.py` | `rp-eval` | 一条命令起 FastAPI 服务并自动开浏览器 |
| config | `src/rpeval/config.py` | `load_scenes()/load_models()` | 题卡 YAML + models.yaml 加载校验 |
| runner | `src/rpeval/runner.py` | `run(scene, models)` | OpenAI 兼容并行调被测模型，按 user_script 喂轮次，落 dialogue.jsonl，断点续跑 |
| judge | `src/rpeval/judge.py` | `score(run)` | TRACE 状态机 checklist 取证 + 六类反应判定 + n=5 多数票，落 score.json |
| aggregate | `src/rpeval/agg.py` | `leaderboard(run)` | 0–10 换算+总分60 / OOR·BUR·BSR·崩档点 / arena-rank Elo+CI / matplotlib 雷达图+象限图 PNG |
| web | `src/rpeval/web/` | FastAPI 路由 | 控制台(SSE 实时流)/证据浏览器/榜单页/盲测页 + 像素主题静态资源 |

## 数据落盘

```
scenes/*.yaml            # 题卡（可开源）
scenes/stress/           # 压力阶梯话术（.gitignore 排除，永不入库）
models.yaml              # 被测池 + judge 配置（改配置不改代码）
runs/<run_id>/           # dialogue.jsonl / score.json / charts/*.png（.gitignore 排除）
battles/battles.jsonl    # 成对比较记录
leaderboard/elo.json     # BT 评分+CI+胜率矩阵
```

## 关键约束

- 单人可维护：Python 单仓（uv），无前端构建链，文件即数据库；
- 合规红线：题库私有、话术永不外泄、对外措辞体检化（ADR-0002）；
- judge 与被测池无同族（ADR-0003）；判定禁正则、LLM 判实质；
- 单用户本地服务：无鉴权，一次只跑一个 run；
- 视觉=账号像素主题（四色+双层网格+扫描线+像素字体；樱粉=警报，钢蓝=正常）。

## 当前功能清单

- 无（文档阶段：CONTEXT.md + ADR 0001–0004 + spec + 票已落盘，代码未开工）。

## 演进方向

- MVP 十票（.scratch/rp-eval-mvp/issues/）走 tracer-bullet：先端到端薄片，再逐层加厚；
- EP1 之后：长线退化马拉松专题、观众实时投票（若做）、框架开源发布。
