## Purpose

Define the stdio MCP contract for the V2 student-management tools. MCP is a
parallel adapter over the approved service and repository layers; it does not
replace the REST API or introduce another transport.

## Requirements

### Requirement: MCP student tools use stdio and approved dependency direction
The system SHALL provide MCP student-management tools over stdio only, and the
dependency direction SHALL remain `MCP Client -> MCP Server / Student Tools ->
StudentService -> StudentRepository -> SQLite`.

#### Scenario: MCP server starts over stdio
- **WHEN** the MCP server is started
- **THEN** it SHALL support a stdio startup flow equivalent to `python -m mcp_server.server`
- **AND** it SHALL NOT require a Flask HTTP request context to serve a tool call
- **AND** stdout SHALL be used only for MCP protocol messages; diagnostics SHALL go to stderr or logging

#### Scenario: MCP tools do not access SQLite directly
- **WHEN** an MCP tool handles a student-management operation
- **THEN** it SHALL call `StudentService`
- **AND** it SHALL NOT execute SQL directly or bypass `StudentService` to access SQLite

#### Scenario: Shared business rules remain centralized
- **WHEN** the system exposes student-management behavior through REST and MCP
- **THEN** both interfaces SHALL reuse the same service-layer validation, normalization, duplicate handling, not-found handling, and student field rules
- **AND** the MCP tool layer SHALL NOT maintain an independent validation flow

### Requirement: MCP dependency construction reuses the V2 database-path rules
The system SHALL construct MCP student-management dependencies without Flask request context while reusing the Flask application's `DATABASE_PATH` resolution rules.

#### Scenario: MCP uses the same database-path resolution contract as Flask
- **WHEN** the MCP server resolves its database path
- **THEN** it SHALL use the same `DATABASE_PATH` configuration rules as Flask
- **AND** it SHALL allow environment-variable or explicit override input
- **AND** it SHALL resolve relative paths consistently with the Flask configuration flow

#### Scenario: MCP startup does not initialize or mutate the database implicitly
- **WHEN** MCP server modules are imported or the server starts
- **THEN** it SHALL NOT create, delete, clear, rebuild, or initialize the configured database automatically
- **AND** initialization SHALL remain an explicit approved action

#### Scenario: MCP components remain framework-independent
- **WHEN** `StudentService` and `StudentRepository` are reused by MCP
- **THEN** they SHALL NOT read `current_app`
- **AND** an MCP dependency builder SHALL construct them explicitly outside Flask request handling

### Requirement: MCP tools expose explicit discovery metadata and input schemas
The system SHALL expose MCP tools with explicit names, descriptions, and input schemas reflecting the approved V2 student contract.

#### Scenario: Tool discovery returns the approved student tool set
- **WHEN** an MCP client lists available tools
- **THEN** it SHALL discover exactly these student tools: `list_students`, `search_students`, `get_student_by_id`, `get_student_by_number`, `count_students`, `add_student`, `update_student`, `upsert_student`, `delete_student`, and `batch_delete_students`

#### Scenario: Tool schemas use approved field names and enums
- **WHEN** a client inspects MCP student-tool input schemas
- **THEN** field names SHALL remain `student_number`, `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email`
- **AND** `year_level` SHALL allow only `大一`, `大二`, `大三`, and `大四`
- **AND** `age` SHALL be in the inclusive range 10 through 100
- **AND** `score` SHALL be in the inclusive range 0 through 100
- **AND** `sort_order` SHALL allow only `asc` and `desc`

#### Scenario: Tool schema validation does not replace service validation
- **WHEN** MCP arguments satisfy the declared schema but violate a business rule
- **THEN** `StudentService` SHALL remain the final source of truth for validation and normalization

### Requirement: MCP list and search tools reuse the approved list contract
The system SHALL expose list and search tools that reuse the approved pagination, safe sorting, search, and count behavior.

#### Scenario: list_students returns paginated students with meta
- **WHEN** an MCP client calls `list_students`
- **THEN** it SHALL support `keyword`, `page`, `page_size`, `sort_by`, and `sort_order`
- **AND** it SHALL reuse StudentService paging and safe sorting rules
- **AND** `data` and `meta` SHALL preserve `page`, `page_size`, `total`, `total_pages`, `sort_by`, and `sort_order`

#### Scenario: search_students requires a nonblank keyword and reuses list logic
- **WHEN** an MCP client calls `search_students`
- **THEN** `keyword` SHALL be required and nonblank
- **AND** it SHALL search only `student_number`, `name`, `major`, `phone`, and `email`
- **AND** it SHALL reuse the `list_students` predicate and pagination logic instead of a separate SQL path

#### Scenario: count_students supports optional keyword counting
- **WHEN** an MCP client calls `count_students`
- **THEN** it SHALL return the SQLite-backed total as `data.total_students`
- **AND** an empty keyword SHALL count all students
- **AND** a nonempty keyword SHALL count only records matching the approved search predicate

### Requirement: MCP read tools preserve current student lookup behavior
The system SHALL expose tools to retrieve a student by internal ID or student number without altering the approved model.

#### Scenario: get_student_by_id validates positive integer IDs
- **WHEN** an MCP client calls `get_student_by_id`
- **THEN** `student_id` SHALL be a positive integer
- **AND** a missing record SHALL return `not_found`

#### Scenario: get_student_by_number preserves leading zeros
- **WHEN** an MCP client calls `get_student_by_number` with a nonblank `student_number`
- **THEN** the lookup SHALL preserve its exact text form, and leading zeros SHALL remain significant
- **AND** a missing record SHALL return `not_found`

