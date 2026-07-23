## ADDED Requirements

### Requirement: MCP student tools use stdio and approved dependency direction
The system SHALL provide MCP student-management tools over stdio only, and the
dependency direction SHALL remain `MCP Client -> MCP Server / Student Tools ->
StudentService -> StudentRepository -> SQLite`.

#### Scenario: MCP server starts over stdio
- **WHEN** the MCP server is started for this change
- **THEN** it SHALL support a stdio startup flow equivalent to
  `python -m mcp_server.server`
- **AND** it SHALL NOT require a Flask HTTP request context to serve a tool
  call

#### Scenario: MCP tools do not access SQLite directly
- **WHEN** an MCP tool handles a student-management operation
- **THEN** it SHALL call `StudentService`
- **AND** it SHALL NOT execute SQL directly
- **AND** it SHALL NOT bypass `StudentService` by calling SQLite from the tool
  layer

#### Scenario: Shared business rules remain centralized
- **WHEN** the system exposes student-management behavior through both REST and
  MCP
- **THEN** the two interfaces SHALL reuse the same service-layer validation,
  normalization, duplicate handling, not-found handling, and student field
  rules
- **AND** the system SHALL NOT maintain a second independent validation flow in
  the MCP tool layer

### Requirement: MCP dependency construction reuses the V2 database-path rules
The system SHALL construct MCP student-management dependencies without Flask
request context while reusing the same database-path resolution rules approved
for the Flask app.

#### Scenario: MCP uses the same database-path resolution contract as Flask
- **WHEN** the MCP server resolves its database path
- **THEN** it SHALL use the same `DATABASE_PATH` configuration rules as the
  current Flask application
- **AND** it SHALL allow environment-variable or explicit override input
- **AND** it SHALL resolve relative database paths consistently with the Flask
  configuration flow

#### Scenario: MCP startup does not initialize or mutate the database implicitly
- **WHEN** the MCP server modules are imported or the server process starts
- **THEN** the system SHALL NOT create, delete, clear, rebuild, or initialize
  the configured database automatically
- **AND** database initialization SHALL remain an explicit action through the
  project's approved initialization mechanism

#### Scenario: MCP components remain framework-independent
- **WHEN** `StudentService` and `StudentRepository` are reused by the MCP path
- **THEN** they SHALL NOT read `current_app`
- **AND** the MCP dependency builder SHALL create them explicitly outside Flask
  request handling

### Requirement: MCP tools expose explicit discovery metadata and input schemas
The system SHALL expose MCP tools with explicit names, descriptions, and input
schemas that reflect the approved V2 student contract.

#### Scenario: Tool discovery returns approved student tool set
- **WHEN** an MCP client lists available tools
- **THEN** it SHALL discover tools for `list_students`, `search_students`,
  `get_student_by_id`, `get_student_by_number`, `count_students`, `add_student`,
  `update_student`, `upsert_student`, `delete_student`, and
  `batch_delete_students`

