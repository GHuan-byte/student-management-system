## 1. Scope Guardrails

This Change is limited to Flask Foundation only.

Out of scope for this Change:

- Database
- Repository
- Service
- Authentication
- Student CRUD
- Templates and frontend JavaScript
- MCP
- AI Chat
- Import / export
- Data migration

Execution guardrails for this Change:

- Do not create `tests/conftest.py`
- Do not create `tests/test_*.py`
- Do not add pytest fixtures
- Do not add `mock app.run`-based test work
- Do not use test-first implementation steps in this Change
- Do not run `pytest`
- Do not create, activate, or manage virtual environments
- Do not resolve interpreter-selection issues
- Do not install dependencies automatically
- Keep the code structure modular so a later Testing / Final Verification Change can add automated tests without reshaping Foundation modules
- Complete this Change and stop; do not move into the next Change automatically

---

## 2. Project Scaffolding

- [x] 2.1 Create `pyproject.toml` with `[build-system]` and `[project]`
- [x] 2.2 Set `requires-python = ">=3.12"` in `pyproject.toml`
- [x] 2.3 Declare Foundation dependencies `flask>=3.0` and `python-dotenv>=1.0` in `pyproject.toml`
- [x] 2.4 Add setuptools package discovery configuration in `pyproject.toml` for the `app` package
- [x] 2.5 Update `.gitignore` with Python project baseline ignores appropriate for Foundation
- [x] 2.6 Update `.env.example` with recognized environment variables using placeholder values only

---

## 3. Configuration Module

- [x] 3.1 Create `app/config.py`
- [x] 3.2 Define `Config`, `DevelopmentConfig`, `TestingConfig`, and `ProductionConfig`
- [x] 3.3 Implement config resolution order as `config_name` > `APP_ENV` > `"development"`
- [x] 3.4 Ensure unknown config names raise a clear exception
- [x] 3.5 Ensure `config_overrides` has the highest priority over class defaults and environment-derived values
- [x] 3.6 Ensure Production configuration validation happens after `config_overrides` are applied
- [x] 3.7 Ensure Production raises a clear exception when `SECRET_KEY` is missing or still set to a development default value
- [x] 3.8 Ensure Foundation startup does not require `DATABASE_PATH`

---

## 4. Application Factory

- [x] 4.1 Create `app/__init__.py`
- [x] 4.2 Implement `create_app(config_name=None, config_overrides=None, load_env=True)` in `app/__init__.py`
- [x] 4.3 Load `.env` before parsing environment-derived configuration when `load_env=True`
- [x] 4.4 Apply the resolved configuration object to `app.config`
- [x] 4.5 Apply `config_overrides` after base configuration loading and before final Production validation
- [x] 4.6 Call Blueprint registration, error handler registration, and logging configuration from the factory

---

## 5. Unified JSON Response Utilities

- [x] 5.1 Create `app/utils/__init__.py`
- [x] 5.2 Create `app/utils/response.py`
- [x] 5.3 Implement `api_success()` using the unified response fields `success`, `data`, `message`, `error`, and `meta`
- [x] 5.4 Implement `api_error()` using the unified response fields `success`, `data`, `message`, `error`, and `meta`
- [x] 5.5 Ensure `api_error()` always returns an `error` object containing `code` and `details`
- [x] 5.6 Implement `api_paginated()` using the unified response structure
- [x] 5.7 Ensure `api_paginated()` returns pagination metadata in `meta`
- [x] 5.8 Ensure `api_paginated()` calculates `total_pages`
- [x] 5.9 Ensure `api_paginated()` raises `ValueError` when `page_size <= 0`

---

## 6. Application Exceptions and Error Handling

- [x] 6.1 Create `app/utils/errors.py`
- [x] 6.2 Define `AppError` and core subclasses in `app/utils/errors.py`
- [x] 6.3 Create `app/error_handlers.py`
- [x] 6.4 Implement `AppError` handling so responses use the exception's own `code`, `message`, `status_code`, and `details`
- [x] 6.5 Map HTTP 404 errors to error code `not_found`
- [x] 6.6 Map HTTP 405 errors to error code `method_not_allowed`
- [x] 6.7 Map unexpected exceptions to error code `internal_error`
- [x] 6.8 Ensure unexpected exception responses use HTTP 500 and do not leak stack traces, raw exception text, or internal filesystem paths
- [x] 6.9 Ensure unexpected exceptions are logged with full details for debugging

---

## 7. Blueprint Registration and Health Check

- [x] 7.1 Create `app/routes/__init__.py`
- [x] 7.2 Create `app/routes/health.py`
- [x] 7.3 Add centralized `register_blueprints(app)` integration in `app/__init__.py`
- [x] 7.4 Register the Foundation health Blueprint through the centralized registration path
- [x] 7.5 Implement `GET /api/health`
- [x] 7.6 Ensure the health check returns HTTP 200 and the unified JSON response structure

---

## 8. Logging Configuration

- [x] 8.1 Create `app/logging_config.py`
- [x] 8.2 Implement `configure_logging(app)` in `app/logging_config.py`
- [x] 8.3 Use `logging.config.dictConfig` for application-managed logging setup
- [x] 8.4 Read `LOG_LEVEL` from the final `app.config`
- [x] 8.5 Default `LOG_LEVEL` to `INFO`
- [x] 8.6 Ensure repeated calls do not add duplicate application-managed handlers
- [x] 8.7 Ensure Foundation default logging does not output `SECRET_KEY`, API keys, request bodies, or student information

---

## 9. Application Entry Point

- [x] 9.1 Create `run.py`
- [x] 9.2 Separate argument parsing from application creation
- [x] 9.3 Support `--host` and `--port`
- [x] 9.4 Use priority order `CLI > environment variables > defaults`
- [x] 9.5 Use default host `127.0.0.1` and default port `5001`
- [x] 9.6 Use `if __name__ == "__main__": main()`

---

## 10. Documentation

- [x] 10.1 Update `README.md` with Python `>=3.12` requirement
- [x] 10.2 Document manual dependency installation commands in `README.md`
- [x] 10.3 Document `python run.py` startup instructions in `README.md`
- [x] 10.4 Document manual health check instructions for `http://127.0.0.1:5001/api/health` in `README.md`
- [x] 10.5 State clearly in `README.md` that complete automated testing is deferred to a later Testing / Final Verification Change

---

## 11. Final Verification

### Agent Checks

- [x] 11.1 Run `git diff --check`
- [x] 11.2 Run `git status`
- [x] 11.3 Check that the implementation scope remains limited to Flask Foundation
- [x] 11.4 Summarize the manual commands the user needs for dependency installation, application startup, and health check verification

Agent verification constraints:

- Do not run `pytest`
- Do not install dependencies
- Do not create, activate, or manage virtual environments
- Do not resolve interpreter-selection issues
- Stop after this Change and do not enter the next Change automatically

### User Acceptance

- [x] 11.5 [USER] Confirm the active Python interpreter version is `>=3.12`
- [x] 11.6 [USER] Run the documented dependency installation command manually
- [x] 11.7 [USER] Run `python run.py`
- [x] 11.8 [USER] Access `http://127.0.0.1:5001/api/health` manually or with an HTTP client
- [x] 11.9 [USER] Confirm the response returns HTTP 200 and uses the unified JSON response structure
