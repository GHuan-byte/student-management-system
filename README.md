# Student Management System V2

Student Management System V2 is a clean rewrite of the original project in
`D:\Python\student-management-system`.

This repository is currently implementing the approved OpenSpec change
`bootstrap-v2-foundation`, which is limited to a runnable Flask Foundation.

## Current Scope

Implemented in this phase:

- Flask application factory
- Centralized configuration
- Unified JSON response helpers
- Application exceptions and global error handling
- Blueprint registration
- Health check endpoint
- Logging configuration
- Application entry point

Not implemented in this phase:

- Database
- Repository
- Service
- Authentication
- Student CRUD
- Templates or frontend JavaScript
- MCP
- AI Chat
- Import or export
- Legacy data migration

Complete automated testing is deferred to a later Testing / Final Verification
Change.

## Requirements

- Python `>=3.12`

## Manual Dependency Installation

This Change does not create or manage a virtual environment automatically.
Install dependencies manually in the environment you choose:

```powershell
pip install -e .
```

## Run the Foundation

Start the application manually:

```powershell
python run.py
```

Optional host and port overrides:

```powershell
python run.py --host 0.0.0.0 --port 5001
```

## Manual Health Check

After the application is running, verify the Foundation health endpoint:

```powershell
curl http://127.0.0.1:5001/api/health
```

Expected behavior:

- HTTP status `200`
- Unified JSON response structure
- `data.status` equals `"ok"`

## Project Layout

```text
student-management-system-v2/
|-- app/
|   |-- __init__.py
|   |-- config.py
|   |-- error_handlers.py
|   |-- logging_config.py
|   |-- routes/
|   |   |-- __init__.py
|   |   `-- health.py
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
