## 1. Configuration and Database

- [x] 1.1 Extend `app/config.py` so student CRUD uses centralized `DATABASE_PATH` configuration while preserving the existing Foundation precedence rules.
- [x] 1.2 Implement `DATABASE_PATH` rules so Development defaults to `<Flask instance path>/students_v2.db`, relative configured paths resolve against the project root, and Production requires an explicit configured database path.
- [x] 1.3 Create `app/database/__init__.py`, `app/database/connection.py`, and `app/database/schema.py` for centralized SQLite connections, `sqlite3.Row`, foreign-key enablement, and explicit database initialization.
- [x] 1.4 Define the `students` table schema with `id INTEGER PRIMARY KEY AUTOINCREMENT`, optional `year_level TEXT`, optional `score INTEGER`, required timestamps, `year_level` constrained to `NULL` or one of `大一`, `大二`, `大三`, `大四`, `score` constrained to `NULL` or `0..100`, and `age` constrained to `NULL` or `10..100`, without initializing the database during module import or `create_app()`.
- [x] 1.5 Create `app/cli.py` with `register_cli_commands(app)` and an `init-db` Flask CLI command that supports `flask --app run.py init-db`, may create the configured database parent directory, may create missing tables, and must not delete existing tables or erase records.
- [x] 1.6 Update the Foundation wiring in `app/__init__.py` only as needed to register the CLI command and expose the new database-backed CRUD blueprints without collapsing logic back into the app factory.

## 2. Repository

- [x] 2.1 Create `app/repositories/__init__.py` and `app/repositories/student_repository.py`.
- [x] 2.2 Implement `StudentRepository` so it receives a database path or connection factory explicitly and does not rely on Flask request context or `current_app`.
- [x] 2.3 Implement repository read methods for `list_students`, `search_students`, `get_student_by_id`, and `get_student_by_number` using parameterized SQL, dictionary-shaped results, and keyword search over `student_number`, `name`, `major`, `phone`, and `email` only.
- [x] 2.4 Implement repository write methods for `add_student`, `update_student`, and `delete_student` with reliable connection cleanup, successful commits, failed-write rollbacks, UTC ISO 8601 timestamps in `YYYY-MM-DDTHH:MM:SSZ`, insert-time creation of both timestamps, and refresh of `updated_at` on every successful update.

## 3. Service

- [x] 3.1 Create `app/services/__init__.py` and `app/services/student_service.py`.
- [x] 3.2 Implement `StudentService` so it receives a `StudentRepository` instance explicitly and remains usable outside Flask.
- [x] 3.3 Implement student payload normalization, including consistent handling of optional blank-string values.
- [x] 3.4 Implement service-layer validation and error translation for required fields, `year_level` limited to `大一`, `大二`, `大三`, `大四`, integer `score` in `0..100`, `age` in `10..100`, empty update payloads, duplicate student numbers, missing records, unknown fields, and protected fields `id`, `created_at`, and `updated_at`.
- [x] 3.5 Normalize empty-string `year_level` and `score` values to `null`, and keep the allowed editable fields limited to `student_number`, `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email`.

## 4. REST API

- [x] 4.1 Create `app/routes/students.py` and register it through the centralized blueprint integration point.
- [x] 4.2 Resolve route dependencies from the configured Flask application while keeping repository and service construction independent from request context.
- [x] 4.3 Implement `GET /api/students` and `GET /api/students/<student_id>` so routes call `StudentService` rather than SQLite directly and return unified JSON responses with status `200`.
- [x] 4.4 Implement `POST /api/students` with unified JSON responses and status `201`, preserving leading zeros in `student_number`.
- [x] 4.5 Implement `POST` and `PUT` request handling so the editable payload fields are limited to `student_number`, `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email`.
- [x] 4.6 Implement `PUT /api/students/<student_id>` as a partial JSON-object update that requires at least one allowed editable field, validates all supplied values, rejects unknown or protected fields, and returns the updated student with status `200`.
- [x] 4.7 Keep search scope limited to `student_number`, `name`, `major`, `phone`, and `email`, without adding search over `year_level` or `score`, pagination, or sorting.
- [x] 4.8 Implement page-facing API documentation and route behavior so `year_level` remains the year field and `score` remains the score field throughout the JSON contract.
- [x] 4.9 Implement `DELETE /api/students/<student_id>` with a unified JSON success response and status `200`, and preserve the existing global error-handling flow for `404 not_found`, `409 duplicate`, and `400 validation_error`.

