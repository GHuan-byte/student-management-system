## Context

The archived Foundation change established the Flask application factory, centralized configuration, unified JSON responses, error handling, logging, a health endpoint, and a runnable `run.py`. The project now needs its first database-backed feature slice that exercises the intended dependency direction:

`Browser UI -> Flask REST API -> StudentService -> StudentRepository -> SQLite`

This change must stay intentionally small. It adds only basic student CRUD, a simple keyword search, and a minimal browser UI. Automated tests, pagination, sorting, batch actions, authentication, MCP, AI chat, import/export, deployment work, and legacy migration remain out of scope.

## Goals / Non-Goals

**Goals:**
- Add centralized `DATABASE_PATH` configuration that works with the existing application factory and override precedence rules.
- Add explicit SQLite connection and schema initialization without initializing the database during module import.
- Add a Flask CLI command path for manual database initialization with `flask --app run.py init-db`.
- Add a `students` table with the required fields and constraints for a first CRUD slice, using `year_level` for student year and `score` for academic score.
- Add repository and service layers that keep SQL out of routes and keep Flask response objects out of data-access code.
- Add REST API routes that reuse the existing unified JSON helpers and global error handlers.
- Add a basic student management page using Flask templates and vanilla JavaScript ES modules.
- Keep the implementation modular so later pagination, sorting, import/export, MCP, AI chat, and automated tests can be added without rewriting the foundation.
- Document manual initialization, startup, and CRUD verification steps.

**Non-Goals:**
- Pagination, sorting, select-all, batch delete, and advanced list state.
- Authentication, authorization, or session management.
- MCP tools, AI chat features, or legacy database migration.
- Automated testing, pytest infrastructure, or dependency installation automation.
- Creating, activating, diagnosing, or modifying virtual environments.
- Additional third-party runtime dependencies beyond the current Foundation stack, including any new package installation for SQLite support.

## Decisions

### 1. Keep database setup explicit and centralized

The change will add `app/database/connection.py`, `app/database/schema.py`, and `app/cli.py` rather than scattering `sqlite3.connect()` calls across routes or services.

- `app/config.py` will expose `DATABASE_PATH`.
- The development default path will be `<Flask instance path>/students_v2.db`.
- A relative `DATABASE_PATH` supplied by configuration will resolve consistently against the project root.
- Production will require an explicitly configured `DATABASE_PATH`.
- Connection helpers will enable `sqlite3.Row` and `PRAGMA foreign_keys = ON` for every connection.
- Schema creation will happen only through an explicit initialization entry point, not during module import and not implicitly during `create_app()`.
- The manual initialization command will be `flask --app run.py init-db`.
- The command may create the configured database parent directory and missing tables, but it must not delete existing tables or erase existing records.
- Database files or parent directories will not be created during module import, configuration loading, or application creation.

Alternative considered:
- Auto-initialize the database during application startup.
Why rejected:
- It hides write-side effects inside startup, makes failures less explicit, and couples app creation to schema mutation.

### 2. Define dependency injection explicitly at the repository and service boundaries

The CRUD stack will keep construction boundaries explicit so the same service can be used from Flask routes now and from future MCP code later.

- `StudentRepository` will receive a database path or a connection factory explicitly.
- `StudentService` will receive a `StudentRepository` instance explicitly.
- Repository and service modules will not require Flask request context and will not read `current_app` directly.
- Flask routes may resolve dependencies from the configured application, but the core service construction must remain usable outside Flask.

Alternative considered:
- Letting repository and service code read `current_app` directly.
Why rejected:
- It would hard-couple the business layer to Flask context and make reuse from non-Flask entry points unnecessarily difficult.

### 3. Keep the student schema narrow and use SQLite-native constraints where practical

