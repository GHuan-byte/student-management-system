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

#### Scenario: Invalid config_name raises ValueError
- **WHEN** `create_app("invalid")` is called
- **THEN** a `ValueError` SHALL be raised

#### Scenario: config_overrides take highest precedence
- **WHEN** `create_app("development", config_overrides={"TEST_KEY": "override"})` is called
- **THEN** `app.config["TEST_KEY"]` SHALL equal `"override"`

---

### Requirement: Configuration boundaries
The system SHALL define `DevelopmentConfig`, `TestingConfig`, and `ProductionConfig`, all inheriting from a base `Config` class.

#### Scenario: Development configuration
- **WHEN** DevelopmentConfig is used
- **THEN** `DEBUG` SHALL be `True`

#### Scenario: Testing configuration
- **WHEN** TestingConfig is used
- **THEN** `TESTING` SHALL be `True`

#### Scenario: Production SECRET_KEY validation
- **WHEN** ProductionConfig is used
- **THEN** the system SHALL raise a `RuntimeError` on startup if `SECRET_KEY` is missing or still set to a development default

#### Scenario: Foundation startup without DATABASE_PATH
- **WHEN** the application starts without `DATABASE_PATH` set
- **THEN** it SHALL NOT fail, because database configuration is outside the Foundation phase

---

### Requirement: Environment variable loading
The system SHALL load environment variables from a `.env` file using `python-dotenv` before environment-related configuration values are parsed and applied.

#### Scenario: .env loaded before config parsing
- **WHEN** `create_app()` is called with `load_env=True`
- **THEN** `load_dotenv()` SHALL be called before environment-related config values are parsed and applied

#### Scenario: System environment overrides .env
- **WHEN** both the system environment and `.env` file define `SECRET_KEY`
- **THEN** the system environment variable SHALL be used

#### Scenario: config_overrides after config merge
- **WHEN** both `.env` and `config_overrides` define the same key
- **THEN** the value from `config_overrides` SHALL be used

---

### Requirement: Unified JSON response
The system SHALL provide helper functions that return a consistent JSON response structure: `{"success": bool, "data": any, "message": str, "error": null|dict, "meta": dict}`.

#### Scenario: Successful response structure
- **WHEN** a success response is returned
- **THEN** it SHALL include `success`, `data`, `message`, `error`, and `meta`

#### Scenario: Error response structure
- **WHEN** an error response is returned
- **THEN** it SHALL include `success`, `data`, `message`, `error`, and `meta`

#### Scenario: Paginated response metadata
- **WHEN** a paginated response is returned
- **THEN** `meta` SHALL include `page`, `page_size`, `total`, and `total_pages`

#### Scenario: Error object structure
- **WHEN** an error response is created
- **THEN** the `error` field SHALL be an object with `code` and nullable `details`, and SHALL NOT contain a raw Python exception object

---

### Requirement: Application exceptions
The system SHALL define a hierarchy of application exceptions: `AppError` as base, with `NotFoundError`, `ValidationError`, `DuplicateError`, and `ForbiddenError` subclasses.

#### Scenario: Application exception carries metadata
- **WHEN** an application exception is created
- **THEN** it SHALL carry `code`, `message`, `status_code`, and `details`

#### Scenario: NotFoundError maps to 404
- **WHEN** `NotFoundError` is raised
- **THEN** it SHALL represent status code 404 and code `"not_found"`

#### Scenario: ValidationError maps to 400
- **WHEN** `ValidationError` is raised
- **THEN** it SHALL represent status code 400 and code `"validation_error"`

---

### Requirement: Global error handling
The system SHALL register global error handlers for `AppError`, `werkzeug.exceptions.HTTPException`, and unexpected `Exception`.

#### Scenario: AppError returns unified error response
- **WHEN** an `AppError` is raised during request processing
- **THEN** the response SHALL use the unified JSON error structure

#### Scenario: HTTPException returns unified error response
- **WHEN** a `HTTPException` occurs during request processing
- **THEN** the response SHALL use the unified JSON error structure instead of HTML

#### Scenario: Unexpected exception returns generic 500
- **WHEN** an unhandled `Exception` occurs
- **THEN** the response SHALL return status 500 with unified JSON structure and SHALL NOT expose internal implementation details

