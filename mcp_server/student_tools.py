from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError


# ============================================================
# 1. 数据库路径
# ============================================================

# 当前文件：
# D:\Python\student-management-system\mcp_server\student_tools.py
#
# parents[1]：
# D:\Python\student-management-system

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = PROJECT_ROOT / "data" / "students.db"


# ============================================================
# 2. 数据库连接
# ============================================================

def get_readonly_connection() -> sqlite3.Connection:
    """
    以只读模式连接学生数据库。

    只读模式可以避免当前测试阶段误修改数据库。
    """

    if not DB_PATH.exists():
        raise ToolError(f"数据库文件不存在：{DB_PATH}")

    # 转换成 SQLite URI，例如：
    # file:D:/Python/student-management-system/database/students.db?mode=ro
    database_uri = f"file:{DB_PATH.resolve().as_posix()}?mode=ro"

    try:
        connection = sqlite3.connect(
            database_uri,
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        return connection

    except sqlite3.Error as exc:
        raise ToolError(f"无法连接数据库：{exc}") from exc


# ============================================================
# 3. 注册学生相关 MCP Tools
# ============================================================

def register_student_tools(mcp: FastMCP) -> None:
    """
    将学生数据库工具注册到 MCP Server。

    目前只注册只读工具：
    1. 检查数据库状态
    2. 查看 students 表结构
    3. 统计学生数量
    """

    @mcp.tool()
    def database_status() -> dict[str, Any]:
        """
        检查学生数据库是否存在，并返回数据库中的表名。

        该工具不会修改数据库。
        """

        if not DB_PATH.exists():
            return {
                "success": False,
                "database_exists": False,
                "database_path": str(DB_PATH),
                "tables": [],
                "message": "没有找到数据库文件。",
            }

        try:
            with closing(get_readonly_connection()) as connection:
                rows = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    ORDER BY name
                    """
                ).fetchall()

            tables = [row["name"] for row in rows]

            return {
                "success": True,
                "database_exists": True,
                "database_path": str(DB_PATH),
                "tables": tables,
                "message": "数据库连接正常。",
            }

        except sqlite3.Error as exc:
            raise ToolError(f"读取数据库状态失败：{exc}") from exc

    @mcp.tool()
    def get_student_table_schema() -> dict[str, Any]:
        """
        获取 students 表的字段结构。

        返回字段名称、数据类型、是否允许为空以及是否为主键。
        """

        try:
            with closing(get_readonly_connection()) as connection:
                rows = connection.execute(
                    "PRAGMA table_info(students)"
                ).fetchall()

            if not rows:
                raise ToolError(
                    "数据库中没有找到 students 表，"
                    "请检查数据库表名。"
                )

            columns = []

            for row in rows:
                columns.append(
                    {
                        "column_id": row["cid"],
                        "name": row["name"],
                        "type": row["type"],
                        "not_null": bool(row["notnull"]),
                        "default_value": row["dflt_value"],
                        "primary_key": bool(row["pk"]),
                    }
                )

            return {
                "success": True,
                "table": "students",
                "column_count": len(columns),
                "columns": columns,
            }

        except ToolError:
            raise

        except sqlite3.Error as exc:
            raise ToolError(
                f"读取 students 表结构失败：{exc}"
            ) from exc

    @mcp.tool()
    def count_students() -> dict[str, Any]:
        """
        统计 students 表中的学生总数。

        该工具只执行 SELECT 查询，不会修改学生数据。
        """

        try:
            with closing(get_readonly_connection()) as connection:
                row = connection.execute(
                    """
                    SELECT COUNT(*) AS total_students
                    FROM students
                    """
                ).fetchone()

            total_students = int(row["total_students"]) if row else 0

            return {
                "success": True,
                "total_students": total_students,
            }

        except sqlite3.Error as exc:
            raise ToolError(
                f"统计学生数量失败：{exc}"
            ) from exc