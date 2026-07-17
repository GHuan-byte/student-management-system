from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP

from mcp_server.student_tools import register_student_tools


# ============================================================
# 1. 创建 MCP Server
# ============================================================

mcp = FastMCP(
    name="Student Management MCP Server",
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
# 6. stdio 服务入口
# ============================================================

def main() -> None:
    """
    以 stdio 方式启动 MCP Server，通过标准输入/输出与客户端通信。
    """

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
