## 1. Project Scaffolding

- [ ] 1.1 Create `pyproject.toml` with `[build-system]` (setuptools), `[project]` (name, version, `requires-python = ">=3.12"`, dependencies: `flask>=3.0`, `python-dotenv>=1.0`), `[project.optional-dependencies] dev = ["pytest>=8.0"]`, and `[tool.setuptools.packages.find]` for package discovery
- [ ] 1.2 Update `.gitignore` with Python project standards (`.env`, `__pycache__/`, `*.db`, `.venv/`, etc.)
- [ ] 1.3 Update `.env.example` with all recognized environment variables (`APP_ENV`, `SECRET_KEY`, `LOG_LEVEL`, `FLASK_HOST`, `FLASK_PORT`) using placeholder values only; mark `MCP_TRANSPORT`, `MCP_HTTP_HOST`, `MCP_HTTP_PORT`, `OPENAI_API_BASE`, `OPENAI_API_KEY`, `OPENAI_MODEL` as `# reserved for future phases`
- [ ] 1.4 Confirm local Python version satisfies `requires-python >= 3.12`: `python --version`
- [ ] 1.5 Create V2 independent virtual environment: `python -m venv .venv && source .venv/bin/activate`
- [ ] 1.6 Install project in dev mode: `pip install -e ".[dev]"`

> **Verify:** `python -c "import flask; print(flask.__version__)"` and `pytest --version`

---

## 2. Configuration Module

- [ ] 2.1 Create `app/__init__.py` (minimal, package marker only — factory comes later)
- [ ] 2.2 Create `app/config.py` with base `Config` class using class-attribute defaults. **Important:** all env-dependent values must be read inside methods or `__init__`, not at module level, to avoid freezing before `load_dotenv()` is called
- [ ] 2.3 Implement `DevelopmentConfig` with `DEBUG = True` and non-production `SECRET_KEY` default
- [ ] 2.4 Implement `TestingConfig` with `TESTING = True` (no `DATABASE_PATH` default)
- [ ] 2.5 Implement `ProductionConfig` — postpone final validation so it runs after `config_overrides` are applied
- [ ] 2.6 Implement config resolution function: explicit `config_name` > `APP_ENV` env var > fallback to `"development"`, raise `ValueError` for unknown names
- [ ] 2.7 Create `tests/conftest.py` with shared `app` fixture (`create_app("testing", load_env=False)`) and `client` fixture
- [ ] 2.8 Create `tests/test_config.py` covering:
  - DevelopmentConfig has `DEBUG = True`
  - TestingConfig has `TESTING = True`
  - Unknown `config_name` raises `ValueError`
  - `APP_ENV=testing` selects TestingConfig when `config_name` is `None`
  - Explicit `config_name` overrides `APP_ENV`

> **Verify:** `pytest tests/test_config.py -q`

---

## 3. Response Utilities

- [ ] 3.1 Create `app/utils/__init__.py`
- [ ] 3.2 Create `app/utils/response.py` with `api_success(data=None, message="", meta=None, status_code=200)` returning `(Response, status_code, headers)` with `Content-Type: application/json`
- [ ] 3.3 Implement `api_error(message="", error=None, status_code=400)` where `error` is `{"code": "...", "details": null}` — never a raw Exception object
- [ ] 3.4 Implement `api_paginated(data, total, page, page_size, message="")` computing `total_pages` via `ceil(total / page_size)`, raising `ValueError` for `page_size <= 0`
- [ ] 3.5 Create `tests/test_response.py` covering:
  - `api_success` returns 200 with expected structure
  - `api_success` with `status_code=201` returns 201
  - `api_error` returns 404 with `error.code == "not_found"`
  - `api_paginated` with `total=50, page=1, page_size=15` computes `total_pages=4`
  - `api_paginated` with `total=0` returns `total_pages=0`
  - `api_paginated` with `page_size=0` raises `ValueError`

> **Verify:** `pytest tests/test_response.py -q`

---

## 4. Exception Classes

- [ ] 4.1 Create `app/utils/errors.py` with base `AppError(code, message, status_code, details=None)` and subclasses:
  - `NotFoundError` → `status_code=404`, `code="not_found"`
  - `ValidationError` → `status_code=400`, `code="validation_error"`
  - `DuplicateError` → `status_code=409`, `code="duplicate"`
  - `ForbiddenError` → `status_code=403`, `code="forbidden"`
- [ ] 4.2 Create `tests/test_errors.py` covering:
  - Each exception subclass has correct `status_code` and `code`
  - `AppError` default `details` is `None`

> **Verify:** `pytest tests/test_errors.py -q`

---

## 5. Error Handlers

- [ ] 5.1 Create `app/error_handlers.py` with `register_error_handlers(app)` function
- [ ] 5.2 `@app.errorhandler(AppError)` — extract `code`, `message`, `details`, `status_code`, return `api_error()` format
- [ ] 5.3 `@app.errorhandler(HTTPException)` — map 404 → `"not_found"`, 405 → `"method_not_allowed"`, other codes to generic `"http_error"`
- [ ] 5.4 `@app.errorhandler(Exception)` — log full stack trace, return 500 with `{"code": "internal_error", "details": null}` in the full unified structure (`success`, `data`, `message`, `error`, `meta`)
- [ ] 5.5 Create `tests/test_health.py` (health check), `tests/test_app_factory.py` (error handler registration) covering:
  - `NotFoundError` during request → unified error JSON with status 404
  - 404 route → `error.code == "not_found"` (not HTML)
  - 405 method → `error.code == "method_not_allowed"`
  - 500 on unexpected exception → full unified structure; test must disable exception propagation (`app.config["TESTING"] = True` is not enough — use `app.test_client()` which already catches exceptions; if needed set `app.config["PROPAGATE_EXCEPTIONS"] = False` to ensure the handler is reached)

