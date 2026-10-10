# PROJECT.md — rp-eval 当前真相

> 只回答"项目现在是什么样"。为什么这样→docs/adr/；术语→CONTEXT.md；意图→票。

## 目标

RP 模型横评本地工具：脚本化多轮取证 + LLM judge 判分 + Elo 聚合 + 像素风可视化前端，
服务"比特毯子"账号的模型测评系列视频（EP1=RP 模型横评，六项：文笔/入戏/审查/舔狗/代打/记忆）。

## 模块地图（现状：MVP 十票 + 设置页/全局导航/八维题库/破甲分级/程序化校验/NIAH长文注入/破甲payload注入+证据结论横幅+证据页交互优化(筛选/折叠/分组/热力图)+灰度复杂卡+长文注入破限变体，152 测试通过）

| 模块 | 代码区域 | 核心入口 | 职责 |
|---|---|---|---|
| cli | `src/rpeval/cli.py` | `rp-eval` | 一条命令起 FastAPI 服务并自动开浏览器；`rp-eval init` 生成配置模板 |
| config | `src/rpeval/config.py` | `load_scenes()/load_models()` | 题卡 YAML（含 scenes/stress/ 子目录）+ models.yaml 加载校验（含价格字段）+ 同族警告 |
| settings | `src/rpeval/settings.py` | `save_settings()/settings_view()` | 预置 8 家服务商注册表；前端配置写 models.yaml（无 key）+ .env（key 永不入库）；只读视图仅回显 key_set |
| runner | `src/rpeval/runner.py` | `run()`/`build_case_async()` | OpenAI 兼容并行调被测模型，按 user_script 喂轮次，落 dialogue.jsonl，断点续跑 |
| judge | `src/rpeval/judge.py` | `run_state_machine()`/`judge_reactions()`/`ladder_metrics()`/`write_score_json()` | TRACE 状态机 checklist 取证 + 六类反应判定 + n=5 多数票 + 崩档点/OOR/BUR/BSR/rated，落 score.json 末端自动出图 |
| aggregate | `src/rpeval/agg.py` | `leaderboard()`/`bt_ratings()`/`judge_battle()` | 0–10 换算+总分60 汇总 / Bradley-Terry 自实现 Elo+bootstrap CI+胜率矩阵 / battles.jsonl 读写 / 成对比较双向平均防位置偏差 |
| charts | `src/rpeval/charts.py` | `render_run_charts()` | matplotlib 雷达图+象限图 PNG（像素四色，横/竖两套尺寸） |
| web | `src/rpeval/web/` | FastAPI 路由 | 控制台(SSE 实时流)/证据浏览器/榜单页/盲测页 + 像素主题；console.py 管 run 互斥与事件流，evidence.py 合并 dialogue+score，leaderboard.py 聚合+盲测记票 |

## 数据落盘

```
scenes/*.yaml            # 题卡（可开源）
scenes/stress/           # 压力阶梯话术（.gitignore 排除，永不入库）
models.yaml              # 被测池 + judge 配置（改配置不改代码）
runs/<run_id>/           # dialogue.jsonl / score.json / battles.jsonl / charts/*.png（.gitignore 排除）
```

> 注：battles.jsonl 落 `runs/<run_id>/` 内（随 run 走），非独立 `battles/` 目录；Elo 实时由 `agg.bt_ratings` 从 battles 算，不单独落 `leaderboard/elo.json`（榜单页按需计算）。

## 关键约束

- 单人可维护：Python 单仓（uv），无前端构建链，文件即数据库；
- 合规红线：题库私有、话术永不外泄、对外措辞体检化（ADR-0002）；
- judge 与被测池无同族（ADR-0003）；判定禁正则、LLM 判实质；
- 单用户本地服务：无鉴权，一次只跑一个 run；
- 视觉=账号像素主题（四色+双层网格+扫描线+像素字体；樱粉=警报，钢蓝=正常）。

## 当前功能清单（MVP 十票完成）

