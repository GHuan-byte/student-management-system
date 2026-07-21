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

- [ ] 2.1 Create `pyproject.toml` with `[build-system]` and `[project]`
- [ ] 2.2 Set `requires-python = ">=3.12"` in `pyproject.toml`
- [ ] 2.3 Declare Foundation dependencies `flask>=3.0` and `python-dotenv>=1.0` in `pyproject.toml`
- [ ] 2.4 Add setuptools package discovery configuration in `pyproject.toml` for the `app` package
- [ ] 2.5 Update `.gitignore` with Python project baseline ignores appropriate for Foundation
- [ ] 2.6 Update `.env.example` with recognized environment variables using placeholder values only

---

## 3. Configuration Module

- [ ] 3.1 Create `app/config.py`
- [ ] 3.2 Define `Config`, `DevelopmentConfig`, `TestingConfig`, and `ProductionConfig`
- [ ] 3.3 Implement config resolution order as `config_name` > `APP_ENV` > `"development"`
- [ ] 3.4 Ensure unknown config names raise a clear exception
- [ ] 3.5 Ensure `config_overrides` has the highest priority over class defaults and environment-derived values
- [ ] 3.6 Ensure Production configuration validation happens after `config_overrides` are applied
- [ ] 3.7 Ensure Production raises a clear exception when `SECRET_KEY` is missing or still set to a development default value
- [ ] 3.8 Ensure Foundation startup does not require `DATABASE_PATH`

---

## 4. Application Factory

- [ ] 4.1 Create `app/__init__.py`
- [ ] 4.2 Implement `create_app(config_name=None, config_overrides=None, load_env=True)` in `app/__init__.py`
- [ ] 4.3 Load `.env` before parsing environment-derived configuration when `load_env=True`
- [ ] 4.4 Apply the resolved configuration object to `app.config`
- [ ] 4.5 Apply `config_overrides` after base configuration loading and before final Production validation
- [ ] 4.6 Call Blueprint registration, error handler registration, and logging configuration from the factory

---

## 5. Unified JSON Response Utilities

- [ ] 5.1 Create `app/utils/__init__.py`
- [ ] 5.2 Create `app/utils/response.py`
- [ ] 5.3 Implement `api_success()` using the unified response fields `success`, `data`, `message`, `error`, and `meta`
- [ ] 5.4 Implement `api_error()` using the unified response fields `success`, `data`, `message`, `error`, and `meta`
- [ ] 5.5 Ensure `api_error()` always returns an `error` object containing `code` and `details`
- [ ] 5.6 Implement `api_paginated()` using the unified response structure
- [ ] 5.7 Ensure `api_paginated()` returns pagination metadata in `meta`
- [ ] 5.8 Ensure `api_paginated()` calculates `total_pages`
- [ ] 5.9 Ensure `api_paginated()` raises `ValueError` when `page_size <= 0`

---

## 6. Application Exceptions and Error Handling

- [ ] 6.1 Create `app/utils/errors.py`
- [ ] 6.2 Define `AppError` and core subclasses in `app/utils/errors.py`
- [ ] 6.3 Create `app/error_handlers.py`
- [ ] 6.4 Implement `AppError` handling so responses use the exception's own `code`, `message`, `status_code`, and `details`
- [ ] 6.5 Map HTTP 404 errors to error code `not_found`
- [ ] 6.6 Map HTTP 405 errors to error code `method_not_allowed`
- [ ] 6.7 Map unexpected exceptions to error code `internal_error`
- [ ] 6.8 Ensure unexpected exception responses use HTTP 500 and do not leak stack traces, raw exception text, or internal filesystem paths
- [ ] 6.9 Ensure unexpected exceptions are logged with full details for debugging

---

## 7. Blueprint Registration and Health Check

- [ ] 7.1 Create `app/routes/__init__.py`
- [ ] 7.2 Create `app/routes/health.py`
- [ ] 7.3 Add centralized `register_blueprints(app)` integration in `app/__init__.py`
- [ ] 7.4 Register the Foundation health Blueprint through the centralized registration path
- [ ] 7.5 Implement `GET /api/health`
- [ ] 7.6 Ensure the health check returns HTTP 200 and the unified JSON response structure

---

## 8. Logging Configuration

- [ ] 8.1 Create `app/logging_config.py`
- [ ] 8.2 Implement `configure_logging(app)` in `app/logging_config.py`
- [ ] 8.3 Use `logging.config.dictConfig` for application-managed logging setup
- [ ] 8.4 Read `LOG_LEVEL` from the final `app.config`
- [ ] 8.5 Default `LOG_LEVEL` to `INFO`
- [ ] 8.6 Ensure repeated calls do not add duplicate application-managed handlers
- [ ] 8.7 Ensure Foundation default logging does not output `SECRET_KEY`, API keys, request bodies, or student information

---

## 9. Application Entry Point

- [ ] 9.1 Create `run.py`
- [ ] 9.2 Separate argument parsing from application creation
- [ ] 9.3 Support `--host` and `--port`
- [ ] 9.4 Use priority order `CLI > environment variables > defaults`
- [ ] 9.5 Use default host `127.0.0.1` and default port `5001`
- [ ] 9.6 Use `if __name__ == "__main__": main()`

---

## 10. Documentation

- [ ] 10.1 Update `README.md` with Python `>=3.12` requirement
- [ ] 10.2 Document manual dependency installation commands in `README.md`
- [ ] 10.3 Document `python run.py` startup instructions in `README.md`
- [ ] 10.4 Document manual health check instructions for `http://127.0.0.1:5001/api/health` in `README.md`
- [ ] 10.5 State clearly in `README.md` that complete automated testing is deferred to a later Testing / Final Verification Change

---

## 11. Final Verification

### Agent Checks

- [ ] 11.1 Run `git diff --check`
- [ ] 11.2 Run `git status`
- [ ] 11.3 Check that the implementation scope remains limited to Flask Foundation
- [ ] 11.4 Summarize the manual commands the user needs for dependency installation, application startup, and health check verification

Agent verification constraints:

- Do not run `pytest`
- Do not install dependencies
- Do not create, activate, or manage virtual environments
- Do not resolve interpreter-selection issues
- Stop after this Change and do not enter the next Change automatically

### User Acceptance

- [ ] 11.5 [USER] Confirm the active Python interpreter version is `>=3.12`
- [ ] 11.6 [USER] Run the documented dependency installation command manually
- [ ] 11.7 [USER] Run `python run.py`
- [ ] 11.8 [USER] Access `http://127.0.0.1:5001/api/health` manually or with an HTTP client
- [ ] 11.9 [USER] Confirm the response returns HTTP 200 and uses the unified JSON response structure
