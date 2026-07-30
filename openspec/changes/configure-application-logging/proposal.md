## Why

The Flask application and the stdio MCP server currently configure logging
independently, with no correlation field, central redaction policy, or safe
file-logging lifecycle. The first security stage needs a shared, testable
logging foundation before login and access-control events are introduced.

## What Changes

- Define one application logging policy used by Flask and MCP, with a shared
  human-readable structured formatter, redaction filter, and security-event
  logging interface.
- Configure Flask logging with idempotent `logging.config.dictConfig` setup so
  repeated app creation does not duplicate handlers or output.
- Add environment-backed console and optional rotating-file logging settings;
  file logging defaults to `instance/logs/app.log` when enabled and is isolated
  from tests.
- Preserve full tracebacks for unexpected Flask and MCP failures while ensuring
  logs redact credentials, tokens, cookies, session identifiers, and complete
  student records.
- Ensure MCP stdio logging uses stderr only and does not contaminate protocol
  stdout.
- Add automated coverage and update configuration examples and Git ignore rules
  for runtime log files.
- Do not implement login, authentication, sessions, CSRF, or authorization.
- Do not introduce third-party logging, monitoring, telemetry, Sentry, hosted
  log aggregation, or external observability platforms.

## Capabilities

### New Capabilities

- `application-logging`: Shared, safe, configurable logging for Flask and MCP.

### Modified Capabilities

- None.

## Impact

Likely changes are limited to centralized configuration, Flask/MCP logging
integration, error logging call sites, logging tests, `.env.example`, and
`.gitignore`. No new dependency, HTTP endpoint, database schema, login,
authentication mechanism, session, CSRF behavior, authorization rule, external
observability service, or AI confirmation behavior is introduced.
