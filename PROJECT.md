# PROJECT.md — rp-eval 当前真相

> 只回答"项目现在是什么样"。为什么这样→docs/adr/；术语→CONTEXT.md；意图→票。

## 目标

RP 模型横评本地工具：脚本化多轮取证 + LLM judge 判分 + Elo 聚合 + 像素风可视化前端，
服务"比特毯子"账号的模型测评系列视频（EP1=RP 模型横评，**六大项**：文笔/格式/抢话/入戏/审查/记忆）。

## 模块地图（现状：MVP 十票 + v2 四 Issue（#1–#4）全部完成，284 测试通过）

| 模块 | 代码区域 | 核心入口 | 职责 |
|---|---|---|---|
| cli | `src/rpeval/cli.py` | `rp-eval` | 一条命令起 FastAPI 服务并自动开浏览器；`rp-eval init` 生成配置模板 |
| config | `src/rpeval/config.py` | `load_scenes()/load_models()` | 题卡 YAML（含 scenes/stress/ 子目录）+ models.yaml 加载校验（含价格字段）+ 同族警告 + judge 温度必须为 0 |
| settings | `src/rpeval/settings.py` | `save_settings()/settings_view()` | 预置 8 家服务商注册表；前端配置写 models.yaml（无 key）+ .env（key 永不入库）；只读视图仅回显 key_set |
| runner | `src/rpeval/runner.py` | `run()`/`build_case_async()` | OpenAI 兼容并行调被测模型，按 user_script 喂轮次，落 dialogue.jsonl，断点续跑；**提示词装配**（预设→卡面→资料→收尾，ADR-0005）+ 双壳 |
| judge | `src/rpeval/judge.py` | `run_state_machine()`/`judge_reactions()`/`ladder_metrics()`/`write_score_json()` | TRACE 状态机 checklist 取证 + 六类反应判定 + n=5 多数票 + 崩档点/破甲等级/打太极率/OOR/BUR/BSR/rated，落 score.json 末端自动出图 |
| export | `src/rpeval/export.py` | `build_script_pack()`/`write_script_pack()`/`render_markdown()` | 一次 run → 脚本数据包（七块 + 口径自述 + 脱敏），只做视图不重算指标 |
| aggregate | `src/rpeval/agg.py` | `leaderboard()`/`bt_ratings()`/`judge_battle()` | 0–10 换算+总分60 汇总 + **预设差值** / Bradley-Terry 自实现 Elo+bootstrap CI+胜率矩阵 / battles.jsonl 读写 |
| charts | `src/rpeval/charts.py` | `render_run_charts()` | matplotlib 雷达图+象限图 PNG（像素四色，横/竖两套尺寸） |
| labels | `src/rpeval/web/labels.py` | `reaction_label()/metric_label()` | **显示层白话映射的唯一来源**：代码值与数据契约用原 key，界面文字一律从这里取 |
| web | `src/rpeval/web/` | FastAPI 路由 | 控制台(SSE 实时流)/证据浏览器/榜单页/盲测页 + 像素主题；console.py 管 run 互斥与事件流，evidence.py 合并 dialogue+score，leaderboard.py 聚合+盲测记票 |

## 数据落盘

```
scenes/*.yaml            # 题卡（可开源）
scenes/stress/           # 压力阶梯话术（.gitignore 排除，永不入库）
models.yaml              # 被测池 + judge 配置（改配置不改代码）
runs/<run_id>/           # dialogue.jsonl / score.json / battles.jsonl / script_pack.{md,json} / charts/*.png（.gitignore 排除）
```

> 注：battles.jsonl 落 `runs/<run_id>/` 内（随 run 走），非独立 `battles/` 目录；Elo 实时由 `agg.bt_ratings` 从 battles 算，不单独落 `leaderboard/elo.json`（榜单页按需计算）。

## 关键约束

- 单人可维护：Python 单仓（uv），无前端构建链，文件即数据库；
- 合规红线：题库私有、话术永不外泄、对外措辞体检化（ADR-0002）；**导出脚本包按 tier 打码，payload/payload_desc 永不出现**；
- judge 与被测池无同族（ADR-0003）；**judge.temperature 必须为 0**；判定禁正则、LLM 判实质（格式类确定性 check 除外）；
- **提示词装配顺序固定**（预设→卡面→资料→收尾，ADR-0005）；旧题卡拼出必须逐字节一致；
- 单用户本地服务：无鉴权，一次只跑一个 run；
- 视觉=账号像素主题（四色+双层网格+扫描线+像素字体；樱粉=警报，钢蓝=正常）；**界面不出现英文缩写**（显示文字统一从 `web/labels.py` 取）；
- 开发纪律：功能改动走 `/git-native-sop` 三门（G1 门禁 → G2 测试+票级/PR 级审查 → G3 回写）；**文档维护类小改动走 `docs:` 前缀直推 main**（不变量 3 的仓库级例外，已在此声明，不留灰色地带）。

## 当前功能清单（MVP 十票 + v2 四 Issue 完成）

