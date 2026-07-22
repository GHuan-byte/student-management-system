## 1. Scope and Dependency Check

- [ ] 1.1 Confirm the active branch, current V2 architecture, and existing student CRUD contracts before adding MCP planning or implementation work.
- [ ] 1.2 Check whether the Python `mcp` package is already available in the implementation environment and document a manual dependency recommendation if it is missing.
- [ ] 1.3 Confirm this change will not add schema changes, UI changes, AI Chat, HTTP transport, Excel I/O, migration, pytest, or deployment work.

## 2. Shared Service Construction

- [ ] 2.1 Add a framework-independent dependency builder that can construct `StudentRepository` and `StudentService` without Flask request context.
- [ ] 2.2 Reuse the same `DATABASE_PATH` resolution and relative-path finalization rules already approved for the Flask app.
- [ ] 2.3 Ensure MCP startup does not create, clear, or initialize the database during module import.

## 3. Missing Repository and Service Capability

- [ ] 3.1 Review the current repository and service surface for MCP needs, including `get_student_by_number`, `count_students`, and batch delete reuse.
- [ ] 3.2 Add any missing service-layer methods needed by MCP so tools can stay thin adapters over `StudentService`.
- [ ] 3.3 Add `upsert_student` as a service-layer operation keyed by `student_number` without adding direct SQL to the tool layer.

## 4. MCP Result and Error Mapping

- [ ] 4.1 Add a pure-Python MCP result helper that returns `success`, `data`, `message`, `error`, and `meta` without using Flask `jsonify`.
- [ ] 4.2 Map `ValidationError`, `NotFoundError`, and `DuplicateError` to `validation_error`, `not_found`, and `duplicate`.
- [ ] 4.3 Ensure unexpected exceptions do not leak SQL, file paths, traceback text, secrets, or environment values to MCP callers.

## 5. Read-Only Tools

- [ ] 5.1 Add MCP tool definitions for `list_students`, `search_students`, `get_student_by_id`, `get_student_by_number`, and `count_students`.
- [ ] 5.2 Define MCP input schemas and descriptions for read-only tools, including pagination, sorting, keyword, and year-level related fields where applicable.
- [ ] 5.3 Reuse the approved searchable fields, paging contract, sorting whitelist, and leading-zero student-number behavior from `StudentService`.

## 6. Write Tools

- [ ] 6.1 Add MCP tool definitions for `add_student`, `update_student`, `upsert_student`, `delete_student`, and `batch_delete_students`.
- [ ] 6.2 Reuse the existing student field contract for `student_number`, `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email`.
- [ ] 6.3 Ensure write tools keep partial-update rules, duplicate handling, not-found handling, batch-delete deduplication, and protected-field rejection aligned with `StudentService`.

## 7. MCP Server

- [ ] 7.1 Create the modular `mcp_server` package structure for dependency wiring, tool registration, result helpers, and stdio startup.
- [ ] 7.2 Register the approved MCP student tools without placing MCP logic in `app/__init__.py`.
- [ ] 7.3 Ensure stdout remains protocol-safe and that operational logs go to stderr or logging instead of stdout.

## 8. MCP Client

- [ ] 8.1 Create the `mcp_client` package with async discovery and invocation wrappers.
- [ ] 8.2 Add synchronous convenience wrappers that avoid blindly calling `asyncio.run()` inside an already-running event loop.
- [ ] 8.3 Parse structured content, text content, and JSON-like text safely without assuming one exact MCP SDK response shape.

## 9. Temp-DB Self-Check

- [ ] 9.1 Add `mcp_client/self_check.py` to start the stdio server against a temporary SQLite database only.
- [ ] 9.2 Initialize the temporary database through the project's explicit schema-initialization mechanism instead of touching `instance/students_v2.db`.
- [ ] 9.3 Verify tool discovery plus leading-zero handling, duplicate-number handling, invalid `age`, invalid `year_level`, invalid `score`, not-found behavior, and batch-delete deduplication.

## 10. Config and README

- [ ] 10.1 Update documentation and configuration examples only where needed for MCP dependency notes, stdio startup, `DATABASE_PATH`, self-check behavior, and local client setup.
- [ ] 10.2 Document manual setup examples for Codex and Claude Desktop style stdio clients without adding AI Chat or model-call features.
- [ ] 10.3 Do not automate dependency installation, virtual-environment management, or production database initialization.

## 11. Agent Verification

- [ ] 11.1 Review changed files to confirm MCP tools call `StudentService`, not SQLite directly, and that `StudentService` still depends on `StudentRepository`.
- [ ] 11.2 Verify the MCP change does not alter Dashboard, browser UI, REST API contracts, schema, import/export, authentication, AI Chat, or migration behavior.
- [ ] 11.3 Run `git diff --check` and any minimal non-pytest verification allowed by the change, then summarize the exact commands and outcomes.

## 12. USER Acceptance

- [ ] 12.1 [USER] Manually confirm the documented MCP dependency is installed if the environment did not already provide the `mcp` package.
- [ ] 12.2 [USER] Start the stdio MCP server with the documented command and confirm a client can list the approved student tools.
- [ ] 12.3 [USER] Verify `count_students` returns the real SQLite-backed total for the current V2 database.
- [ ] 12.4 [USER] Verify `get_student_by_number` preserves a leading-zero `student_number`.
- [ ] 12.5 [USER] Verify add, update, upsert, delete, and batch delete work through MCP with the approved student fields `year_level` and `score`.
- [ ] 12.6 [USER] Verify invalid parameters return structured MCP errors instead of raw tracebacks or SQL.
- [ ] 12.7 [USER] Verify the self-check uses a temporary database and does not modify the production database.
- [ ] 12.8 [USER] Verify Codex or another stdio MCP client can connect using the documented project command and configuration examples.
