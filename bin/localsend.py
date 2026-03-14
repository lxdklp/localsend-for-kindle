import argparse
import asyncio
import logging
import os, sys

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(base_dir, "site-packages"))

try:
    from src.app import LocalSendApp
except ModuleNotFoundError as err:
    msg = str(err)
    if "aiohttp" in msg or "cryptography" in msg:
        print("依赖未找到: {}\n".format(msg))
        print("请将第三方库放到 lib/vendor 或者运行 pip install aiohttp cryptography 后重试。")
        sys.exit(1)
    raise
from src.config import load_config

log = logging.getLogger("localsend")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="LocalSend for Kindle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="",
    )
    parser.add_argument(
        "command", nargs="?", default="receive",
        choices=["receive", "send"],
        help="运行模式: receive(接收) / send(发送)",
    )
    parser.add_argument("files", nargs="*", help="要发送的文件路径 (send 模式)")
    args = parser.parse_args()
    # 日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # 从 config.json 加载配置
    cfg = load_config()
    cfg.command = args.command
    cfg.files = args.files or None
    try:
        if cfg.command == "send":
            from src.gui.send_gui import run_send_gui
            app = LocalSendApp(cfg)
            log.info("启动发送模式 (GUI)")
            asyncio.run(run_send_gui(app))
        else:
            app = LocalSendApp(cfg)
            log.info("启动 LocalSend 接收模式 (Ctrl+C 退出)")
            asyncio.run(app.run_server())
    except KeyboardInterrupt:
        log.info("已退出")

if __name__ == "__main__":
    main()
