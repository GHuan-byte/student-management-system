## Why

The Flask Foundation is complete, but the project still lacks a real end-to-end business slice that proves the planned layering from browser UI to REST API, service, repository, and SQLite. This change introduces a narrowly scoped student CRUD flow so the V2 architecture becomes usable without pulling in pagination, authentication, MCP, AI chat, or other later-stage concerns.

## What Changes

- Add database-backed student CRUD planning on top of the existing Flask Foundation.
- Add centralized SQLite configuration, connection management, schema creation, and explicit database initialization for a `students` table through a Flask CLI command.
- Add `StudentRepository` and `StudentService` planning with validation, normalization, duplicate handling, not-found handling, transaction-safe writes, and a unified student field design that uses optional `year_level` and optional `score`.
- Add REST API planning for listing, searching, creating, reading, updating, and deleting students through the existing unified JSON response helpers and global error handlers.
- Add a basic student management page planned with Flask templates and vanilla JavaScript ES modules, using Chinese UI labels, including `year_level` shown as “年级” and `score` shown as “成绩”, while keeping English field names in code.
- Extend Foundation planning where needed so configuration, blueprint registration, and documentation support the database-backed CRUD flow.
- Keep automated testing deferred; this change relies on manual verification only.
- Keep runtime dependencies unchanged: SQLite comes from Python's standard library, no additional package installation is required for this change, `pip` must not be run, and any unexpected dependency discovery must stop the change and be reported.

## Capabilities

### New Capabilities
- `student-data-management`: SQLite-backed student schema, repository, service, REST API, and manual CRUD verification.
- `student-management-ui`: Server-rendered student management page and browser-side CRUD interactions over the REST API.

### Modified Capabilities
- `project-foundation`: Extend `DATABASE_PATH` configuration, CLI registration, blueprint registration, and documentation so the Foundation can host database-backed student CRUD.

## Impact

- Affected code areas: `app/config.py`, `app/__init__.py`, `app/cli.py`, new `app/database/`, `app/repositories/`, `app/services/`, `app/routes/students.py`, `app/routes/pages.py`, `app/templates/`, `app/static/`, `README.md`, `.env.example`, and `.gitignore`.
- Affected APIs: add `GET /api/students`, `GET /api/students/<student_id>`, `POST /api/students`, `PUT /api/students/<student_id>`, `DELETE /api/students/<student_id>`, plus a browser page at `GET /students`.
- Dependencies: no new third-party package is planned; SQLite uses Python's standard library, existing Flask Foundation dependencies remain sufficient, and no extra package installation is required for this change.
