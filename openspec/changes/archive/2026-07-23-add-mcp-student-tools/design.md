## Context

The current V2 codebase already provides the approved student-management stack:
Flask routes call `StudentService`, `StudentService` calls
`StudentRepository`, and `StudentRepository` owns SQLite access. Pagination,
sorting, count, `get_student_by_number`, batch delete, `year_level`, `score`,
and leading-zero `student_number` behavior already exist in the service and
repository layers. This change must add MCP as a parallel interface without
moving SQL into tools, duplicating validation logic, or introducing Flask
request-context dependencies into the MCP path.

The target transport for this phase is stdio only. MCP messages must use
stdout, while logs must stay on stderr or go through logging. The current local
environment does not report an installed Python `mcp` package, and neither
`pyproject.toml` nor `requirements.txt` currently declares one, so the design
must treat MCP SDK installation as a documented dependency step rather than an
automatic action.

## Goals / Non-Goals

**Goals:**

- Add a complete V2 MCP interface for the approved student-management
  capability in one change, including read and write tools.
- Keep dependency direction as `MCP Client -> MCP Server / Student Tools ->
  StudentService -> StudentRepository -> SQLite`.
- Reuse the same validation, normalization, sorting, search, duplicate
  handling, and not-found behavior already approved for the REST API.
- Keep MCP server startup framework-independent from Flask request context.
- Reuse the same database-path resolution rules as Flask, including environment
  overrides and relative-path finalization.
- Provide structured MCP tool results with the existing `success`, `data`,
  `message`, `error`, and `meta` contract.
- Provide a safe self-check that uses a temporary SQLite database and never
  modifies `instance/students_v2.db`.
- Keep the code modular with separate modules for dependency construction,
  result formatting, tool definitions, server startup, client wrappers, and
  self-check logic.

**Non-Goals:**

- HTTP MCP transport, Streamable HTTP transport, FastAPI, Uvicorn, or any
  browser-facing chat endpoint
- OpenAI tool conversion, model calls, AI Chat, or chat UI integration
- Database schema changes, migration, seed-data import, or production database
  initialization during module import
- Direct SQL inside MCP tools
- Flask UI changes, Dashboard changes, or REST API redesign
- pytest-based automation, Docker, deployment work, or automatic dependency
  installation

## Decisions

### D1. Use a framework-independent dependency builder for MCP

The change will introduce a pure-Python dependency construction path that can
build `StudentRepository` and `StudentService` without `current_app` or Flask
request context. This can live in a small shared factory module such as
`app/services/factory.py` or an equivalent pure-Python helper.

Rationale:

- Flask routes already construct `StudentService` from configuration, but MCP
  needs the same dependency graph without importing Flask request state.
- The database-path resolution must stay aligned with current Flask config
  rules, including `DATABASE_PATH`, relative-path resolution, and explicit
  overrides.

Alternative considered:

- Reading `current_app.config` or spinning up a Flask request context for MCP
  tool calls. Rejected because it breaks the architecture rule that service and
  repository code remain reusable outside Flask request handling.

### D2. Use stdio transport only and keep stdout protocol-safe

The MCP server will start with a command equivalent to
`python -m mcp_server.server` and communicate through stdio only in this
change. Server logs must go to stderr or logging and must never print protocol
noise to stdout.

Rationale:

- The user explicitly scoped this change to stdio.
- Stdio keeps the first MCP integration simple and directly compatible with
  local tool clients.

Alternative considered:

- Adding HTTP transport now. Rejected because it expands scope and creates a
  second transport contract before the stdio contract is stabilized.

### D3. Keep MCP code out of `app/__init__.py` and split the MCP modules

Planned modules:

- `mcp_server/__init__.py`
- `mcp_server/server.py`
- `mcp_server/dependencies.py`
- `mcp_server/student_tools.py`
- `mcp_server/result.py`
- `mcp_client/__init__.py`
- `mcp_client/client.py`
- `mcp_client/self_check.py`

Rationale:

- Tool registration, dependency wiring, result formatting, and client behavior
  are distinct concerns.
- A split structure keeps future transport additions possible without turning
  the first MCP layer into a single giant module.

Alternative considered:

- Placing server setup, tools, and result helpers in one file. Rejected because
  it would duplicate concerns and make later maintenance harder.

### D4. Every MCP tool must call `StudentService`

Read and write tools will delegate to `StudentService`, not to SQLite, not to
repository methods directly, and not to Flask routes. Missing service
capabilities such as `get_student_by_number` or `upsert_student` can be added
to the repository/service layers if needed, but the tool layer will remain a
thin adapter.

Rationale:

- This preserves one set of business rules for REST and MCP.
- It avoids divergence in validation for `year_level`, `score`, protected
  fields, search behavior, pagination, and duplicate handling.

Alternative considered:

- Reusing Flask routes from MCP. Rejected because that adds unnecessary HTTP
  coupling and still does not solve pure-Python reuse.

### D5. Keep MCP results in the existing unified contract

All MCP tools will return a pure-Python structure shaped like:

```json
{
  "success": true,
  "data": null,
  "message": "",
  "error": null,
  "meta": {}
}
```

