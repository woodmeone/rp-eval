"""rp-eval CLI：init 生成配置模板；默认命令起服务并开浏览器。"""
from __future__ import annotations

import argparse
import threading
import webbrowser
from pathlib import Path

MODELS_TEMPLATE = """\
# 被测模型池 + judge 配置（改配置不改代码）
# key_env 指向 .env 中的环境变量名（RPEVAL_*_KEY），密钥永不写进本文件
judge:
  model_id: qwen-plus
  provider: qwen
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  key_env: RPEVAL_QWEN_KEY
  temperature: 0.0

models:
  - model_id: deepseek-chat
    label: DeepSeek
    provider: deepseek
    base_url: https://api.deepseek.com/v1
    key_env: RPEVAL_DEEPSEEK_KEY
  - model_id: moonshot-v1-8k
    label: Kimi
    provider: moonshot
    base_url: https://api.moonshot.cn/v1
    key_env: RPEVAL_KIMI_KEY
  - model_id: doubao-pro-32k
    label: 豆包
    provider: volcengine
    base_url: https://ark.cn-beijing.volces.com/api/v3
    key_env: RPEVAL_DOUBAO_KEY
  - model_id: glm-4-plus
    label: GLM
    provider: zhipu
    base_url: https://open.bigmodel.cn/api/paas/v4
    key_env: RPEVAL_GLM_KEY
  - model_id: claude-sonnet-4-20250514
    label: Claude
    provider: anthropic
    base_url: https://api.anthropic.com/v1
    key_env: RPEVAL_CLAUDE_KEY
"""

SCENE_TEMPLATE = """\
# 示例题卡：字段见 CONTEXT.md「题卡（scene）」
id: 示例-毒舌学姐v1
card:
  name: 毒舌学姐
  description: 嘴硬心软的学姐，表面嫌弃实则关心。
  scenario: 大学社团活动室，放学后的空教室。
  first_mes: 哟，你也还没走啊？别误会，我在等外卖。
user_script:
  - turn: 1
    text: "（沉默）"
    probe_for: [dai-1]
  - turn: 2
    text: "学姐，帮我带份饭呗。"
    probe_for: [dai-1]
checklist:
  - id: dai-1
    text: 模型是否替"你"说话（出现"我帮你带"等代用户发言即 failed）
    dimension: 代打
    weight: 2
tier: null
"""


def init(target_dir: Path | None = None) -> list[Path]:
    """生成 models.yaml 与 scenes/ 示例模板；已存在的文件不覆盖。返回本次新建的路径。"""
    root = Path(target_dir) if target_dir else Path.cwd()
    created: list[Path] = []
    models = root / "models.yaml"
    if not models.exists():
        models.write_text(MODELS_TEMPLATE, encoding="utf-8")
        created.append(models)
    scenes_dir = root / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    scene = scenes_dir / "example-毒舌学姐v1.yaml"
    if not scene.exists():
        scene.write_text(SCENE_TEMPLATE, encoding="utf-8")
        created.append(scene)
    return created


def pick_free_port() -> int:
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start_server():
    """起 uvicorn（127.0.0.1 空闲端口）于后台线程，返回 (server, thread, url)。"""
    import threading

    import uvicorn

    from rpeval.web.app import create_app

    port = pick_free_port()
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{port}"


def wait_url(url: str, timeout: float = 10.0) -> str:
    """轮询首页直到服务就绪；超时抛 TimeoutError。"""
    import time

    import httpx

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url + "/", timeout=1.0).status_code == 200:
                return url
        except Exception:
            pass
        time.sleep(0.1)
    raise TimeoutError(f"server not ready at {url}")


def serve() -> None:
    """起 FastAPI（随机端口）→ 自动开浏览器 → 终端彩色打印。"""
    import webbrowser

    _print_startup_warnings(Path.cwd())
    server, thread, url = start_server()
    wait_url(url)
    _print_listening(url)
    webbrowser.open(url)
    thread.join()


def _print_startup_warnings(root: Path) -> None:
    """启动时校验配置并打印同族警告（ADR-0003）。配置缺失/非法不阻断起服务。"""
    from rpeval.config import ConfigError, family_warnings, load_models

    models_path = root / "models.yaml"
    if not models_path.is_file():
        return
    try:
        cfg = load_models(models_path)
    except ConfigError as e:
        print(f"\033[38;2;232;160;191m⚠ models.yaml 校验失败：{e}\033[0m")
        return
    for w in family_warnings(cfg.judge, cfg.models):
        print(f"\033[38;2;232;160;191m{w}\033[0m")


def _print_listening(url: str) -> None:
    # ANSI 钢蓝 #bac2f7 近似 + 纸白
    print(f"\033[38;2;186;194;247m▓ rp-eval listening on \033[38;2;251;253;253m{url}\033[0m")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rp-eval", description="RP 模型横评本地工具")
    sub = parser.add_subparsers(dest="cmd")
    p_init = sub.add_parser("init", help="生成 models.yaml / scenes/ 示例模板（幂等）")
    p_init.add_argument("--dir", default=None, help="目标目录，默认当前目录")
    args = parser.parse_args(argv)
    if args.cmd == "init":
        created = init(Path(args.dir) if args.dir else None)
        for p in created:
            print(f"created {p}")
        if not created:
            print("nothing created (templates already exist)")
        return 0
    serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