> **Verify:** `pytest tests/test_health.py tests/test_app_factory.py -q`

---

## 6. Logging Configuration

- [ ] 6.1 Create `app/logging_config.py` with `configure_logging(app)` using `logging.config.dictConfig`
- [ ] 6.2 Configure console handler with timestamped format: `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`
- [ ] 6.3 Read `LOG_LEVEL` from `app.config` (not directly from `os.environ`), default to `"INFO"`
- [ ] 6.4 Ensure idempotency: calling `configure_logging()` multiple times does not add duplicate app-managed handlers or produce duplicate log output
- [ ] 6.5 Create `tests/test_logging.py` covering:
  - Root logger level matches `app.config["LOG_LEVEL"]`
  - Default log level is `"INFO"`
  - Multiple calls do not duplicate handlers

> **Verify:** `pytest tests/test_logging.py -q`

---

## 7. Application Factory

- [ ] 7.1 Update `app/__init__.py` with `create_app(config_name=None, config_overrides=None, load_env=True)` factory function
- [ ] 7.2 Load `.env` via `load_dotenv()` first (when `load_env=True`), without overriding existing system environment variables — this ensures env-dependent config values are not frozen before `.env` is loaded
- [ ] 7.3 Resolve config class, instantiate it, apply to `app.config`
- [ ] 7.4 Apply `config_overrides` (highest priority), then run Production `SECRET_KEY` validation *after* overrides
- [ ] 7.5 Call `configure_logging(app)` from `app.logging_config`
- [ ] 7.6 Call `register_blueprints(app)` and `register_error_handlers(app)` inside factory
- [ ] 7.7 Create `tests/test_app_factory.py` covering:
  - Default `create_app()` returns app with DevelopmentConfig
  - `create_app("testing", load_env=False)` does not load `.env`
  - `create_app()` without `config_name` and `APP_ENV=testing` selects TestingConfig
  - `create_app("development")` with `APP_ENV=production` uses DevelopmentConfig
  - `config_overrides` has highest priority over `.env` and config class defaults
  - Production config raises `RuntimeError` if `SECRET_KEY` is missing
  - Production config starts normally if `SECRET_KEY` is provided via `config_overrides`
  - Foundation phase starts without `DATABASE_PATH`

> **Verify:** `pytest tests/test_app_factory.py -q`

---

## 8. Blueprint Registration and Health Check

- [ ] 8.1 Create `app/routes/__init__.py` (package marker)
- [ ] 8.2 Create `app/routes/health.py` Blueprint with `GET /api/health` returning `api_success(data={"status": "ok"})`
- [ ] 8.3 Implement `register_blueprints(app)` in `app/__init__.py` with lazy imports to avoid circular dependencies
- [ ] 8.4 Verify `app/routes/health.py` is independently importable: `python -c "from app.routes.health import health_bp"`
- [ ] 8.5 Add health check scenario to `tests/test_health.py`: `GET /api/health` returns status 200 with body `{"success": true, "data": {"status": "ok"}, "message": "", "error": null, "meta": {}}`

> **Verify:** `pytest tests/test_health.py -q`

---

## 9. Application Entry Point

- [ ] 9.1 Create `run.py` with `parse_args()` function (returns parsed namespace) and `main()` function; use `if __name__ == "__main__": main()` guard
- [ ] 9.2 Parameter priority: CLI args > environment variables (`FLASK_HOST`, `FLASK_PORT`) > defaults (`127.0.0.1:5001`)
- [ ] 9.3 Create `tests/test_run.py` using `unittest.mock.patch` on `app.run` — never start a blocking server in tests; covering:
  - Default host and port
  - `--host 0.0.0.0 --port 8080` overrides defaults
  - Environment variables used as fallback when no CLI args given

> **Verify:** `pytest tests/test_run.py -q`

---

## 10. Documentation

- [ ] 10.1 Update `README.md` with:
  - Prerequisites (Python >= 3.12)
  - Virtual environment setup (`.venv`)
  - Install: `pip install -e ".[dev]"`
  - Run tests: `pytest` or `pytest -q`
  - Start application: `python run.py`
  - Health check: `curl http://127.0.0.1:5001/api/health`
  - Current phase statement: what is implemented (Foundation) and what is not yet implemented (database, authentication, student CRUD, template frontend, MCP, AI Chat, import/export, data migration)

> **Verify:** review rendered `README.md`

---

## 11. Final Verification

- [ ] 11.1 Run full test suite: `pytest -q`
- [ ] 11.2 Check for whitespace issues: `git diff --check`
- [ ] 11.3 Check only intended files are modified: `git status`
- [ ] 11.4 Start application: `python run.py` and verify health check: `curl http://127.0.0.1:5001/api/health`
