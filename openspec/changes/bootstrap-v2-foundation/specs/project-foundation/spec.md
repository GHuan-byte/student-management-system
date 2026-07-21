## ADDED Requirements

### Requirement: Application factory
The system SHALL provide a `create_app(config_name=None, config_overrides=None, load_env=True)` application factory that creates and returns a configured Flask application instance.

#### Scenario: Create app with development default
- **WHEN** `create_app()` is called without arguments and `APP_ENV` is not set
- **THEN** it SHALL return a Flask application instance configured with DevelopmentConfig

#### Scenario: Create app via APP_ENV
- **WHEN** `create_app()` is called without `config_name` and `APP_ENV=testing` is set
- **THEN** it SHALL use `APP_ENV` to select TestingConfig

#### Scenario: Explicit config_name overrides APP_ENV
- **WHEN** `create_app("development")` is called and `APP_ENV=production` is set
- **THEN** it SHALL use DevelopmentConfig regardless of `APP_ENV`

#### Scenario: Production via APP_ENV
- **WHEN** `create_app()` is called without `config_name` and `APP_ENV=production` is set
- **THEN** it SHALL return a Flask application instance configured with ProductionConfig

#### Scenario: Invalid config_name raises ValueError
- **WHEN** `create_app("invalid")` is called
- **THEN** a `ValueError` SHALL be raised

#### Scenario: Testing with load_env=False
- **WHEN** `create_app("testing", load_env=False)` is called
- **THEN** it SHALL NOT load the `.env` file

#### Scenario: config_overrides take highest precedence
- **WHEN** `create_app("development", config_overrides={"TEST_KEY": "override"})` is called
- **THEN** `app.config["TEST_KEY"]` SHALL equal `"override"`, taking precedence over all other config sources

---

### Requirement: Configuration boundaries
The system SHALL define three configuration classes: `DevelopmentConfig`, `TestingConfig`, and `ProductionConfig`, all inheriting from a base `Config` class.

#### Scenario: Development configuration
- **WHEN** DevelopmentConfig is used
- **THEN** `DEBUG` SHALL be `True`

#### Scenario: Testing configuration
- **WHEN** TestingConfig is used
- **THEN** `TESTING` SHALL be `True`

#### Scenario: Production SECRET_KEY validation
- **WHEN** ProductionConfig is used
- **THEN** the system SHALL raise a `RuntimeError` on startup if `SECRET_KEY` is not set or equals the development default value

#### Scenario: Production SECRET_KEY via config_overrides
- **WHEN** ProductionConfig is used and `SECRET_KEY` is provided via `config_overrides`
- **THEN** the application SHALL start normally without raising `RuntimeError`

#### Scenario: Development SECRET_KEY default
- **WHEN** DevelopmentConfig is used
- **THEN** `SECRET_KEY` SHALL have a non-production default value that allows the application to start

#### Scenario: Foundation startup without DATABASE_PATH
- **WHEN** the application starts without `DATABASE_PATH` set
- **THEN** it SHALL NOT fail, because database configuration is not required in the Foundation phase

---

### Requirement: Environment variable loading
The system SHALL load environment variables from a `.env` file using `python-dotenv` before environment-related configuration values are parsed and applied.

#### Scenario: .env loaded before config parsing
- **WHEN** `create_app()` is called with `load_env=True`
- **THEN** `load_dotenv()` SHALL be called before environment-related config values are parsed and applied from the environment

#### Scenario: System environment overrides .env
- **WHEN** both the system environment and `.env` file define `SECRET_KEY`
- **THEN** the system environment variable SHALL be used, because `load_dotenv()` does not override existing environment variables

#### Scenario: Test isolation from .env
- **WHEN** `create_app("testing", load_env=False)` is called
- **THEN** the `.env` file SHALL NOT be loaded, preventing local environment pollution

#### Scenario: config_overrides after config merge, before final validation
- **WHEN** both `.env` file and `config_overrides` define the same key
- **THEN** the value from `config_overrides` SHALL be used, because `config_overrides` is applied after the config merge and before the final validation step

---

### Requirement: Unified JSON response
The system SHALL provide helper functions that return a consistent JSON response structure: `{"success": bool, "data": any, "message": str, "error": null|dict, "meta": dict}`.

#### Scenario: Successful 200 response
- **WHEN** `api_success(data={"key": "value"}, message="OK")` is called
- **THEN** the response SHALL have status 200 with body `{"success": true, "data": {"key": "value"}, "message": "OK", "error": null, "meta": {}}`

#### Scenario: Successful 201 response
- **WHEN** `api_success(data={"id": 1}, message="Created", status_code=201)` is called
- **THEN** the response SHALL have status 201

#### Scenario: Error response with code
- **WHEN** `api_error(message="Not found", error={"code": "not_found", "details": None}, status_code=404)` is called
- **THEN** the response SHALL have status 404 with `{"success": false, "data": null, "message": "Not found", "error": {"code": "not_found", "details": null}, "meta": {}}`

