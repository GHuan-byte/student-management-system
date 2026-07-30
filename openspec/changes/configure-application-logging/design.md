## Context

Flask currently applies a root-console `dictConfig` on each app creation while
the stdio MCP server conditionally calls `basicConfig`. Neither route has a
shared redaction policy, standard `request_id` contract, file-handler lifecycle,
or reliable test-state restoration. Existing Flask and MCP error paths already
use exception logging, so this Change must retain traceback structure while
preventing sensitive data from being formatted into logs.

This is the P1-A logging-only Change. It must establish infrastructure for
future security events without implementing login, authentication, sessions,
CSRF, authorization, user tables, or changes to AI Action Confirmation.

## Goals / Non-Goals

**Goals:**

- Establish one idempotent, `dictConfig`-based policy for Flask and MCP.
- Produce human-readable records with the exact standard fields `timestamp`,
  `level`, `logger`, `request_id`, `event`, and `message`.
- Generate and reset server-side Flask request IDs, support explicit
  correlation in MCP/non-request work, and use `-` for absent context.
- Provide console logging, opt-in rotating files, tracebacks, redaction, and a
  reusable security-event interface.
- Keep logging state isolated and fully restorable in pytest.

**Non-Goals:**

- Login routes, authentication, authorization, user schema, password handling,
  sessions, or CSRF.
- Client-provided `X-Request-ID`, external request-ID forwarding, distributed
  tracing, third-party monitoring, telemetry, Sentry, hosted aggregation, or
  JSON/cloud logging.
- Changing production `SECRET_KEY` validation or AI confirmation token creation,
  verification, expiry, or consumption behavior.

## Decisions

### Shared policy and dictConfig safety

`app.logging_config` becomes the sole policy owner. Flask calls
`configure_logging(app)` and the MCP server calls the same framework-neutral
policy before its stdio transport starts. Every `logging.config.dictConfig`
mapping SHALL set `disable_existing_loggers: false`.

The policy will manage only explicitly marked application/MCP handlers; it will
not reset the global logging system to achieve idempotency. Managed handlers
are replaced or reused deterministically, and removed managed file handlers are
flushed and closed. Unrelated third-party logger handlers, levels, propagation,
disabled flags, and filters remain untouched.

Alternative: reconfigure the root logger or retain `basicConfig` for MCP.
Rejected because both approaches can duplicate output, mutate unrelated logger
state, and cause Flask/MCP formatting and redaction drift.

### Required application-factory ordering

The factory SHALL execute this sequence:

1. Create the Flask application instance.
2. Load and normalize the selected configuration.
3. Apply configuration overrides.
4. Validate configuration required for the selected environment.
5. Call `configure_logging(app)`.
6. Only then initialize extensions, repositories, blueprints, error handlers,
   services, and other components that can emit managed startup logs.

`configure_logging(app)` therefore runs after configuration is available and
validated, but before any application component emits a managed startup log.

### Standard request_id and event context

Use a `contextvars.ContextVar` for the shared correlation context. At the start
of every Flask request, generate `uuid.uuid4().hex`, set it as `request_id`,
and retain it for all records emitted in that request. Distinct requests get
distinct non-empty values. Reset the ContextVar token in request teardown so
completion—including exceptional completion—cannot leak context to later work.

Every managed record receives a `request_id`; outside an active Flask request
or explicit correlation context it is exactly `-`. MCP/non-request execution
can set an explicit correlation identifier through the shared context. A
client-supplied `X-Request-ID` is never adopted in this Change. `request_id` is
not a user ID, session ID, action ID, authentication token, or student ID.

A filter injects the exact `request_id` and `event` fields before formatting,
with `-` as the event fallback. This ensures records remain formattable when
optional application metadata is absent. `log_security_event(event, *,
level=..., **safe_metadata)` is the future-facing API; it has no login or
authorization behavior in this Change.

Alternative: use Flask `g` or an incoming header. Rejected because Flask `g`
does not cover MCP/non-request work and trusting client identifiers is outside
scope.

### Formatter and output targets

The shared human-readable formatter renders timestamp, level, logger,
request_id, event, and message. Console logging is enabled by default. File
logging is opt-in through central configuration and uses `RotatingFileHandler`
with default `instance/logs/app.log`, 5 MB `maxBytes`, and `backupCount=5`.
The directory is created only when file logging is enabled. Testing disables
development/production runtime file targets, while an explicitly supplied
temporary test path and small test-only rotation threshold can exercise rollover.

MCP's console handler explicitly writes to `sys.stderr`; stdout remains solely
for MCP protocol messages.

### Boundary redaction

The policy-owned filter/sanitizer creates safe copies; it never mutates
caller-owned mappings, sequences, or exception objects. It recursively
sanitizes mappings, lists, tuples, sets, and nested sequences; sanitizes logging
arguments before message formatting; and sanitizes structured metadata and
event fields. It redacts password/password-hash, API-key, Authorization-header,
cookie, session-ID, CSRF-token, AI-confirmation-token, known development and
placeholder `SECRET_KEY` values, and complete student records.

Ordinary strings are sanitized with explicit sensitive-key and token-pattern
rules. Exception text is sanitized while traceback structure is retained. When
practical, only the sensitive portion is replaced rather than replacing an
entire safe message.

Heuristic string rules cannot guarantee detection of every arbitrary unknown
secret; minimising logged payloads and maintaining explicit rules/tests are
required complements. Manual call-site redaction alone is rejected because
exception and future security-event paths are easy to miss.

### Test-state restoration

Reusable pytest fixtures must snapshot and restore root and managed logger
handlers, levels, propagation flags, disabled flags, filters, idempotency
markers, relevant environment variables, Flask request context, and correlation
ContextVar state after every test. Managed file handlers are flushed and closed
before temporary directories are removed. No test may leak handlers, open files,
log levels, request IDs, environment overrides, or correlation context into a
later test.

## Risks / Trade-offs

- [Global logging state is process-wide] → use marked managed handlers and
  comprehensive restoration fixtures instead of broad root resets.
- [Redaction heuristics miss unknown secrets] → document the limit, redact
  known keys/patterns recursively, minimise payload logging, and test examples.
- [Tracebacks can contain sensitive exception arguments] → sanitize exception
  text but retain traceback structure and safe HTTP/MCP responses.
- [Rollover tests can leave open files on Windows] → flush/close handlers in
  fixtures before removing their temporary directories.
- [MCP stdout contamination breaks protocol] → bind logging to stderr and test
  captured stdout separately.

## Migration Plan

1. Add central settings, the shared policy, context, sanitization, and fixture
   support.
2. Apply the required factory ordering and route Flask/MCP startup, tool, and
   error logging through the policy.
3. Add focused logging tests, then run the complete suite and inspect the diff.
4. Update `.env.example` and `.gitignore` for optional runtime files.

Rollback is code-only: disable file logging or revert this focused Change. No
database, API, login, token, or user-data migration exists.

## Open Questions

- None. Authentication work will later select security-event names and actor
  metadata using this Change's interface.
