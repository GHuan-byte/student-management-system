# Student Management System V2

Student Management System V2 is a clean rewrite of the original project in
`D:\Python\student-management-system`.

This repository is currently implementing the approved OpenSpec change
`add-mcp-student-tools`, which adds a stdio MCP server, a local MCP client,
and a temporary-database self-check on top of the existing Flask student
management application.

## Current Scope

Implemented in this phase:

- Flask application factory
- Centralized configuration
- SQLite configuration and explicit database initialization
- Unified JSON response helpers
- Application exceptions and global error handling
- Blueprint registration
- Health check endpoint
- Student repository and service layers
- Student CRUD REST API
- Student statistics endpoint
- Dashboard page at `/`
- Student management page with templates and vanilla JavaScript
- Shared navigation and consistent page styling
- Pagination, sorting, current-page select-all, and batch delete
- Logging configuration
- Application entry point
- stdio MCP student tools
- Local MCP client wrappers
- Temporary-database MCP self-check

Still not implemented in this phase:

- Authentication
- AI Chat
- Import or export
- Legacy data migration
- HTTP MCP transport

Complete automated testing is deferred to a later Testing / Final Verification
Change. This phase does not add pytest.

## Requirements

- Python `>=3.12`

## Dependency Notes

- SQLite is part of Python's standard library.
- MCP support uses `mcp>=1.27,<2`.
- Do not install dependencies automatically as part of this Change.
- If the current environment is missing dependencies, install them manually.

Example manual install:

```powershell
pip install -r requirements.txt
```

## Initialize the Database

Initialize the configured SQLite database manually:

```powershell
flask --app run.py init-db
```

The command may create the configured parent directory and any missing tables,
but it does not delete existing tables or erase records.

## Run the Flask Application

Start the application manually:

```powershell
python run.py
```

Optional host and port overrides:

```powershell
python run.py --host 0.0.0.0 --port 5001
```

## MCP Server

This phase adds a stdio-only MCP server. It does not add Streamable HTTP, SSE,
FastAPI, Uvicorn, or any Flask MCP route.

Start the MCP server:

```powershell
python -m mcp_server.server
```

Windows example using the current virtual-environment Python path:

```powershell
D:\Python\student-management-system-v2\student-v2-env\Scripts\python.exe -m mcp_server.server
```

The MCP server uses stdout for protocol messages only. Do not add debug
`print()` output to stdout.

## MCP Client

The local client wrappers live in `mcp_client/client.py` and provide:

- `list_mcp_tools_async()`
- `call_mcp_tool_async(tool_name, arguments)`
- `list_mcp_tools()`
- `call_mcp_tool(tool_name, arguments)`

The sync wrappers must be used only outside an already-running event loop.

## MCP Self-Check

Run the MCP self-check manually:

```powershell
python -m mcp_client.self_check
```

Windows example with the current virtual-environment Python path:

```powershell
D:\Python\student-management-system-v2\student-v2-env\Scripts\python.exe -m mcp_client.self_check
```

The self-check:

- creates a temporary SQLite database
- initializes schema through the approved database initialization logic
- passes the temporary `DATABASE_PATH` to the stdio MCP server
- verifies the full MCP tool set and core validation behavior
- does not modify `instance/students_v2.db`

## DATABASE_PATH

Both Flask and MCP use the same `DATABASE_PATH` resolution rules.

- If `DATABASE_PATH` is unset, development defaults to
  `instance/students_v2.db`
- If `DATABASE_PATH` is relative, it resolves from the project root
- The MCP self-check overrides `DATABASE_PATH` with a temporary SQLite file
- The production-like database and the temporary self-check database are not
  the same thing

## MCP Tool Summary

The stdio MCP server exposes these 10 tools:

- `list_students`
- `search_students`
- `get_student_by_id`
- `get_student_by_number`
- `count_students`
- `add_student`
- `update_student`
- `upsert_student`
- `delete_student`
- `batch_delete_students`

These tools reuse the same approved student model:

- `student_number`
- `name`
- `gender`
- `age`
- `major`
- `year_level`
- `score`
- `phone`
- `email`

