# 票01 — 仓库骨架 + init + 服务起浏览器薄片

## 用户故事
作为 UP 主，我 `uv sync` 后敲 `rp-eval`，浏览器自动打开一个像素主题首页，看到"服务已就绪"。

## 端到端验收
- [ ] uv 项目骨架：`src/rpeval/` 包 + pyproject.toml + entry point `rp-eval`
- [ ] `rp-eval init` 生成 models.yaml / scenes/ 示例模板（幂等，已存在不覆盖）
- [ ] `rp-eval` 起 FastAPI（本地随机端口）→ 自动开浏览器 → 首页渲染像素主题（双层网格+扫描线+四色变量+像素字体）
- [ ] 终端彩色打印"listening on …"
- [ ] .gitignore 已含 scenes/stress/ 与 runs/（本票验证：mkdir stress 放测试文件，`git status` 不可见）

## 范围外
真实测评逻辑、任何数据加载。

## 真相影响
PROJECT.md 模块地图 cli/web 行由"计划"变"现状"；无新术语。
