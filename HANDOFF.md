# HANDOFF — rp-eval AI 接手指南

> 给新会话/AI 的一页上手文档。先读完本文，再按需深入 PROJECT.md / CONTEXT.md / docs/adr/。
> 项目要搬迁位置的话，先读 **迁移清单.md**。
> 最后更新：2026-10-18，git 干净于 `a01d919`，152 测试全过。

## 一、这是什么项目（30 秒）

**RP 模型横评本地工具**：脚本化多轮取证 + LLM judge 判分 + Bradley-Terry Elo 聚合 + 像素风可视化前端。
服务对象是自媒体账号「比特毯子」的模型测评系列视频，**EP1 = RP 模型横评**（对外六维：文笔/入戏/审查/舔狗/代打/记忆）。
工具本身已完成并真实跑通，**当前卡在"私有钓句待用户替换"和"EP1 视频未启动"两件事上**。

## 二、阅读顺序（不要跳）

1. `CONTEXT.md` — 纯术语表（题卡/探针/压力阶梯/崩档点/OOR/BUR/BSR/六类反应/揭名…），全项目通用语言
2. `PROJECT.md` — 当前真相：模块地图、功能清单、数据落盘、**当前停点**
3. `docs/adr/0001–0004` — 四个关键决策的理由（形态=Web 应用 / 仓库边界与隐私 / judge 选型 / 双轨评分）
4. `.scratch/rp-eval-mvp/issues/01–10` — MVP 十票原始意图
5. `research/` — 知识框架（破限/角色卡）与公开数据集，做新题卡前先读

## 三、环境与命令

```powershell
cd d:\桌面\总\项目\rp-eval
uv sync                          # Python ≥3.11，依赖仅 fastapi/uvicorn/pyyaml/matplotlib/numpy
uv run pytest                    # 152 项回归，改任何代码后必须全过
uv run rp-eval                   # 起 FastAPI 服务并自动开浏览器（端口随机，终端会打印实际地址）
```

- 模型配置：`.env`（中转站 API Key，**已存在但永不入库、永不回显**）+ `models.yaml`（前端 /settings 页写入，预置 8 家厂商）。
- 已验证可用的真实配置：中转站跑通过 judge=MiniMax-M3、被测 deepseek-v4.1-flash / glm-5.3-flash。
- **模型名必须与端点实际返回的列表严格一致**（曾因写 `deepseek-flash` 不存在而跑挂）。

## 四、目录速查

```
src/rpeval/
  cli.py config.py settings.py runner.py judge.py agg.py charts.py llm.py
  web/  app.py console.py evidence.py leaderboard.py theme.py   # 四页前端+SSE
scenes/            # 公开题卡（可入库）：学姐/大禹/文笔/格式v2/长上下文×2/破甲演示/灰度ruxi
scenes/stress/     # L0–L6+L6b 压力阶梯话术 —— .gitignore 排除，私有！
runs/<run_id>/     # dialogue.jsonl / score.json / battles.jsonl / charts/*.png（不入库）
research/          # 知识框架+数据集（不入库）
docs/adr/  .scratch/rp-eval-mvp/  # 决策与票
```

## 五、进度与待办

**不在这里维护。** 进度看 `git log` + 已关 Issue，当前停点与待办看 `PROJECT.md §当前停点`。
（理由：一个事实只住一个家——历史住 Git，现状住 PROJECT.md。此节重复它们就是第二份清单。）

## 七、红线（违反=返工，必读）

- **合规**：题库话术私有永不入库；L6 红线档实测画面不外泄；审查模块对外统一叫「RP 耐心值测试」；破甲演示只用无害载荷（蓝鲸7749 类）。
- **密钥**：API Key 只进 `.env`，永不写 git、永不在前端回显（只回显 key_set）。
- **判分**：judge 与被测池禁同族（ADR-0003）；语义判定必须 LLM 判实质、**禁正则**；只有确定性格式 check（json/html/len/regex）允许程序化判分。
- **单用户本地**：无鉴权、一次只跑一个 run（console.py 有互斥）。
- **Discord 采集**：模拟浏览器访问必须避免被检测为机器/AI（手动浏览节奏）。

## 八、已知坑（都踩过，别重蹈）

- Bradley-Terry 必须带 `reg=0.5` 伪计数，否则 9:0 完全压制时 MLE 不存在、MM 迭代发散。
- 象限图无 L1–L5 阶梯数据时优雅降级返回 None（L6-only 不出图是**正确行为**，不是 bug）。
- `write_score_json` 出图失败走 stderr 告警，不作废整轮判分——别改回静默吞掉。
- config 的 `price_per_1k_*` 解析曾有真 bug（冒烟抓出），已修，回归时留意。
- MVP 边界项（有意为之，未修）：SSE 事件可能重复推送；盲测 pair 仅内存态不落盘。

## 九、开发纪律（用户强制要求）

- 任何开发动作走 **matt 系列流程**：ask-matt 路由 → grill-with-docs → to-spec → to-tickets → implement（内部 TDD）→ code-review；禁止 ad-hoc 手写代码+手动 pytest 替代。
- **每个 issue 一个 commit**，整体完成后统一 PR；不直接 push main（除非用户明示）。
- 视觉=账号像素主题：四色 #0b0c15/#fbfdfd/#e8a0bf/#bac2f7 + 双层网格 + 扫描线 + 像素字体；樱粉=警报，钢蓝=正常。
