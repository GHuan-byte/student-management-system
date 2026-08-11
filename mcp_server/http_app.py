"""MCP Server 的 HTTP（streamable-http）入口。

供 uvicorn 直接加载启动，例如：

    python -m uvicorn mcp_server.http_app:app --host 127.0.0.1 --port 8000

也可以被 run.py 以子进程方式拉起，与主 Flask 应用同时运行。
"""

from __future__ import annotations

from mcp_server.server import mcp

# 复用 server.py 中已注册好全部工具（含学生数据库工具）的 mcp 实例，
# 将其包装为 Starlette ASGI 应用供 uvicorn 服务。
app = mcp.streamable_http_app()
