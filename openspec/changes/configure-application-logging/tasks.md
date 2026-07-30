## 1. Logging configuration foundation

- [ ] 1.1 Add centralized logging configuration values for level, console output, optional file output, default `instance/logs/app.log`, 5 MB rotation, and five backups; ensure testing disables runtime file output.
- [ ] 1.2 Replace the current minimal setup with an idempotent `logging.config.dictConfig`-based shared policy that manages only its own handlers, sets `disable_existing_loggers` to `False`, and preserves unrelated third-party logger state.
- [ ] 1.3 Add formatter, filter, and context support for `timestamp`, `level`, `logger`, `request_id`, `event`, and `message`; use a stable `-` fallback outside an active request or explicit correlation context.
- [ ] 1.4 Add the reusable security-event logging interface without adding login, user, session, authorization, or CSRF behavior.

## 2. Safe Flask and MCP integration

- [ ] 2.1 Add boundary redaction for passwords, password hashes, API keys, Authorization headers, cookies, session IDs, CSRF tokens, AI confirmation tokens, complete student records, and known unsafe `SECRET_KEY` values; recursively sanitize nested mappings and sequences, strings, arguments, exception text, and structured metadata without mutating caller-owned objects.
- [ ] 2.2 Call `configure_logging(app)` after application configuration is loaded, overridden, normalized, and validated, but before extensions, blueprints, error handlers, repositories, or services can emit startup logs; route unexpected-error logging through the shared policy while preserving safe JSON responses and full server-side tracebacks.
- [ ] 2.3 Replace MCP-specific `basicConfig` setup with the shared policy and ensure startup, tool outcome, and MCP error logs use it.
- [ ] 2.4 Ensure the MCP console handler writes only to stderr and that protocol stdout remains untouched.
- [ ] 2.5 Add configuration examples and Git ignore coverage for optional runtime log files without changing authentication or AI Action Confirmation semantics.

## 3. Automated verification

- [ ] 3.1 Add logging tests for default and configured levels, console setup, idempotence, and no duplicate managed handlers/output across repeated app creation.
- [ ] 3.2 Add tests for opt-in rotating file logging defaults, directory creation only when enabled, testing isolation from development and production log paths, and actual rollover after a test-configured size threshold is reached.
- [ ] 3.3 Add tests that unexpected Flask exceptions retain traceback logging while their HTTP response remains safe and unchanged.
- [ ] 3.4 Add redaction and security-event tests covering all required sensitive fields, complete student records, and both development and placeholder secret-key values.
- [ ] 3.5 Add MCP logging tests proving shared format/redaction use and stderr-only output with no logging contamination of stdout.
- [ ] 3.6 Run the focused logging tests, the complete `pytest` suite, `git diff --check`, and review the final Git diff after the last implementation change.
- [ ] 3.7 Add request-ID tests proving that multiple records within one Flask request share the same non-empty `request_id`, separate requests receive separate identifiers, request context is reset afterward, and records outside a request use the stable `-` fallback without formatting failure.
- [ ] 3.8 Add reusable test fixtures that capture and restore root and managed logger handlers, logger levels, propagation flags, disabled flags, relevant filters, idempotency markers, modified environment variables, Flask request context, and correlation `ContextVar` state after each test; flush and close managed file handlers before temporary directories are removed so tests leak no handlers, files, request IDs, log levels, or environment overrides.

## 4. Manual acceptance

- [ ] 4.1 [USER] With file logging disabled, start Flask and MCP manually and confirm normal console logs are readable while no `instance/logs/` directory is created solely by logging setup.
- [ ] 4.2 [USER] Enable rotating file logging with a local non-secret configuration, confirm logs are written beneath `instance/logs/`, and confirm the runtime files are ignored by Git.
- [ ] 4.3 [USER] Run the MCP server with a stdio client and confirm protocol interaction succeeds without application log lines appearing on stdout.
- [ ] 4.4 [USER] Review representative logs for normal requests, an intentional safe failure, and MCP tool activity; confirm no secret, token, cookie, session value, or complete student record is visible.