`year_level` remains one of `大一` / `大二` / `大三` / `大四`, `score` remains
`0-100`, and leading zeros in `student_number` are preserved.

## MCP Client Config Examples

Codex-style stdio client example:

```json
{
  "command": "D:\\Python\\student-management-system-v2\\student-v2-env\\Scripts\\python.exe",
  "args": ["-m", "mcp_server.server"],
  "cwd": "D:\\Python\\student-management-system-v2",
  "env": {
    "DATABASE_PATH": "instance/students_v2.db"
  }
}
```

Claude Desktop or Claude Code style stdio client example:

```json
{
  "mcpServers": {
    "student-management-v2": {
      "command": "D:\\Python\\student-management-system-v2\\student-v2-env\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "D:\\Python\\student-management-system-v2",
      "env": {
        "DATABASE_PATH": "instance/students_v2.db"
      }
    }
  }
}
```

These are example configurations only. Do not commit real secrets, private API
keys, or runtime database copies to Git.

## Manual Verification

After the application is running, you can still verify the health endpoint:

```powershell
curl http://127.0.0.1:5001/api/health
```

You can also verify the Dashboard and student-management flow manually:

```powershell
curl http://127.0.0.1:5001/api/students
curl http://127.0.0.1:5001/api/students?keyword=test
curl http://127.0.0.1:5001/api/students/stats
```

Open the browser pages:

```text
http://127.0.0.1:5001/
http://127.0.0.1:5001/students
```

Manual acceptance checks for this Change include:

- verify `/` renders an HTML Dashboard
- verify Dashboard navigation between `首页` and `学生管理`
- verify Dashboard loads the student total count and system status
- list students
- search students by keyword
- verify the default page shows no more than 15 students
- verify sorting by approved table headers
- verify current-page select-all and indeterminate checkbox behavior
- verify batch delete removes only the selected visible records through one request
- verify deleting the last records on a page falls back to the previous valid page
- create a student and preserve leading zeros in `student_number`
- retrieve a student by ID
- edit a student and confirm `created_at` stays stable while `updated_at`
  changes
- delete a student
- verify `400 validation_error` for invalid `year_level`, `score`, and `age`
- verify `404 not_found` for a missing student
- verify `409 duplicate` for a duplicate `student_number`
- verify the page shows `year_level` as `年级` and `score` as `成绩`
- verify a stdio MCP client can list all 10 student tools
- verify MCP returns unified structured results and validation errors
- verify `python -m mcp_client.self_check` uses only a temporary database
- verify AI Chat is still not part of this phase

## Project Layout

```text
student-management-system-v2/
|-- app/
|   |-- __init__.py
|   |-- cli.py
|   |-- config.py
|   |-- database/
|   |   |-- __init__.py
|   |   |-- connection.py
|   |   `-- schema.py
|   |-- error_handlers.py
|   |-- logging_config.py
|   |-- repositories/
|   |   |-- __init__.py
|   |   `-- student_repository.py
|   |-- routes/
|   |   |-- __init__.py
|   |   |-- health.py
|   |   |-- pages.py
|   |   `-- students.py
|   |-- services/
|   |   |-- __init__.py
|   |   |-- factory.py
|   |   `-- student_service.py
|   |-- static/
|   |   |-- css/
|   |   |   `-- style.css
|   |   `-- js/
|   |       |-- dashboard.js
|   |       `-- students.js
|   |-- templates/
|   |   |-- _student_form_fields.html
|   |   |-- base.html
|   |   |-- dashboard.html
|   |   `-- students.html
|   `-- utils/
|       |-- __init__.py
|       |-- errors.py
|       `-- response.py
|-- docs/
|-- mcp_client/
|   |-- __init__.py
|   |-- client.py
|   `-- self_check.py
|-- mcp_server/
|   |-- __init__.py
|   |-- dependencies.py
|   |-- result.py
|   |-- server.py
|   `-- student_tools.py
|-- openspec/
|-- .env.example
|-- .gitignore
|-- pyproject.toml
|-- README.md
`-- run.py
```
