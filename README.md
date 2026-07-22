# Student Management System V2

Student Management System V2 is a clean rewrite of the original project in
`D:\Python\student-management-system`.

This repository is currently implementing the approved OpenSpec change
`build-student-crud`, which adds a basic end-to-end student CRUD flow on top of
the Flask Foundation.

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
- Student management page with templates and vanilla JavaScript
- Logging configuration
- Application entry point

Not implemented in this phase:

- Authentication
- Pagination
- Sorting
- Select-all
- Batch delete
- MCP
- AI Chat
- Import or export
- Legacy data migration

Complete automated testing is deferred to a later Testing / Final Verification
Change.

## Requirements

- Python `>=3.12`

## Dependency Notes

- SQLite is part of Python's standard library.
- No additional package installation is required for `build-student-crud`.
- Do not run `pip` as part of this Change.
- If an unexpected dependency is discovered, stop and report it before
  continuing.

## Initialize the Database

Initialize the configured SQLite database manually:

```powershell
flask --app run.py init-db
```

The command may create the configured parent directory and any missing tables,
but it does not delete existing tables or erase records.

## Run the Application

Start the application manually:

```powershell
python run.py
```

Optional host and port overrides:

```powershell
python run.py --host 0.0.0.0 --port 5001
```

## Manual Verification

After the application is running, you can still verify the Foundation health
endpoint:

```powershell
curl http://127.0.0.1:5001/api/health
```

You can also verify the student CRUD flow manually:

```powershell
curl http://127.0.0.1:5001/api/students
curl http://127.0.0.1:5001/api/students?keyword=test
```

Open the browser page:

```text
http://127.0.0.1:5001/students
```

Manual acceptance checks for this Change include:

- list students
- search students by keyword
- create a student and preserve leading zeros in `student_number`
- retrieve a student by ID
- edit a student and confirm `created_at` stays stable while `updated_at`
  changes
- delete a student
- verify `400 validation_error` for invalid `year_level`, `score`, and `age`
- verify `404 not_found` for a missing student
- verify `409 duplicate` for a duplicate `student_number`
- verify the page shows `year_level` as `年级` and `score` as `成绩`

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
|   |   `-- student_service.py
|   |-- static/
|   |   |-- css/
|   |   |   `-- style.css
|   |   `-- js/
|   |       `-- students.js
|   |-- templates/
|   |   |-- _student_form_fields.html
|   |   |-- base.html
|   |   `-- students.html
|   `-- utils/
|       |-- __init__.py
|       |-- errors.py
|       `-- response.py
|-- docs/
|-- openspec/
|-- .env.example
|-- .gitignore
|-- pyproject.toml
|-- README.md
`-- run.py
```