The `students` table will contain only:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `student_number TEXT NOT NULL UNIQUE`
- `name TEXT NOT NULL`
- `gender TEXT nullable`
- `age INTEGER nullable`
- `major TEXT nullable`
- `year_level TEXT nullable`
- `score INTEGER nullable`
- `phone TEXT nullable`
- `email TEXT nullable`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Key rules:
- `student_number` remains `TEXT`, is required, is unique, and must preserve leading zeros.
- `name` is required.
- `year_level` is optional text and may only be `大一`, `大二`, `大三`, or `大四` when supplied.
- `score` is optional integer and represents an academic score in the range `0` to `100` when supplied.
- `age` must be an integer in the range `10` through `100` when supplied.
- Optional blank strings will be normalized consistently before persistence.
- Empty-string `year_level` values will normalize to `null`.
- Empty-string `score` values will normalize to `null`.
- SQLite constraints will enforce `year_level IS NULL OR year_level IN ('大一', '大二', '大三', '大四')`.
- SQLite constraints will enforce `score IS NULL OR score BETWEEN 0 AND 100`.
- SQLite constraints will enforce `age IS NULL OR age BETWEEN 10 AND 100`.
- Timestamps will use UTC ISO 8601 in the format `YYYY-MM-DDTHH:MM:SSZ`.
- Inserts will set both `created_at` and `updated_at`.
- Every successful update will refresh `updated_at` while retaining `created_at`.

Alternative considered:
- Reusing one field to represent both year-level and academic score, or introducing a separate school-year style label field.
Why rejected:
- A combined field would keep the semantics ambiguous, and a school-year style label could be misread as something like `2026-2027`. Splitting the concepts into `year_level` and `score` keeps both the data model and UI language unambiguous.

### 4. Keep SQL and transaction control inside repository/database boundaries

`StudentRepository` will be responsible for all SQL statements and write transactions.

- Read methods will return dictionaries or lists of dictionaries.
- Write methods will commit successful changes and roll back failed changes.
- Repository code will use parameterized SQL only.
- The repository will depend on centralized connection helpers rather than opening ad hoc connections.

Alternative considered:
- Letting services or routes build SQL directly for simple operations.
Why rejected:
- It violates the architecture rules already captured in ADR-001 and would make later testing and reuse harder.

### 5. Put validation, normalization, and domain error translation in StudentService

`StudentService` will sit between the API routes and the repository.

- It will normalize incoming payloads, including consistent handling of optional blank strings.
- It will validate required fields, `year_level`, `score`, and `age`.
- It will reject empty update payloads after normalization.
- It will reject unknown fields.
- It will reject attempts to update `id`, `created_at`, or `updated_at` directly.
- It will translate duplicate student number conflicts into `DuplicateError`.
- It will translate missing rows into `NotFoundError`.
- It will translate invalid inputs into `ValidationError`.

Alternative considered:
- Performing validation directly in Flask routes.
Why rejected:
- It would couple HTTP concerns to business rules and break the planned reuse boundary between interfaces and services.

### 6. Keep the REST API small and aligned with the existing response contract

This change will add:

- `GET /api/students`
- `GET /api/students/<student_id>`
- `POST /api/students`
- `PUT /api/students/<student_id>`
- `DELETE /api/students/<student_id>`

API behavior decisions:
- `GET /api/students` supports an optional basic `keyword` query parameter.
- Basic keyword search covers `student_number`, `name`, `major`, `phone`, and `email`.
- No pagination, sorting, or bulk operations are included.
- Successful responses use the existing unified JSON helpers.
- Error responses rely on the existing global handlers and application exceptions.
- Status mapping will be explicit:
  - `GET /api/students` -> `200`
  - `GET /api/students/<student_id>` -> `200`
  - `POST /api/students` -> `201`
  - `PUT /api/students/<student_id>` -> `200`
  - `DELETE /api/students/<student_id>` -> `200`
  - missing student -> `404 not_found`
  - duplicate `student_number` -> `409 duplicate`
  - invalid payload -> `400 validation_error`