Failures will keep `success: false` and use structured error codes such as
`validation_error`, `not_found`, and `duplicate`. Internal errors must not
expose SQL text, local paths, secrets, environment values, or traceback
content to the MCP caller.

Rationale:

- This keeps caller expectations aligned with the existing V2 API contract.
- The same error vocabulary can be reused across REST and MCP.

Alternative considered:

- Returning raw SDK content or raw exceptions. Rejected because it would create
  a second inconsistent caller contract and leak implementation details.

### D6. Treat MCP schema validation as an adapter, not a business-rule replacement

Each tool will expose a clear MCP input schema with the approved field names,
types, enums, ranges, and descriptions. The tool schema will constrain obvious
shape errors, but `StudentService` will remain the source of truth for final
validation and normalization.

Rationale:

- Schema-level validation improves tool discovery and AI client usability.
- Service-layer validation is still required for protected fields, partial
  updates, blank-string normalization, duplicate handling, and repository-level
  outcomes.

### D7. Reuse current list/search/sort/count behavior

`list_students` and `search_students` tools will reuse the same service-side
pagination, sorting, whitelist, and search predicate already approved for
`GET /api/students`. `search_students` will require a nonblank keyword and
internally delegate to the same list/search path rather than introducing a new
repository query contract.

Rationale:

- Searchable fields are already defined and implemented as
  `student_number`, `name`, `major`, `phone`, and `email`.
- Reusing the same logic prevents REST/MCP drift.

### D8. Define upsert as service-layer orchestration by student number

`upsert_student` will use `student_number` as the identity key. The service
will first look up the student by `student_number`; if the student exists, it
will update that record using the editable fields except for changing the
identity to another `student_number`; if the student does not exist, it will
create a new record. If a concurrent write causes a uniqueness conflict between
lookup and create, the operation will surface as `DuplicateError` rather than
silently mutating another record.

Rationale:

- This keeps the rule readable and consistent with existing repository methods.
- It avoids introducing raw database-specific UPSERT SQL into the tool layer.

### D9. Make client wrappers async-first and loop-safe

`mcp_client/client.py` will expose:

- `list_mcp_tools_async()`
- `call_mcp_tool_async(tool_name, arguments)`
- `list_mcp_tools()`
- `call_mcp_tool(tool_name, arguments)`

The async wrappers will own the real session flow. The sync wrappers will not
blindly call `asyncio.run()` inside an already-running event loop; they will
raise a clear error or use another explicit safe strategy chosen during
implementation.

Rationale:

- The old project used unconditional `asyncio.run()`, which is fragile in
  embedded or notebook-like callers.
- Async-first design keeps the transport implementation cleaner.

### D10. Self-check must use a temporary database only

`mcp_client/self_check.py` will create a temporary directory, initialize a
temporary SQLite database through the project's explicit schema-init mechanism,
pass the temporary `DATABASE_PATH` into the stdio server environment, perform
safe checks, and exit nonzero on failure. It must never touch
`instance/students_v2.db`.

Rationale:

- The user explicitly prohibited mutation of the production database during
  self-check.
- Temporary-database verification is enough to validate tool discovery,
  validation, duplicate handling, and batch-delete behavior.

## Risks / Trade-offs

- [MCP SDK API drift] -> The local environment does not currently detect the
  Python `mcp` package, so implementation must confirm the exact import and
  session API before coding against it. Recommendation: document a dependency
  such as `mcp>=1.0,<2.0` and verify the installed surface before final code is
  written.
- [Config duplication risk] -> If MCP builds `DATABASE_PATH` differently from
  Flask, the two interfaces could point at different databases. Mitigation:
  centralize non-Flask dependency construction around the same config-finalize
  rules already used by the app factory.
- [Tool/client contract ambiguity] -> Different MCP SDK versions may surface
  tool results through `structuredContent`, text blocks, or mixed content.
  Mitigation: client planning explicitly includes safe parsing for structured
  and text content without assuming one exact response shape.
- [Upsert race window] -> A lookup-then-create flow can still race under
  concurrent writes. Mitigation: preserve unique constraints in SQLite and
  translate resulting integrity failures into `DuplicateError`.
- [Sensitive logging risk] -> Tool failures could accidentally log student or
  path details. Mitigation: keep caller-visible errors generic and keep logs
  minimal, structured, and free of full student payloads, secrets, or db-path
  disclosure.

## Migration Plan

1. Add MCP planning artifacts for the new capability and confirm they do not
   alter the existing student CRUD, Dashboard, or schema contracts.
2. During implementation, add the MCP SDK dependency only if the environment
   still lacks it and document manual installation rather than automating it.
3. Implement shared dependency construction before MCP tool modules so both
   Flask and MCP can resolve the same database path and service graph.
4. Add MCP tools in read-only and write-tool stages while preserving the
   current REST API behavior.
5. Verify MCP behavior through temporary-database self-check and user-run stdio
   client acceptance, without touching the production database.
6. Rollback, if needed, consists of removing the new MCP server/client modules
   and related documentation because this change does not require schema
   migration.

## Open Questions

- Which exact `mcp` package version will be available in the implementation
  environment when coding begins? The planning recommendation is
  `mcp>=1.0,<2.0`, but the final import surface must be confirmed before the
  apply phase.