#### Scenario: Paginated response with data
- **WHEN** `api_paginated(data=["a"], total=50, page=1, page_size=15)` is called
- **THEN** the response SHALL include `meta` with `{"page": 1, "page_size": 15, "total": 50, "total_pages": 4}`

#### Scenario: Paginated response with total zero
- **WHEN** `api_paginated(data=[], total=0, page=1, page_size=15)` is called
- **THEN** `meta` SHALL contain `{"page": 1, "page_size": 15, "total": 0, "total_pages": 0}`

#### Scenario: Invalid page_size raises ValueError
- **WHEN** `api_paginated(data=[], total=0, page=1, page_size=0)` or `page_size=-1` is called
- **THEN** a `ValueError` SHALL be raised

#### Scenario: Error code field structure
- **WHEN** an error response is created
- **THEN** the `error` field SHALL be an object with `code` (string) and `details` (nullable), and SHALL NOT contain a raw Python Exception object

---

### Requirement: Application exceptions
The system SHALL define a hierarchy of application exceptions: `AppError` as base, with `NotFoundError`, `ValidationError`, `DuplicateError`, and `ForbiddenError` subclasses. Each exception SHALL carry a `code`, `message`, `status_code`, and `details` (defaulting to `None`).

#### Scenario: AppError has details attribute
- **WHEN** `AppError("Something went wrong")` is created
- **THEN** its `details` SHALL default to `None`

#### Scenario: NotFoundError properties
- **WHEN** `NotFoundError("Student not found")` is raised
- **THEN** its `status_code` SHALL be 404 and `code` SHALL be `"not_found"`

#### Scenario: ValidationError properties
- **WHEN** `ValidationError("Invalid age")` is raised
- **THEN** its `status_code` SHALL be 400 and `code` SHALL be `"validation_error"`

#### Scenario: DuplicateError properties
- **WHEN** `DuplicateError("Student number exists")` is raised
- **THEN** its `status_code` SHALL be 409 and `code` SHALL be `"duplicate"`

#### Scenario: ForbiddenError properties
- **WHEN** `ForbiddenError("Admin only")` is raised
- **THEN** its `status_code` SHALL be 403 and `code` SHALL be `"forbidden"`

---

### Requirement: Global error handling
The system SHALL register three global error handlers to cover `AppError`, `werkzeug.exceptions.HTTPException`, and unexpected `Exception`. All error responses SHALL use the full unified structure including `success`, `data`, `message`, `error`, and `meta`.

#### Scenario: AppError returns unified error response
- **WHEN** a `NotFoundError` is raised during request processing
- **THEN** the response SHALL be a full unified error JSON with status code 404

#### Scenario: 404 HTTPException maps to not_found
- **WHEN** a request is made to a non-existent route
- **THEN** the response SHALL be a unified error JSON (not HTML) with `error.code` of `"not_found"`

#### Scenario: 405 HTTPException maps to method_not_allowed
- **WHEN** a request uses an HTTP method not allowed by the route
- **THEN** the response SHALL be a unified error JSON with `error.code` of `"method_not_allowed"`

#### Scenario: Unexpected exception returns generic 500
- **WHEN** an unhandled `Exception` is raised during request processing
- **THEN** the response SHALL have status 500 with the full unified structure `{"success": false, "data": null, "message": "Internal server error", "error": {"code": "internal_error", "details": null}, "meta": {}}`, and the full exception stack trace SHALL be logged

---

### Requirement: Blueprint registration
The system SHALL provide a `register_blueprints(app)` function in `app/__init__.py` that registers all application Blueprints.

#### Scenario: Health blueprint registered
- **WHEN** the application starts
- **THEN** the health check Blueprint SHALL be registered via `register_blueprints()`

#### Scenario: Health blueprint independently importable
- **WHEN** the health Blueprint module is imported directly (not via `register_blueprints`)
- **THEN** it SHALL NOT cause circular import errors

---

### Requirement: Health check endpoint
The system SHALL provide a `GET /api/health` endpoint that returns a unified success response.

#### Scenario: Health check returns ok
- **WHEN** a GET request is sent to `/api/health`
- **THEN** the response SHALL have status 200 and body `{"success": true, "data": {"status": "ok"}, "message": "", "error": null, "meta": {}}`

---

### Requirement: Logging configuration
The system SHALL provide a `configure_logging(app)` function using `logging.config.dictConfig` that configures the root logger. The function SHALL be idempotent: calling it multiple times SHALL NOT add duplicate app-managed handlers or produce duplicate log output.

#### Scenario: LOG_LEVEL from app.config
- **WHEN** `LOG_LEVEL=DEBUG` is set in environment and `create_app()` stores it in `app.config["LOG_LEVEL"]`
- **THEN** `configure_logging(app)` SHALL read `LOG_LEVEL` from `app.config` and set the root logger level to `DEBUG`