#### Scenario: Tool schemas use approved field names and enums
- **WHEN** a client inspects the input schema for MCP student tools
- **THEN** Python, SQLite, and JSON field names SHALL remain `student_number`,
  `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, and
  `email`
- **AND** `year_level` SHALL use the allowed values `大一`, `大二`, `大三`, and
  `大四`
- **AND** `sort_order` SHALL allow only `asc` and `desc`

#### Scenario: Tool schema validation does not replace service validation
- **WHEN** an MCP tool receives arguments that satisfy the declared schema but
  still violate business rules
- **THEN** the service layer SHALL remain the final source of truth for
  validation and normalization

### Requirement: MCP list and search tools reuse the approved list contract
The system SHALL expose list and search tools that reuse the approved V2
pagination, search, sorting, and count behavior.

#### Scenario: list_students returns paginated students with meta
- **WHEN** an MCP client calls `list_students`
- **THEN** the tool SHALL support `keyword`, `page`, `page_size`, `sort_by`,
  and `sort_order`
- **AND** it SHALL reuse the current StudentService paging and sorting rules
- **AND** the tool result `data` and `meta` SHALL preserve `page`, `page_size`,
  `total`, `total_pages`, `sort_by`, and `sort_order`

#### Scenario: search_students requires a nonblank keyword and reuses list logic
- **WHEN** an MCP client calls `search_students`
- **THEN** `keyword` SHALL be required and nonblank
- **AND** the tool SHALL search only the approved searchable fields
  `student_number`, `name`, `major`, `phone`, and `email`
- **AND** it SHALL reuse the same list/search predicate and pagination logic as
  `list_students` instead of adding a separate SQL path

#### Scenario: count_students supports optional keyword counting
- **WHEN** an MCP client calls `count_students`
- **THEN** the tool SHALL return the SQLite-backed total as
  `data.total_students`
- **AND** an empty keyword SHALL mean the total count of all students
- **AND** a nonempty keyword SHALL count only records matching the approved
  search predicate

### Requirement: MCP read tools preserve current student lookup behavior
The system SHALL expose read tools for retrieving a student by internal ID or
by student number without altering the approved student model.

#### Scenario: get_student_by_id validates positive integer IDs
- **WHEN** an MCP client calls `get_student_by_id`
- **THEN** `student_id` SHALL be a positive integer
- **AND** the tool SHALL return `not_found` when the record does not exist

#### Scenario: get_student_by_number preserves leading zeros
- **WHEN** an MCP client calls `get_student_by_number` with a nonblank
  `student_number`
- **THEN** the lookup SHALL preserve the exact text form of the student number
- **AND** leading zeros SHALL remain significant
- **AND** the tool SHALL return `not_found` when no matching student exists

### Requirement: MCP write tools reuse current CRUD validation and field rules
The system SHALL expose write tools that reuse the approved student field
contract, validation, normalization, and timestamp behavior.

#### Scenario: add_student uses the approved editable fields
- **WHEN** an MCP client calls `add_student`
- **THEN** the allowed editable fields SHALL be `student_number`, `name`,
  `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email`
- **AND** the tool SHALL reuse current create validation for required fields,
  `year_level`, `score`, `age`, and duplicate `student_number`

#### Scenario: update_student supports partial updates but protects internal fields
- **WHEN** an MCP client calls `update_student`
- **THEN** the tool SHALL require `student_id`
- **AND** it SHALL allow partial updates using the approved editable fields
- **AND** it SHALL reject empty update payloads
- **AND** it SHALL reject attempts to set `id`, `created_at`, or `updated_at`
- **AND** a successful update SHALL preserve `created_at` and refresh
  `updated_at`

#### Scenario: upsert_student uses student_number as identity
- **WHEN** an MCP client calls `upsert_student`
- **THEN** the service SHALL look up the record by `student_number`
- **AND** it SHALL create a new student when no record exists
- **AND** it SHALL update the existing student when that same student number
  already exists
- **AND** the result SHALL identify whether the action was `created` or
  `updated`

#### Scenario: delete_student removes one student by ID
- **WHEN** an MCP client calls `delete_student` with an existing positive
  `student_id`
- **THEN** the tool SHALL delete that record through `StudentService`
- **AND** it SHALL return the deleted student in the unified success contract

#### Scenario: batch_delete_students validates and normalizes IDs
- **WHEN** an MCP client calls `batch_delete_students`
- **THEN** `student_ids` SHALL be a non-empty array of positive integers
- **AND** boolean values SHALL be invalid
- **AND** duplicate IDs SHALL be normalized before the repository call
- **AND** the request SHALL allow at most `50` unique IDs
- **AND** the tool result SHALL return `requested_count` and `deleted_count`

### Requirement: MCP tools return the unified structured result contract
The system SHALL return structured MCP tool results that mirror the existing V2
response contract without depending on Flask `jsonify`.

#### Scenario: Successful MCP tool result uses unified success fields
- **WHEN** an MCP tool succeeds
- **THEN** it SHALL return `success`, `data`, `message`, `error`, and `meta`
- **AND** `error` SHALL be `null`

#### Scenario: Known application errors map to approved MCP codes
- **WHEN** `StudentService` raises `ValidationError`, `NotFoundError`, or
  `DuplicateError`
- **THEN** the MCP result SHALL use error codes `validation_error`,
  `not_found`, and `duplicate` respectively
- **AND** the tool SHALL preserve structured error details where available

#### Scenario: Internal errors are hidden from the caller
- **WHEN** an unexpected exception occurs during an MCP tool call
- **THEN** the caller-visible result SHALL indicate failure without exposing SQL
  text, local file paths, traceback text, exception class names, API keys, or
  environment secrets
- **AND** detailed diagnostic information SHALL remain limited to stderr or
  logging

### Requirement: MCP client supports discovery and invocation
The system SHALL provide a local MCP client module that can start the project's
stdio server, list tools, call tools, and safely interpret returned content.

#### Scenario: Async wrappers own the real session flow
- **WHEN** the local client lists tools or calls a tool asynchronously
- **THEN** it SHALL start the configured stdio server process
- **AND** it SHALL establish the MCP client session and perform the requested
  discovery or invocation flow

#### Scenario: Sync wrappers do not blindly nest asyncio.run
- **WHEN** a caller uses the synchronous client wrappers from a running event
  loop
- **THEN** the wrappers SHALL fail clearly or use another explicit safe
  strategy
- **AND** they SHALL NOT blindly call `asyncio.run()` inside that running loop

#### Scenario: Client parses structured and text content safely
- **WHEN** an MCP tool result arrives
- **THEN** the client SHALL support structured content and text content
- **AND** it SHALL safely attempt JSON parsing for JSON text results
- **AND** it SHALL retain raw text when parsing is not possible

### Requirement: MCP self-check uses a temporary SQLite database
The system SHALL provide a self-check flow that verifies MCP discovery and
student-tool behavior without touching the production database.

#### Scenario: Self-check creates and uses a temporary database
- **WHEN** the self-check starts
- **THEN** it SHALL create a temporary SQLite database
- **AND** it SHALL initialize that database through the project's explicit
  schema-initialization mechanism
- **AND** it SHALL pass the temporary `DATABASE_PATH` to the stdio MCP server

#### Scenario: Self-check verifies tool discovery and core behavior
- **WHEN** the self-check runs successfully
- **THEN** it SHALL verify discovery of the approved MCP student tools
- **AND** it SHALL verify leading-zero `student_number` handling
- **AND** it SHALL verify duplicate-number handling, invalid `age`, invalid
  `year_level`, invalid `score`, not-found behavior, and batch-delete
  deduplication

#### Scenario: Self-check never touches the production database
- **WHEN** the self-check completes
- **THEN** it SHALL not modify `instance/students_v2.db`
- **AND** it SHALL allow its temporary database resources to be cleaned up
  automatically

### Requirement: MCP documentation and manual verification remain explicit
The system SHALL document MCP dependency, startup, client usage, configuration,
and manual verification without automating installation or virtual-environment
management.

#### Scenario: Documentation explains MCP dependency and startup
- **WHEN** the project documentation is updated for this change
- **THEN** it SHALL document the required MCP SDK dependency if the environment
  does not already provide it
- **AND** it SHALL explain stdio server startup, local client usage, and
  `DATABASE_PATH` behavior
- **AND** it SHALL not claim that dependencies are installed automatically

#### Scenario: Manual verification covers stdio clients and self-check
- **WHEN** the user performs manual verification for this change
- **THEN** the documented acceptance flow SHALL cover listing tools, reading
  students, preserving leading zeros, add/update/upsert/delete/batch-delete
  behavior, structured validation errors, and safe self-check behavior without
  production-database modification