### Requirement: MCP write tools reuse current CRUD validation and field rules
The system SHALL expose write tools that reuse approved validation, normalization, field, and timestamp behavior.

#### Scenario: add_student uses the approved editable fields
- **WHEN** an MCP client calls `add_student`
- **THEN** its editable fields SHALL be `student_number`, `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email`
- **AND** it SHALL reuse validation for required fields, `year_level`, `score`, `age`, and duplicate `student_number`

#### Scenario: update_student supports partial updates but protects internal fields
- **WHEN** an MCP client calls `update_student`
- **THEN** it SHALL require `student_id` and allow partial updates using approved editable fields
- **AND** an empty update SHALL return `validation_error`
- **AND** attempts to set `id`, `created_at`, or `updated_at` SHALL be rejected
- **AND** a successful update SHALL preserve `created_at` and refresh `updated_at`

#### Scenario: upsert_student uses student_number as identity
- **WHEN** an MCP client calls `upsert_student`
- **THEN** the service SHALL look up the record by the string `student_number`, preserving leading zeros
- **AND** it SHALL create when no record exists and update when that same student number exists
- **AND** the result SHALL identify the action as `created` or `updated`

#### Scenario: delete_student removes one student by ID
- **WHEN** an MCP client calls `delete_student` with an existing positive `student_id`
- **THEN** it SHALL delete through `StudentService` and return the deleted student in the unified success contract

#### Scenario: batch_delete_students validates and normalizes IDs
- **WHEN** an MCP client calls `batch_delete_students`
- **THEN** `student_ids` SHALL be a nonempty array of positive integers and boolean values SHALL be invalid
- **AND** duplicate IDs SHALL be removed before the repository call
- **AND** at most 50 unique IDs SHALL be accepted
- **AND** `requested_count` SHALL be the number of normalized unique requested IDs
- **AND** `deleted_count` SHALL be the number of rows actually deleted

### Requirement: MCP tools return the unified structured result contract
The system SHALL return structured MCP tool results without depending on Flask `jsonify`.

#### Scenario: Successful MCP tool result uses unified success fields
- **WHEN** an MCP tool succeeds
- **THEN** it SHALL return `success`, `data`, `message`, `error`, and `meta`
- **AND** `success` SHALL be true and `error` SHALL be null

#### Scenario: Known application errors map to approved MCP codes
- **WHEN** `StudentService` raises `ValidationError`, `NotFoundError`, or `DuplicateError`
- **THEN** the MCP result SHALL map them to `validation_error`, `not_found`, and `duplicate` respectively
- **AND** structured error details SHALL be retained where available

#### Scenario: Internal errors are hidden from the caller
- **WHEN** an unexpected exception occurs during an MCP tool call
- **THEN** the result SHALL use `internal_error` and indicate failure
- **AND** it SHALL not expose SQL, paths, tracebacks, exception class names, API keys, or environment secrets
- **AND** detailed diagnostics SHALL be limited to stderr or logging

### Requirement: MCP client supports discovery and invocation
The system SHALL provide a local MCP client module that can start the stdio server, list tools, call tools, and safely interpret returned content.

#### Scenario: Async wrappers own the real session flow
- **WHEN** the local client lists tools or calls a tool asynchronously
- **THEN** it SHALL start the configured stdio server, establish an MCP session, and perform discovery or invocation

#### Scenario: Sync wrappers do not blindly nest asyncio.run
- **WHEN** a caller uses synchronous client wrappers from a running event loop
- **THEN** wrappers SHALL fail clearly or use another explicit safe strategy
- **AND** they SHALL NOT blindly call `asyncio.run()` inside that loop

#### Scenario: Client parses structured and text content safely
- **WHEN** an MCP tool result arrives
- **THEN** the client SHALL support structured and text content
- **AND** it SHALL attempt JSON parsing for JSON text and retain raw text if parsing is not possible

### Requirement: MCP self-check uses a temporary SQLite database
The system SHALL provide a self-check that verifies MCP discovery and student-tool behavior without touching the production database.

#### Scenario: Self-check creates and uses a temporary database
- **WHEN** the self-check starts
- **THEN** it SHALL create a temporary SQLite database and initialize it through the explicit schema-initialization mechanism
- **AND** it SHALL pass its temporary `DATABASE_PATH` to the stdio MCP server

#### Scenario: Self-check verifies tool discovery and core behavior
- **WHEN** self-check runs successfully
- **THEN** it SHALL verify discovery of all approved student tools
- **AND** it SHALL verify leading-zero student numbers, duplicate numbers, invalid `age`, invalid `year_level`, invalid `score`, not-found behavior, and batch-delete deduplication

#### Scenario: Self-check never touches the production database
- **WHEN** self-check completes
- **THEN** it SHALL not modify `instance/students_v2.db`
- **AND** temporary database resources SHALL be eligible for automatic cleanup

### Requirement: MCP documentation and manual verification remain explicit
The system SHALL document MCP dependency, startup, client usage, configuration, and manual verification without automating installation or environment management.

#### Scenario: Documentation explains MCP dependency and startup
- **WHEN** MCP documentation is updated
- **THEN** it SHALL document any required MCP SDK dependency, stdio startup, local client usage, and `DATABASE_PATH` behavior
- **AND** it SHALL not claim that dependencies are installed automatically

#### Scenario: Manual verification covers stdio clients and self-check
- **WHEN** the user manually verifies MCP
- **THEN** the documented acceptance flow SHALL cover discovery, reads, leading-zero preservation, add/update/upsert/delete/batch-delete behavior, structured validation errors, and the self-check's production-database safety