## 5. Templates and JavaScript

- [x] 5.1 Create `app/routes/pages.py`, `app/templates/base.html`, `app/templates/students.html`, `app/static/css/style.css`, and `app/static/js/students.js`.
- [x] 5.2 Render a student management page at `GET /students` with Chinese UI labels, English field names in code, and visible loading, empty, and error states.
- [x] 5.3 Use the fields `student_number`, `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email` in the table and the reusable create/edit modal, showing `year_level` as “年级” and `score` as “成绩”.
- [x] 5.4 Implement browser-side list, keyword search, add, edit, and delete behavior through a vanilla JavaScript ES module that calls the REST API.
- [x] 5.5 Render `GET /students` so the full student page is visible first, with the reusable modal and backdrop hidden by default on initial load and after refresh.
- [x] 5.6 Use page-level trigger buttons so only `新增学生` opens the reusable modal in create mode and only a row-level `编辑` action opens it in edit mode, instead of permanently expanded inline create and edit forms.
- [x] 5.7 Prefill edit mode with the current student data, keep the reusable modal closed during page load, refresh, list loading, and empty-state rendering, close it after a successful submission, refresh the visible list after success, and support explicit cancel or close behavior.
- [x] 5.8 Update `README.md` and `.env.example` with manual database initialization, application startup, and manual CRUD verification instructions, explicitly stating that SQLite is part of Python, no additional package installation is required for this change, `pip` must not be run for this change, and any unexpected dependency discovery must stop and be reported.
- [x] 5.9 Ensure `*.egg-info/` remains ignored and is not committed.

## 6. Manual Verification

### Agent Checks

- [x] 6.1 Review changed and untracked files to confirm the implementation stays scoped to configuration/database, repository, service, REST API, templates, and JavaScript only.
- [x] 6.2 Run `git diff --check`.
- [x] 6.3 Run `git status`.
- [x] 6.4 Summarize the manual commands the user must run for `flask --app run.py init-db`, application startup, and CRUD verification, explicitly noting that SQLite is part of Python, no additional package installation is required for this change, and that `pip`, `pytest`, and virtual-environment management commands must not be run as part of this change.

### User Acceptance

- [x] 6.5 [USER] Initialize the SQLite database using the documented manual command.
- [x] 6.6 [USER] Start the application with `python run.py`.
- [x] 6.7 [USER] Open `/students` and confirm the initial load shows either the current student list or the empty state with Chinese UI labels.
- [x] 6.8 [USER] Open the create modal, create a student, and confirm the UI and API preserve leading zeros in `student_number`.
- [x] 6.9 [USER] Search for a student by keyword and confirm the displayed list updates from the API response.
- [x] 6.10 [USER] Retrieve a student by ID and confirm `GET /api/students/<student_id>` returns HTTP `200` with the unified JSON structure.
- [x] 6.11 [USER] Submit a duplicate `student_number` and confirm the API returns HTTP `409` with code `duplicate`.
- [x] 6.12 [USER] Submit an invalid `year_level` outside `大一`, `大二`, `大三`, `大四` and confirm the API returns HTTP `400` with code `validation_error`.
- [x] 6.13 [USER] Submit a `score` outside `0..100` or a non-integer `score` and confirm the API returns HTTP `400` with code `validation_error`.
- [x] 6.14 [USER] Submit an invalid `age` outside `10..100` or a non-integer age and confirm the API returns HTTP `400` with code `validation_error`.
- [x] 6.15 [USER] Request, update, or delete a missing student and confirm the API returns HTTP `404` with code `not_found`.
- [x] 6.16 [USER] Open the edit modal, edit a student, and confirm validation behaves correctly, `created_at` is retained, and `updated_at` changes after the successful update.
- [x] 6.17 [USER] Verify the page shows `year_level` as “年级” and `score` as “成绩” in the table and modal forms.
- [x] 6.18 [USER] Verify the create and edit modals can both be cancelled or closed without submitting a mutation request.
- [x] 6.19 [USER] Refresh or reopen `/students` and confirm the page starts with the reusable modal closed and the student management page visible.
- [x] 6.20 [USER] Delete a student and confirm the record is removed from the UI and subsequent API results.
