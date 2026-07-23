"""Temporary-database self-check for the MCP student tools."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from app.database.schema import initialize_database
from app.services.factory import project_root
from mcp_client.client import call_mcp_tool_async, list_mcp_tools_async

EXPECTED_TOOL_NAMES = {
    "list_students",
    "search_students",
    "get_student_by_id",
    "get_student_by_number",
    "count_students",
    "add_student",
    "update_student",
    "upsert_student",
    "delete_student",
    "batch_delete_students",
}


def capture_database_metadata(database_path: Path) -> dict[str, Any]:
    """Capture lightweight metadata for the production database path."""
    if not database_path.exists():
        return {
            "path": str(database_path),
            "exists": False,
        }

    stat = database_path.stat()
    return {
        "path": str(database_path),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def ensure_unified_result(payload: Any) -> dict[str, Any]:
    """Require the MCP tool payload to match the unified result contract."""
    if not isinstance(payload, dict):
        raise AssertionError("Tool result must be a dictionary")

    expected_keys = {"success", "data", "message", "error", "meta"}
    if set(payload) != expected_keys:
        raise AssertionError(f"Tool result keys must be {sorted(expected_keys)}")
    return payload


def ensure_no_internal_leak(payload: dict[str, Any]) -> None:
    """Check that caller-visible content does not leak internals."""
    rendered = json.dumps(payload, ensure_ascii=False)
    for fragment in [
        "Traceback",
        "sqlite3.",
        "D:\\",
        "site-packages",
        "student-v2-env",
        "SECRET_KEY",
        "OPENAI_API_KEY",
    ]:
        if fragment in rendered:
            raise AssertionError(f"Leaked internal detail: {fragment}")


def redact_student_snapshot(student: dict[str, Any]) -> dict[str, Any]:
    """Return a minimal student snapshot for non-sensitive comparisons."""
    return {
        "id": student["id"],
        "student_number": student["student_number"],
        "year_level": student["year_level"],
        "score": student["score"],
        "updated_at": student["updated_at"],
    }


async def run_self_check() -> int:
    """Run the full MCP self-check against a temporary SQLite database."""
    repo_root = project_root()
    production_database = repo_root / "instance" / "students_v2.db"
    before_metadata = capture_database_metadata(production_database)
    checks: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="student-mcp-self-check-") as temp_dir:
        temp_db_path = Path(temp_dir) / "students_mcp_self_check.db"
        initialize_database(temp_db_path)

        async def list_tools() -> list[dict[str, Any]]:
            return await list_mcp_tools_async(
                database_path=str(temp_db_path),
                cwd=str(repo_root),
            )

        async def call_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
            response = await call_mcp_tool_async(
                tool_name,
                arguments,
                database_path=str(temp_db_path),
                cwd=str(repo_root),
            )
            payload = ensure_unified_result(response["result"])
            ensure_no_internal_leak(payload)
            return payload

        try:
            tools = await list_tools()
            discovered_names = {tool["name"] for tool in tools}
            if discovered_names != EXPECTED_TOOL_NAMES:
                raise AssertionError(
                    f"Expected tools {sorted(EXPECTED_TOOL_NAMES)}, got {sorted(discovered_names)}"
                )
            checks.append({"check": "tool_discovery", "status": "PASS", "details": sorted(discovered_names)})

            baseline_create = await call_tool(
                "add_student",
                {
                    "student_number": "00001",
                    "name": "MCP基线学生",
                    "gender": "男",
                    "age": 20,
                    "major": "计算机",
                    "year_level": "大一",
                    "score": 88,
                    "phone": "10086",
                    "email": "mcp-baseline@example.com",
                },
            )
            if not baseline_create["success"]:
                raise AssertionError("Baseline add_student should succeed")
            baseline_student = baseline_create["data"]
            baseline_id = baseline_student["id"]
            if baseline_student["student_number"] != "00001":
                raise AssertionError("Leading zeros were not preserved in baseline student")
            checks.append({"check": "add_student", "status": "PASS", "details": {"baseline_id": baseline_id}})

            listed = await call_tool("list_students", {})
            if not listed["success"] or listed["meta"]["total"] != 1:
                raise AssertionError("list_students should return one baseline student")
            checks.append({"check": "list_students", "status": "PASS"})

            searched = await call_tool("search_students", {"keyword": "00001"})
            if not searched["success"] or searched["meta"]["total"] != 1:
                raise AssertionError("search_students should find the baseline student")
            checks.append({"check": "search_students", "status": "PASS"})

            by_id = await call_tool("get_student_by_id", {"student_id": baseline_id})
            if not by_id["success"] or by_id["data"]["student_number"] != "00001":
                raise AssertionError("get_student_by_id should return the baseline student")
            checks.append({"check": "get_student_by_id", "status": "PASS"})

            by_number = await call_tool("get_student_by_number", {"student_number": "00001"})
            if not by_number["success"] or by_number["data"]["id"] != baseline_id:
                raise AssertionError("get_student_by_number should preserve leading-zero lookup")
            checks.append({"check": "get_student_by_number", "status": "PASS"})

            counted = await call_tool("count_students", {})
            if not counted["success"] or counted["data"]["total_students"] != 1:
                raise AssertionError("count_students should return 1 after baseline insert")
            checks.append({"check": "count_students", "status": "PASS"})

            updated = await call_tool(
                "update_student",
                {
                    "student_id": baseline_id,
                    "year_level": "大二",
                    "score": 95,
                },
            )
            if not updated["success"] or updated["data"]["year_level"] != "大二" or updated["data"]["score"] != 95:
                raise AssertionError("update_student should update year_level and score")
            checks.append({"check": "update_student", "status": "PASS"})

            before_empty_update = await call_tool("get_student_by_id", {"student_id": baseline_id})
            before_empty_snapshot = redact_student_snapshot(before_empty_update["data"])
            empty_update = await call_tool("update_student", {"student_id": baseline_id})
            if empty_update["success"] or empty_update["error"]["code"] != "validation_error":
                raise AssertionError("update_student with only student_id should return validation_error")
            after_empty_update = await call_tool("get_student_by_id", {"student_id": baseline_id})
            after_empty_snapshot = redact_student_snapshot(after_empty_update["data"])
            if before_empty_snapshot != after_empty_snapshot:
                raise AssertionError("Empty update must not change existing student fields")
            checks.append(
                {
                    "check": "empty_update",
                    "status": "PASS",
                    "details": {
                        "unchanged_fields": sorted(before_empty_snapshot),
                    },
                }
            )

            upsert_created = await call_tool(
                "upsert_student",
                {
                    "student_number": "00002",
                    "name": "MCP新增学生",
                    "year_level": "大三",
                    "score": 80,
                },
            )
            if not upsert_created["success"] or upsert_created["data"]["action"] != "created":
                raise AssertionError("upsert_student should create when student_number is new")
            created_upsert_id = upsert_created["data"]["student"]["id"]
            checks.append({"check": "upsert_student_create", "status": "PASS"})

            upsert_updated = await call_tool(
                "upsert_student",
                {
                    "student_number": "00002",
                    "name": "MCP更新学生",
                    "year_level": "大四",
                    "score": 82,
                },
            )
            updated_student = upsert_updated["data"]["student"]
            if (
                not upsert_updated["success"]
                or upsert_updated["data"]["action"] != "updated"
                or updated_student["id"] != created_upsert_id
                or updated_student["year_level"] != "大四"
            ):
                raise AssertionError("upsert_student should update the existing student")
            checks.append({"check": "upsert_student_update", "status": "PASS"})

            extra_student = await call_tool(
                "add_student",
                {
                    "student_number": "00003",
                    "name": "MCP批量删除学生",
                    "year_level": "大一",
                    "score": 70,
                },
            )
            extra_student_id = extra_student["data"]["id"]

            duplicate = await call_tool(
                "add_student",
                {
                    "student_number": "00001",
                    "name": "重复学号",
                },
            )
            if duplicate["success"] or duplicate["error"]["code"] != "duplicate":
                raise AssertionError("Duplicate student number should map to duplicate")
            checks.append({"check": "duplicate_student_number", "status": "PASS"})

            invalid_age = await call_tool(
                "add_student",
                {
                    "student_number": "00010",
                    "name": "非法年龄",
                    "age": 9,
                },
            )
            if invalid_age["success"] or invalid_age["error"]["code"] != "validation_error":
                raise AssertionError("Invalid age should map to validation_error")
            checks.append({"check": "invalid_age", "status": "PASS"})

            invalid_year_level = await call_tool(
                "add_student",
                {
                    "student_number": "00011",
                    "name": "非法年级",
                    "year_level": "大五",
                },
            )
            if invalid_year_level["success"] or invalid_year_level["error"]["code"] != "validation_error":
                raise AssertionError("Invalid year_level should map to validation_error")
            checks.append({"check": "invalid_year_level", "status": "PASS"})

            invalid_score = await call_tool(
                "add_student",
                {
                    "student_number": "00012",
                    "name": "非法成绩",
                    "score": 101,
                },
            )
            if invalid_score["success"] or invalid_score["error"]["code"] != "validation_error":
                raise AssertionError("Invalid score should map to validation_error")
            checks.append({"check": "invalid_score", "status": "PASS"})

            missing_student = await call_tool("get_student_by_id", {"student_id": 999999})
            if missing_student["success"] or missing_student["error"]["code"] != "not_found":
                raise AssertionError("Missing student lookup should map to not_found")
            checks.append({"check": "not_found", "status": "PASS"})

            batch_deleted = await call_tool(
                "batch_delete_students",
                {
                    "student_ids": [created_upsert_id, created_upsert_id, extra_student_id],
                },
            )
            if (
                not batch_deleted["success"]
                or batch_deleted["data"]["requested_count"] != 2
                or batch_deleted["data"]["deleted_count"] != 2
            ):
                raise AssertionError("batch_delete_students should deduplicate IDs and delete two rows")
            checks.append({"check": "batch_delete_students", "status": "PASS"})

            batch_delete_zero_id = await call_tool(
                "batch_delete_students",
                {
                    "student_ids": [0],
                },
            )
            if batch_delete_zero_id["success"] or batch_delete_zero_id["error"]["code"] != "validation_error":
                raise AssertionError("batch_delete_students should reject zero IDs")
            checks.append({"check": "batch_delete_zero_id", "status": "PASS"})

            batch_delete_negative_id = await call_tool(
                "batch_delete_students",
                {
                    "student_ids": [-1],
                },
            )
            if batch_delete_negative_id["success"] or batch_delete_negative_id["error"]["code"] != "validation_error":
                raise AssertionError("batch_delete_students should reject negative IDs")
            checks.append({"check": "batch_delete_negative_id", "status": "PASS"})

            batch_delete_boolean_id = await call_tool(
                "batch_delete_students",
                {
                    "student_ids": [True],
                },
            )
            if batch_delete_boolean_id["success"] or batch_delete_boolean_id["error"]["code"] != "validation_error":
                raise AssertionError("batch_delete_students should reject boolean IDs")
            checks.append({"check": "batch_delete_boolean_id", "status": "PASS"})

            batch_delete_more_than_50_unique_ids = await call_tool(
                "batch_delete_students",
                {
                    "student_ids": list(range(1, 52)),
                },
            )
            if (
                batch_delete_more_than_50_unique_ids["success"]
                or batch_delete_more_than_50_unique_ids["error"]["code"] != "validation_error"
            ):
                raise AssertionError("batch_delete_students should reject more than 50 unique IDs")
            checks.append({"check": "batch_delete_more_than_50_unique_ids", "status": "PASS"})

            deleted = await call_tool("delete_student", {"student_id": baseline_id})
            if not deleted["success"] or deleted["data"]["id"] != baseline_id:
                raise AssertionError("delete_student should delete the baseline student")
            checks.append({"check": "delete_student", "status": "PASS"})

            final_list = await call_tool("list_students", {})
            if not final_list["success"] or final_list["meta"]["total"] != 0:
                raise AssertionError("Temporary database should be empty after cleanup")
            checks.append({"check": "final_cleanup", "status": "PASS"})

        except Exception as error:  # noqa: BLE001 - self-check must return nonzero on failure
            checks.append({"check": "self_check", "status": "FAIL", "details": str(error)})
            print(
                json.dumps(
                    {
                        "success": False,
                        "temporary_database": str(temp_db_path),
                        "checks": checks,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            after_metadata = capture_database_metadata(production_database)
            if before_metadata != after_metadata:
                print(
                    json.dumps(
                        {
                            "production_database_changed": True,
                            "before": before_metadata,
                            "after": after_metadata,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            return 1

    after_metadata = capture_database_metadata(production_database)
    print(
        json.dumps(
            {
                "success": True,
                "temporary_database_strategy": {
                    "used_temporary_database": True,
                    "production_database_path": str(production_database),
                    "production_database_unchanged": before_metadata == after_metadata,
                },
                "checks": checks,
                "production_database_before": before_metadata,
                "production_database_after": after_metadata,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> None:
    """Run the asynchronous self-check and exit with its status code."""
    raise SystemExit(asyncio.run(run_self_check()))


if __name__ == "__main__":
    main()