---

### Requirement: Blueprint registration
The system SHALL provide a `register_blueprints(app)` function that registers application Blueprints through a centralized integration point.

#### Scenario: Health blueprint registered
- **WHEN** the application starts
- **THEN** the health check Blueprint SHALL be registered through `register_blueprints()`

#### Scenario: Blueprint registration avoids circular imports
- **WHEN** route modules are imported for registration
- **THEN** the registration structure SHALL avoid circular import failures

---

### Requirement: Health check
The system SHALL provide a `GET /api/health` endpoint that returns a unified success response.

#### Scenario: Health check returns ok
- **WHEN** a GET request is sent to `/api/health`
- **THEN** the response SHALL return status 200
- **AND** the response body SHALL use the unified JSON structure
- **AND** `data.status` SHALL equal `"ok"`

---

### Requirement: Logging configuration
The system SHALL provide a `configure_logging(app)` function that configures application logging through a centralized entry point.

#### Scenario: LOG_LEVEL comes from configuration
- **WHEN** logging is configured
- **THEN** the effective log level SHALL be derived from application configuration

#### Scenario: Logging setup is idempotent
- **WHEN** logging configuration is applied more than once
- **THEN** it SHALL NOT create duplicate application-managed logging behavior

---

### Requirement: Application entry point
The system SHALL provide a `run.py` entry point that starts the Flask application with configurable host and port.

#### Scenario: Default host and port
- **WHEN** `python run.py` is executed without arguments or environment overrides
- **THEN** the application SHALL start with default host `127.0.0.1` and default port `5001`

#### Scenario: Command-line arguments override environment variables
- **WHEN** `python run.py --host 0.0.0.0 --port 8080` is executed
- **THEN** the command-line values SHALL take precedence over environment variables and defaults

#### Scenario: Environment variables act as fallback
- **WHEN** `FLASK_HOST` and `FLASK_PORT` are set and CLI arguments are omitted
- **THEN** the application SHALL use the environment values as fallback

---

### Requirement: pyproject.toml project metadata
The system SHALL declare project metadata and Foundation dependencies in `pyproject.toml`.

#### Scenario: Flask dependency declared
- **WHEN** `pyproject.toml` is parsed
- **THEN** it SHALL include `flask>=3.0` as a dependency

#### Scenario: python-dotenv dependency declared
- **WHEN** `pyproject.toml` is parsed
- **THEN** it SHALL include `python-dotenv>=1.0` as a dependency

#### Scenario: Python version requirement
- **WHEN** `pyproject.toml` is parsed
- **THEN** `requires-python` SHALL be `">=3.12"`

---

### Requirement: Foundation documentation
The system SHALL update `README.md` and `.env.example` to document manual setup and manual Foundation verification.

#### Scenario: README contains manual install instructions
- **WHEN** `README.md` is read
- **THEN** it SHALL include user-facing dependency installation commands

#### Scenario: README contains startup instructions
- **WHEN** `README.md` is read
- **THEN** it SHALL include instructions for starting the application with `python run.py`

#### Scenario: README contains health check instructions
- **WHEN** `README.md` is read
- **THEN** it SHALL describe how to verify `GET /api/health`

#### Scenario: .env.example contains placeholder values
- **WHEN** `.env.example` is read
- **THEN** it SHALL document recognized environment variables using placeholder values only

#### Scenario: Documentation states deferred testing
- **WHEN** `README.md` is read
- **THEN** it SHALL state that full automated testing is deferred to a later Testing / Final Verification Change

---

### Requirement: Manual foundation verification
The system SHALL support manual Foundation verification after the user manually installs dependencies.

#### Scenario: Manual run succeeds
- **WHEN** the user manually installs dependencies and runs `python run.py`
- **THEN** the Flask Foundation SHALL start successfully

#### Scenario: Manual health check succeeds
- **WHEN** the user sends `GET http://127.0.0.1:5001/api/health`
- **THEN** the response SHALL return status 200 and the unified JSON response structure

#### Scenario: Formatting check passes
- **WHEN** `git diff --check` is run
- **THEN** it SHALL report no formatting errors
