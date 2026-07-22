## Why

The current V2 application already has a usable Flask UI, REST API, service
layer, and SQLite-backed repository, but it does not yet expose the same
student-management capability through MCP. This change is needed now to add a
stdio-based MCP interface that reuses the approved V2 business rules instead of
reintroducing duplicate validation, direct SQL access, or old-project coupling.

## What Changes

- Add a new stdio-only MCP server layer for student-management tools.
- Add MCP tool definitions for list, search, get-by-id, get-by-number, count,
  add, update, upsert, delete, and batch delete.
- Add framework-independent dependency construction so MCP and Flask can reuse
  the same `StudentService` and `StudentRepository` flow.
- Add a pure-Python MCP result and error-mapping helper that preserves the
  existing unified response contract without relying on Flask `jsonify`.
- Add an MCP client module with async and sync wrappers for tool discovery and
  tool invocation.
- Add a non-pytest self-check that starts the MCP server over stdio with a
  temporary SQLite database and verifies discovery, validation, and write-tool
  behavior without touching the production database.
- Update documentation and dependency notes only as needed for MCP startup,
  configuration, and manual verification.

## Capabilities

### New Capabilities
- `mcp-student-tools`: stdio MCP server, client, tool contract, shared service
  reuse, structured tool results, and temporary-database self-check for the V2
  student-management system

### Modified Capabilities
- None.

## Impact

- Affected code areas: `app/services/`, `app/repositories/`, new `mcp_server/`
  and `mcp_client/` packages, and related configuration/documentation files
- Affected systems: local stdio MCP clients such as Codex or Claude Desktop
- API/behavior impact: no database schema change, no UI change, no REST API
  contract change; MCP adds a parallel interface that must reuse the same V2
  rules for `year_level`, `score`, leading-zero `student_number`, CRUD,
  pagination, sorting, and batch deletion
- Dependency impact: the local planning review did not detect an installed
  Python `mcp` package, so implementation may require adding an MCP SDK
  dependency such as `mcp>=1.0,<2.0` after verifying the exact API surface to
  target
