## 1. Project Scaffolding

- [ ] 1.1 Create `pyproject.toml` with `[build-system]`, `[project]`, `requires-python = ">=3.12"`, and Foundation dependencies `flask>=3.0` and `python-dotenv>=1.0`
- [ ] 1.2 Update `.gitignore` with Python project baseline ignores appropriate for Foundation
- [ ] 1.3 Update `.env.example` with recognized environment variables using placeholder values only
- [ ] 1.4 Keep the current phase scoped to Flask Foundation only and exclude database, Repository, Service, authentication, student CRUD, frontend, MCP, AI Chat, import/export, and migration

---

## 2. Configuration Module

- [ ] 2.1 Create `app/config.py` with `Config`, `DevelopmentConfig`, `TestingConfig`, and `ProductionConfig`
- [ ] 2.2 Implement config resolution order: explicit `config_name` > `APP_ENV` > `"development"`
- [ ] 2.3 Ensure unknown config names raise a clear exception
- [ ] 2.4 Ensure Foundation startup does not require database configuration

---

## 3. Application Factory

- [ ] 3.1 Create `app/__init__.py` with `create_app(config_name=None, config_overrides=None, load_env=True)`
- [ ] 3.2 Load `.env` before parsing environment-derived configuration when `load_env=True`
- [ ] 3.3 Apply `config_overrides` with highest precedence
- [ ] 3.4 Invoke configuration loading, Blueprint registration, error handler registration, and logging configuration from the factory

---

## 4. Unified JSON Response Utilities

- [ ] 4.1 Create `app/utils/response.py`
- [ ] 4.2 Implement unified success response helper
- [ ] 4.3 Implement unified error response helper
- [ ] 4.4 Implement unified paginated response helper

---

## 5. Application Exceptions and Error Handling

- [ ] 5.1 Create `app/utils/errors.py` with `AppError` and core subclasses
- [ ] 5.2 Create global error handler registration module
- [ ] 5.3 Ensure `AppError`, `HTTPException`, and unexpected exceptions all return unified JSON error responses
- [ ] 5.4 Ensure unexpected exceptions do not leak internal details to API callers

---

## 6. Blueprint Registration and Health Check

- [ ] 6.1 Create route package structure for Foundation
- [ ] 6.2 Add centralized `register_blueprints(app)` integration point
- [ ] 6.3 Add `GET /api/health`
- [ ] 6.4 Ensure the health check returns status 200 and the unified JSON response structure

---

## 7. Logging Configuration

- [ ] 7.1 Create logging configuration module
- [ ] 7.2 Read `LOG_LEVEL` from application configuration
- [ ] 7.3 Keep logging initialization idempotent
- [ ] 7.4 Avoid logging sensitive information in Foundation defaults

---

## 8. Application Entry Point

- [ ] 8.1 Create `run.py` as the Foundation startup entry point
- [ ] 8.2 Support host and port configuration with precedence `CLI > environment > defaults`
- [ ] 8.3 Keep entry-point logic simple and modular for later verification work

---

## 9. Documentation

- [ ] 9.1 Update `README.md` with Python `>=3.12` requirement
- [ ] 9.2 Provide manual dependency installation commands in `README.md`, but do not auto-run them
- [ ] 9.3 Document `python run.py` startup instructions
- [ ] 9.4 Document manual health check instructions for `http://127.0.0.1:5001/api/health`
- [ ] 9.5 State clearly that complete automated testing is deferred to a later Testing / Final Verification Change

---

## 10. Final Manual Verification

- [ ] 10.1 Check the user's current Python version satisfies `>=3.12`
- [ ] 10.2 Provide dependency installation commands to the user, but do not automatically execute them
- [ ] 10.3 User manually runs `python run.py`
- [ ] 10.4 User manually accesses or calls `http://127.0.0.1:5001/api/health`
- [ ] 10.5 Confirm the response is HTTP 200 and uses the unified JSON response structure
- [ ] 10.6 Run `git diff --check`
- [ ] 10.7 Run `git status`
- [ ] 10.8 Do not run `pytest`
- [ ] 10.9 Do not handle virtual environment creation, activation, or interpreter selection issues in this Change
