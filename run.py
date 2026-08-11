"""
统一启动入口：在保持 app.py 原有启动方式的前提下，同时启动 MCP Server。

用法：
    python run.py              默认：启动 MCP Server（HTTP :8000）+ 主 Flask 应用（:5000）
    python run.py web          仅启动主 Flask 应用（等价于 python app.py）
    python run.py mcp          仅启动 MCP Server（stdio 模式，供 Claude Desktop 等客户端连接）
    python run.py mcp-http     仅启动 MCP Server（HTTP / streamable-http，默认 :8000）
    python run.py mcp-check    对 MCP Server 做一次自检后退出

环境变量：
    MCP_HOST / MCP_PORT         MCP HTTP 服务监听地址（默认 127.0.0.1:8000）
    HOST / PORT                 主 Flask 应用监听地址（默认 0.0.0.0:5000）
    FLASK_DEBUG                 是否开启调试模式（默认 true）
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

MCP_STDOUT_LOG = LOG_DIR / "mcp_server_stdout.log"
MCP_STDERR_LOG = LOG_DIR / "mcp_server_stderr.log"

MCP_HTTP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_HTTP_PORT = int(os.environ.get("MCP_PORT", 8000))

FLASK_HOST = os.environ.get("HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("PORT", 5000))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "true").lower() == "true"

logger = logging.getLogger("run")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def check_mcp_server_once() -> bool:
    """启动前对 MCP Server 做一次暖机自检（通过 stdio 拉起子进程并验证工具可加载）。"""
    from mcp_client import check_mcp_server

    result = check_mcp_server()
    if result.get("success"):
        logger.info(
            "MCP Server 自检通过: server=%s, tools=%s",
            result.get("server_name"),
            result.get("tools"),
        )
        return True

    logger.error("MCP Server 自检失败: %s", result.get("error"))
    return False


def start_mcp_http_subprocess() -> subprocess.Popen:
    """以子进程方式启动 MCP Server（streamable-http），输出写入 logs/ 目录。"""
    logger.info("正在启动 MCP Server (HTTP) %s:%s ...", MCP_HTTP_HOST, MCP_HTTP_PORT)
    with (
        MCP_STDOUT_LOG.open("a", encoding="utf-8") as stdout_file,
        MCP_STDERR_LOG.open("a", encoding="utf-8") as stderr_file,
    ):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "mcp_server.http_app:app",
                "--host",
                str(MCP_HTTP_HOST),
                "--port",
                str(MCP_HTTP_PORT),
                "--log-level",
                "info",
            ],
            cwd=str(BASE_DIR),
            env={**os.environ, "PYTHONPATH": str(BASE_DIR)},
            stdout=stdout_file,
            stderr=stderr_file,
        )
    logger.info("MCP Server (HTTP) 已启动，PID=%s", process.pid)
    return process


def run_flask_app() -> None:
    """启动主 Flask 应用（与 app.py 的 __main__ 保持一致的启动参数）。"""
    from app import app

    logger.info("正在启动主 Flask 应用 http://%s:%s ...", FLASK_HOST, FLASK_PORT)
    app.run(
        debug=FLASK_DEBUG,
        host=FLASK_HOST,
        port=FLASK_PORT,
    )


def run_mcp_stdio() -> None:
    """以 stdio 方式运行 MCP Server（供 MCP 客户端连接）。"""
    from mcp_server.server import main as mcp_server_main

    mcp_server_main()


def run_mcp_http() -> None:
    """在前台运行 MCP Server（streamable-http）。"""
    import uvicorn

    from mcp_server.http_app import app

    uvicorn.run(app, host=MCP_HTTP_HOST, port=MCP_HTTP_PORT, log_level="info")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="学生信息管理系统统一启动入口",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="all",
        choices=["all", "web", "mcp", "mcp-http", "mcp-check"],
        help="启动模式（默认 all：MCP + 主应用）",
    )
    args = parser.parse_args(argv)

    setup_logging()

    if args.mode == "mcp":
        run_mcp_stdio()
        return 0

    if args.mode == "mcp-http":
        run_mcp_http()
        return 0

    if args.mode == "mcp-check":
        ok = check_mcp_server_once()
        return 0 if ok else 1

    if args.mode == "web":
        run_flask_app()
        return 0

    # all 模式：MCP 自检 -> 拉起 MCP HTTP 子进程 -> 启动主应用
    # Flask debug 模式的重载器会以子进程重新执行 run.py，
    # 通过 WERKZEUG_RUN_MAIN 区分父/子进程：仅在父进程拉起 MCP，避免重复启动。
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    mcp_process: subprocess.Popen | None = None
    if not is_reloader_child:
        check_mcp_server_once()
        mcp_process = start_mcp_http_subprocess()

    try:
        run_flask_app()
    finally:
        if mcp_process is not None and mcp_process.poll() is None:
            logger.info("正在关闭 MCP Server (PID=%s)...", mcp_process.pid)
            mcp_process.terminate()
            try:
                mcp_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                mcp_process.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