- The allowed editable request fields for create and update will be `student_number`, `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email`.
- `PUT /api/students/<student_id>` will accept a partial JSON object containing at least one allowed editable field.
- Update requests must use a JSON object body, must reject an empty object, must reject unknown fields, must reject direct updates to `id`, `created_at`, and `updated_at`, must validate all supplied values, and must return the updated student.

Alternative considered:
- Adding pagination and sorting now to reduce future rework.
Why rejected:
- The user explicitly deferred those concerns, and adding them now would expand both API and UI complexity beyond the current phase.

### 7. Use a server-rendered page with a focused ES-module client

The browser UI will be intentionally simple:

- `app/routes/pages.py` will serve a student management page at `GET /students`.
- `app/templates/base.html` and `app/templates/students.html` will provide the page shell.
- `app/static/js/students.js` will handle API calls, rendering, search, add, edit, delete, loading state, empty state, and error messages.
- UI labels will be Chinese, while field names and payload keys remain English in code.
- The table view plus create and edit forms will include `student_number`, `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email`.
- The page will label `year_level` as “年级” and `score` as “成绩”.

Alternative considered:
- Building the first UI entirely with server-side form submissions and redirects.
Why rejected:
- The project needs to exercise the REST API directly from the browser, and the planned ES-module pattern already exists in the architecture guidance.

### 8. Keep verification manual and document it clearly

Automated testing is explicitly deferred by this change. Verification will focus on:

- manual database initialization through `flask --app run.py init-db`
- manual app startup
- manual CRUD checks for create, list, search, retrieve by ID, edit, and delete
- manual checks confirming `year_level` accepts only `大一`, `大二`, `大三`, and `大四`
- manual error checks for duplicate student numbers, invalid score, invalid age, invalid year_level, and missing students
- manual timestamp checks confirming `created_at` is retained and `updated_at` changes after edit
- `git diff --check`
- `git status`
- scope review against proposal, design, specs, and tasks

Alternative considered:
- Adding even a minimal pytest smoke suite now.
Why rejected:
- The current project constraints explicitly defer automated testing and environment management to a later change.

## Risks / Trade-offs

- [No automated tests in this change] -> Mitigation: require explicit manual verification steps for database initialization, list, search, create, edit, delete, and scope review.
- [Initialization may fail if the configured parent directory does not exist] -> Mitigation: allow the explicit `init-db` command to create the configured parent directory only during manual initialization.
- [SQLite write concurrency is limited] -> Mitigation: acceptable for this local single-user CRUD phase; revisit only when concurrency becomes a real requirement.
- [Field semantics can drift if UI labels and API field names diverge] -> Mitigation: use `year_level` only for student year, display it as “年级”, use `score` only for academic score, display it as “成绩”, and keep those meanings aligned across specs, tasks, and implementation.
- [Adding UI, API, service, repository, and database in one change is broader than Foundation] -> Mitigation: keep the data model to one table, avoid pagination/sorting/batch features, and reuse the existing Foundation helpers instead of inventing parallel patterns.

## Migration Plan

1. Extend configuration, CLI registration, and blueprint registration so the existing Foundation can expose database-backed student features.
2. Add explicit database initialization support and document the manual `flask --app run.py init-db` command.
3. Add the updated student schema, repository, and service layers with `year_level` and `score` validation before adding API routes.
4. Add the student API and the browser UI after the backend layers are in place, using “年级” for `year_level` and “成绩” for `score`.
5. Verify manually with initialization, startup, list, search, retrieve-by-ID, create, edit, delete, and error-condition flows, including validation for `year_level`, `score`, and timestamp behavior.

Rollback strategy:
- Revert the code change and remove the SQLite file created for this feature if needed.
- No legacy migration or irreversible data transformation is part of this change.

## Open Questions

- None that block planning. If the product later needs free-text year descriptions or school-year semantics such as `2026-2027`, that should be proposed as a separate schema change rather than overloading `year_level`.