#### Scenario: Default log level
- **WHEN** `LOG_LEVEL` is not set
- **THEN** `app.config["LOG_LEVEL"]` SHALL default to `"INFO"`, and `configure_logging(app)` SHALL set the root logger level to `INFO`

#### Scenario: Multiple calls do not duplicate handlers
- **WHEN** `configure_logging(app)` is called twice
- **THEN** the root logger SHALL NOT have duplicate handlers, and log output SHALL NOT be duplicated

---

### Requirement: Application entry point
The system SHALL provide a `run.py` entry point that starts the Flask development server with configurable host and port. Testing SHALL use argument parsing and `mock.patch` on `app.run`, not start a blocking server.

#### Scenario: Default host and port
- **WHEN** `python run.py` is executed without arguments
- **THEN** the server SHALL start on `127.0.0.1:5001` (default values), verified via argument parsing and mocked `app.run`

#### Scenario: Command-line arguments override environment variables
- **WHEN** `python run.py --host 0.0.0.0 --port 8080` is executed
- **THEN** the server SHALL start on `0.0.0.0:8080`, verified via argument parsing and mocked `app.run`

#### Scenario: Environment variables as fallback
- **WHEN** `FLASK_HOST=0.0.0.0 FLASK_PORT=9000 python run.py` is executed without `--host` or `--port`
- **THEN** the server SHALL start on `0.0.0.0:9000`, verified via argument parsing and mocked `app.run`

---

### Requirement: Foundation documentation
The system SHALL update `README.md` to include installation, testing, startup, and health check instructions, as well as a clear statement of what is not yet implemented in the Foundation phase.

#### Scenario: README contains setup instructions
- **WHEN** `README.md` is read
- **THEN** it SHALL contain instructions for installing dependencies (`pip install -e .` or equivalent)

#### Scenario: README contains test instructions
- **WHEN** `README.md` is read
- **THEN** it SHALL contain instructions for running tests (`pytest`)

#### Scenario: README contains startup instructions
- **WHEN** `README.md` is read
- **THEN** it SHALL contain instructions for starting the application (`python run.py`)

#### Scenario: README contains health check instructions
- **WHEN** `README.md` is read
- **THEN** it SHALL describe how to verify the application is running (`curl http://127.0.0.1:5001/api/health`)

#### Scenario: README documents unimplemented scope
- **WHEN** `README.md` is read
- **THEN** it SHALL state which features are not yet implemented in this phase (database, authentication, student CRUD, MCP, AI Chat, etc.)

---

### Requirement: Environment variable template
The system SHALL provide a `.env.example` file containing all environment variables the application recognizes. It SHALL use placeholder values only and MUST NOT contain real secrets.

#### Scenario: All env vars documented
- **WHEN** `.env.example` is read
- **THEN** it SHALL define `APP_ENV`, `SECRET_KEY`, `LOG_LEVEL`, `FLASK_HOST`, `FLASK_PORT`, `MCP_TRANSPORT`, `MCP_HTTP_HOST`, `MCP_HTTP_PORT`, `OPENAI_API_BASE`, `OPENAI_API_KEY`, and `OPENAI_MODEL`

#### Scenario: No real secrets in template
- **WHEN** `.env.example` is read
- **THEN** `SECRET_KEY`, `OPENAI_API_KEY`, and any other sensitive values SHALL be placeholder strings (e.g., `"replace-with-development-secret"`)

---

### Requirement: pyproject.toml project metadata
The system SHALL declare project metadata and dependencies in `pyproject.toml`.

#### Scenario: Flask dependency declared
- **WHEN** `pyproject.toml` is parsed
- **THEN** it SHALL include `flask>=3.0` as a dependency

#### Scenario: python-dotenv dependency declared
- **WHEN** `pyproject.toml` is parsed
- **THEN** it SHALL include `python-dotenv>=1.0` as a dependency

#### Scenario: pytest as dev dependency
- **WHEN** `pyproject.toml` is parsed
- **THEN** it SHALL include `pytest>=8.0` as an optional/dev dependency

#### Scenario: Python version requirement
- **WHEN** `pyproject.toml` is parsed
- **THEN** `requires-python` SHALL be `">=3.12"`

---

### Requirement: pytest infrastructure
The system SHALL provide a `conftest.py` file with shared pytest fixtures for application testing.

#### Scenario: App fixture without .env
- **WHEN** the `app` fixture is used in a test
- **THEN** it SHALL create a Flask app using `create_app("testing", load_env=False)`

#### Scenario: Client fixture
- **WHEN** the `client` fixture is used in a test
- **THEN** it SHALL return a Flask test client bound to the `app` fixture

#### Scenario: Health check test
- **WHEN** `pytest` is run
- **THEN** a test SHALL verify that `GET /api/health` returns status 200 with the expected response format