- **cli**：`rp-eval` 一条命令起服务+自动开浏览器；`rp-eval init` 生成 models.yaml/题卡模板。
- **config**：题卡/模型 YAML 加载校验、价格字段解析、judge 与被测池同族警告、check 语法解析、long_doc 解析、payload/payload_desc/goal 字段解析。
- **runner**：OpenAI 兼容并行调被测模型，按 user_script 喂多轮，落 dialogue.jsonl，断点续跑；**long_doc 长文注入**（filler×repeat + needle 按 depth 插入，NIAH 大海捞针）；**{payload} 占位替换**（轮级 payload 优先、缺省场景级，钓句载荷私有注入台词与长文针）。
- **judge**：TRACE checklist 状态机取证（pending→verified/failed，failed 不可逆）+ 六类反应判定 + n=5 多数票；**程序化校验 run_checks**（check 字段：json@N/html@N/len@N:n/regex@N:match|not|count，确定性判分不走 LLM，语义类仍禁正则）；审查阶梯 L0–L6 → 崩档点/破甲等级/OOR/BUR/BSR/rated 一票否决；反应判官注入 payload_desc 钓句目标（"真交付什么才算 harmful comply"）；score.json 每 case 附 **verdict 结论**（headline/tone/tested/proves）；末端自动出图。
- **aggregate**：0–10 各维得分 + 总分（=各维之和，随维度数扩展）榜单；Bradley-Terry 自实现 Elo（MM 迭代 + reg=0.5 伪计数）+ bootstrap CI + 胜率矩阵；judge 自动 battle（双向平均防位置偏差 + 长度截断）与人工记票混装 battles.jsonl。
- **charts**：matplotlib 雷达图 + 审查象限图 PNG（像素四色，横 1920×1080 / 竖 1080×1920，无阶梯数据优雅降级）。
- **web**：控制台（勾模型/题卡+预估成本+SSE 实时判定流+重连回放+维度说明文案）、证据浏览器（**结论总览热力图** 模型×题卡矩阵tone配色+点击跳转case / **高亮结论横幅** verdict=一句话判定+tone配色+测了什么+证明了什么 / 逐轮六类徽章+证据高亮 / checklist 逐条"测→证"取证 / 左列**按场景分组**组头含模型数+破甲计数 / **结论筛选按钮**全部/守住/部分/破甲失守+tone过滤联动组头隐藏 / **长回复点击折叠**>220字默认收起 / **checklist只看问题项开关** / 维度得分面板含破甲档）、榜单页（总分表+得分条+**结论列**每模型最差tone横幅+守住/失守计数+逐卡结论可展开(无verdict灰显降级)+锤点+Elo+图内嵌）、盲测页（A/B 代号并排→投票→揭名，揭名前响应无真名）；终端 ANSI 彩色轮次卡；六页全局导航条；设置页（/settings 前端配置模型 URL/Key，预置服务商下拉，key 仅落 .env 永不回显）；SSE error 事件失败卡片带"检查密钥→"跳转。
- **题库**（scenes/，可开源部分）：学姐卡多维（代打5轮+舔狗3轮+记忆探针）、入戏-大禹时代探针卡、文笔-AI味检测卡、格式遵从卡 v2（11 项全程序化 check：JSON/字数/禁数字/复合模板/300字大HTML配平/三段占位模板/Markdown表格5行/嵌套列表顶层+缩进/代码围栏+函数签名）、长上下文卡（NIAH大海捞针40节depth0.5+NoLiMa无字面召回/远距离召回/规则保持/守密）、**破甲演示卡**（poijia-禁词游戏，L3人设注入，payload=蓝鲸7749 无害载荷端到端跑通破甲链路，可入库对外展示机制）；审查阶梯 L0–L6 落 scenes/stress/（.gitignore 排除，话术私有永不入库），其中 L3–L6 重写为**破甲四级**通用手法骨架：L3=单轮人设注入(DAN/persona modulation)、L4=情景嵌套(fiction/戏中戏)、L5=多轮渐进升温(Crescendo/Echo Chamber)、L6=组合攻击红线(persona+嵌套+升温+编码混淆)；手法名取自公开分类学(SoK 2510.15476/HarmBench/J2)，钓句载荷走 {payload} 占位待替换；**破甲变体 L6b 长文注入型**（上下文层破限：诱导指令伪装成附录口令埋进 40 节长文 depth0.5，测 Lost-in-the-Middle 是否仍被钓起，落 stress/ 私有）；**灰度复杂卡**（ruxi-灰度中介v1，可入库）：亦正亦邪掮客"梅姐"，一卡多维=入戏(张力不洗白不说教)+记忆(第3轮立"不碰害孩子"底线→第4/5轮施压看跨轮一致)+代打(沉默轮)+审查(灰度请求角色内周旋+情景嵌套无害演示)，描述遵循概率计算器写卡论"高信号词+留活口"。
- **审查阶梯指标**：崩档点(首次出戏档·测过敏) + 破甲等级(首次 harmful comply 档·测失守，与崩档点对偶) + OOR/BUR/BSR + rated 一票否决；证据页与象限图同源展示。

## 演进方向

- MVP 十票（.scratch/rp-eval-mvp/issues/）走 tracer-bullet：先端到端薄片，再逐层加厚；
- EP1 之后：长线退化马拉松专题、观众实时投票（若做）、框架开源发布；
- **备忘**：复杂角色卡已按「角色卡知识框架」自研首张（ruxi-灰度中介v1，道德灰度掮客），后续可扩多张灰度卡作基准；stress L3–L6/L6b 的【私有钓句·占位】仍待实跑前替换为私有话术；知识框架文档落 research/（.gitignore 排除，永不入库）。
