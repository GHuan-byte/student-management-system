from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

from mcp.server.fastmcp import FastMCP

from mcp_server.student_tools import register_student_tools


# ============================================================
# 1. 创建 MCP Server (移至第 3 节)
# ============================================================

# ============================================================
# 2. HTTP 配置
# ============================================================

MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))



# ============================================================
# 3. 创建 MCP Server
# ============================================================

mcp = FastMCP(
    name="Student Management MCP Server",

    # 每次 HTTP 请求独立处理，适合后续横向扩展
    stateless_http=True,

    # 普通 JSON 响应，当前项目不依赖 SSE 流式返回
    json_response=True,

    # 网络监听设置
    host=MCP_HOST,
    port=MCP_PORT,
)



# ============================================================
# 4. 基础测试工具
# ============================================================

@mcp.tool()
def mcp_health_check() -> dict[str, str]:
    """
    检查 MCP Server 是否正常运行。

    如果能够成功调用该工具，说明：
    1. MCP Server 已成功启动；
    2. MCP Client 已成功连接；
    3. MCP Tool 可以正常执行。
    """

    return {
        "status": "ok",
        "server": "Student Management MCP Server",
        "message": "MCP Server 运行正常。",
    }


@mcp.tool()
def echo_message(message: str) -> dict[str, Any]:
    """
    原样返回客户端传入的消息。

    用于测试 MCP 工具参数传递和返回结果。
    """

    cleaned_message = message.strip()

    return {
        "success": True,
        "original_message": message,
        "cleaned_message": cleaned_message,
        "message_length": len(cleaned_message),
    }


# ============================================================
# 5. 注册学生数据库工具
# ============================================================

register_student_tools(mcp)


# ============================================================
# 6. HTTP 服务入口
# ============================================================

def main() -> None:
    """
    以 Streamable HTTP 方式启动 MCP Server。
    """

    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