- **cli**：`rp-eval` 一条命令起服务+自动开浏览器（端口随机，终端打印实际地址）；`rp-eval init` 生成 models.yaml/题卡模板。
- **config**：题卡/模型 YAML 加载校验、价格字段解析、judge 与被测池同族警告、check 语法解析、long_doc 解析、payload/payload_desc/goal 字段解析、**lore/preset 可选字段（类型错报文件名+字段名）**、**judge.temperature 必须为 0（缺省补 0，非 0 报错）**。
- **runner**：OpenAI 兼容并行调被测模型，按 user_script 喂多轮，落 dialogue.jsonl，断点续跑；**提示词装配（预设→卡面→资料→收尾，ADR-0005）**；**双壳跑（裸壳/带预设）**；long_doc 长文注入（NIAH）；{payload} 占位替换。
- **judge**：TRACE checklist 状态机取证 + 六类反应判定 + n=5 多数票；程序化校验 run_checks（json/html/len/regex）；审查阶梯 L0–L6 → 崩档点/破甲等级/**打太极率**/OOR/BUR/BSR/rated 一票否决；**打太极计入该答不答，且 L6 打太极不算守住底线**；score.json 每 case 附 verdict 结论；末端自动出图。
- **export**：一次 run → 脚本数据包（`script_pack.md` + `.json`，七块：口径自述/榜单/锤点/正面素材/题卡×模型/可信度/元数据）；**私有档 user 轮打码、payload 与 payload_desc 永不出现**；`/api/script_pack/{run_id}?format=md|json` 先落盘再下发。
- **aggregate**：0–10 各维得分 + 总分榜单；**预设差值（两壳都跑过才算，否则 None）**；Bradley-Terry Elo + bootstrap CI + 胜率矩阵；judge 自动 battle 与人工记票混装。
- **charts**：matplotlib 雷达图 + 审查象限图 PNG（像素四色，横竖两套，无阶梯数据优雅降级；轴标为白话）。
- **labels**：显示层白话映射唯一来源（六类反应 / 阶梯指标 / 取证状态 / 反应计数摘要）。**界面任何位置不出现英文缩写**，有 7 页 × 3 层的验收测试守着。
- **web**：控制台（勾模型/题卡/**外壳开关**+预估成本+SSE 实时判定流+维度说明）、证据浏览器（结论热力图+结论横幅+逐轮徽章+检查项取证+场景分组+筛选+折叠+**压力档白话名**+**导出脚本包按钮**）、榜单页（总分表+**预设差值列**+得分条+结论列+锤点+Elo+图内嵌）、盲测页、设置页、**run 列表标 v1 口径**。
- **题库**（19 张，六大项）：学姐卡（抢话正反两面+记忆）、入戏-大禹、**入戏-人设漂移v1**（12 轮口癖漂移）、文笔-AI味、**格式-卡格式遵从v3**（9 项全程序化）、格式-硬约束v2（保留）、长上下文×2（已归入记忆）、**记忆-资料召回v1**（世界书首次进评测）、破甲演示卡、灰度复杂卡、审查阶梯 L0–L6+L6b（私有）。
- **审查阶梯指标**：崩档点（首次出戏档·测过敏）+ 破甲等级（首次 harmful comply 档·测失守，与崩档点对偶）+ 打太极率 + OOR/BUR/BSR + rated 一票否决；证据页与象限图同源展示。


## 演进方向

- v2（Issue #1–#4）已完成：术语白话化 / 导出脚本包 / 资料与预设进上下文 / 题库重做与判分补漏；
- 下一批候选：**每 case 重复采样 + 反应判定投票**（当前判分噪声未平均，KNOWN_LIMITS 第一条）、
  抗截断指标（提纲率/半句率/截断率）、判据体检（meta-eval）、人工抽检一致率；
- EP1 之后：长线退化马拉松专题、观众实时投票（若做）、框架开源发布；
- **备忘**：stress L3–L6/L6b 的【私有钓句·占位】仍待实跑前替换为私有话术；知识框架文档落 research/（.gitignore 排除，永不入库）。

## 当前停点（2026-10-18 回写，v2 四 Issue 完成，284 测试通过）

- **工具侧**：#1–#24 + v2 的 #1–#4 全部完成；**284 测试通过**；真实链路已用中转站跑通（judge=MiniMax-M3，被测 deepseek-v4.1-flash / glm-5.3-flash）。服务**端口随机**（`cli.pick_free_port()`），启动后终端打印实际地址。
- **素材侧**：Discord 三社区（旅程/类脑/开始吧）采集完成，`research/` 已有破限知识框架、角色卡知识框架及学习笔记；三类公开数据集已抓齐入库 `research/datasets/`。
- **待办（按优先级）**：① 用户手动替换 stress L3–L6/L6b 与灰度卡的【私有钓句·占位符】→ 跑破甲实测；② EP1 视频制作未启动（调研+工具已就绪，待进自媒体管线）；③ 可选：扩灰度卡集、框架开源发布。
- 新会话/AI 接手先读 **HANDOFF.md**。
