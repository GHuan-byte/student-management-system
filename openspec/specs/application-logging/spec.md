# application-logging Specification

## Purpose
TBD - created by archiving change configure-application-logging. Update Purpose after archive.
## Requirements
### Requirement: Shared application logging policy and standard fields
The system SHALL provide one shared logging configuration policy for Flask and
the stdio MCP server. Every managed record SHALL be formattable and contain the
exact fields `timestamp`, `level`, `logger`, `request_id`, `event`, and
`message`. `request_id` and `event` SHALL use `-` when no explicit value
exists.

#### Scenario: Flask and MCP records share the policy
- **WHEN** Flask or the MCP server emits an application log record
- **THEN** the record SHALL use the shared formatter and redaction policy
- **AND** it SHALL contain every standard field

#### Scenario: Optional metadata is absent
- **WHEN** a managed record has no explicit request context or event metadata
- **THEN** its `request_id` and `event` fields SHALL be `-`
- **AND** formatting SHALL not fail

### Requirement: Standard request_id contract
Every managed log record SHALL contain a `request_id`. At the beginning of each
Flask request, the application SHALL generate a server-side identifier using
`uuid.uuid4().hex`. It SHALL not adopt a client-provided `X-Request-ID` in this
Change.

#### Scenario: Records in one request share request_id
- **WHEN** multiple managed records are emitted while handling one Flask request
- **THEN** every record SHALL contain the same non-empty `request_id`

#### Scenario: Separate requests receive separate identifiers
- **WHEN** two separate Flask requests emit managed records
- **THEN** each request SHALL receive a distinct non-empty `request_id`

#### Scenario: Request correlation is reset
- **WHEN** a Flask request completes normally or exceptionally
- **THEN** its correlation context SHALL be reset before subsequent work runs
- **AND** a later record outside a request SHALL use `request_id` `-`

#### Scenario: Non-request correlation is explicit
- **WHEN** MCP or non-request execution supplies an explicit identifier through the shared correlation context
- **THEN** managed records in that context SHALL use the supplied identifier
- **AND** records with no active request or explicit context SHALL use `-`

#### Scenario: request_id is not an identity or token
- **WHEN** the application creates a request identifier
- **THEN** it SHALL not use a user ID, session ID, action ID, authentication token, or student identifier
- **AND** it SHALL not trust a client-provided request identifier

### Requirement: Configurable and idempotent logging setup
The system SHALL configure Flask logging through `logging.config.dictConfig`.
Every logging `dictConfig` mapping SHALL include `disable_existing_loggers: false`.
`LOG_LEVEL` SHALL be configurable and default to `INFO`. Repeating
Flask app creation or logging setup SHALL not duplicate managed handlers or log
output, and SHALL preserve unrelated third-party logger state.

#### Scenario: Default level is used
- **WHEN** `LOG_LEVEL` is unset
- **THEN** the shared logging policy SHALL configure `INFO`

#### Scenario: Configured level is used
- **WHEN** `LOG_LEVEL` is set to a supported value
- **THEN** the shared logging policy SHALL configure that normalized level

#### Scenario: Setup is repeated
- **WHEN** multiple Flask applications are created in one Python process
- **THEN** managed handlers SHALL not accumulate
- **AND** one emitted record SHALL not be written multiple times by duplicate managed handlers

#### Scenario: Third-party logger state is preserved
- **WHEN** logging setup is repeated
- **THEN** it SHALL not reset unrelated third-party logger handlers, levels, propagation flags, disabled flags, or filters

### Requirement: Console and rotating file logging
The shared policy SHALL support console logging by default and optional rotating
file logging. When enabled, file logging SHALL use `RotatingFileHandler` with a
default path of `instance/logs/app.log`, a default maximum file size of 5 MB,
and five backups. The log directory SHALL be created only when file logging is
enabled.

#### Scenario: File logging is disabled
- **WHEN** rotating file logging is disabled
- **THEN** console logging SHALL remain available
- **AND** logging setup SHALL not create the default log directory

#### Scenario: File logging is enabled
- **WHEN** rotating file logging is enabled without an explicit path
- **THEN** records SHALL be written to `instance/logs/app.log`
- **AND** the parent directory SHALL be created
- **AND** rotation SHALL use a 5 MB maximum file size and five backups

#### Scenario: Actual file rollover is verified
- **WHEN** a test enables file logging with an isolated temporary path and a small test-only size threshold
- **THEN** the base log file SHALL be created
- **AND** writing beyond the threshold SHALL create a rollover file
- **AND** no more than the configured backup count SHALL be retained
- **AND** file handlers SHALL be flushed and closed before the test removes the temporary directory

#### Scenario: Testing is isolated from runtime log files
- **WHEN** the testing configuration creates an application
- **THEN** it SHALL not write development or production runtime log files
- **AND** tests SHALL only opt into an isolated temporary file target explicitly

### Requirement: Safe exception and security-event logging
Unexpected Flask exceptions SHALL be logged with full traceback information.
The system SHALL provide a reusable security-event logging interface for later
login, logout, authentication failure, and forbidden-access events without
implementing those authentication behaviors in this Change.

#### Scenario: Flask unexpected exception
- **WHEN** an unhandled exception reaches Flask's global error handler
- **THEN** the server response SHALL remain the existing safe unified internal-error response
- **AND** the corresponding log record SHALL retain the full traceback structure

#### Scenario: Future security event is recorded
- **WHEN** application code calls the reusable security-event logging interface
- **THEN** it SHALL emit a structured event with `event` and `request_id`
- **AND** it SHALL pass through the shared redaction policy

### Requirement: Sensitive data and student-record redaction
The shared logging policy SHALL exclude or redact passwords, password hashes,
API keys, Authorization headers, cookies, session identifiers, CSRF tokens, AI
confirmation tokens, known unsafe development and placeholder `SECRET_KEY`
values, and complete student records from formatted log output. The sanitizer
SHALL recursively sanitize mappings, lists, tuples, sets, nested sequences,
logging arguments before message formatting, structured metadata, event fields,
ordinary strings using explicit sensitive-key and token-pattern rules, and
exception text without suppressing traceback structure. It SHALL not mutate
caller-owned mappings, sequences, or exception objects.

#### Scenario: Sensitive structured values are supplied
- **WHEN** a logger receives sensitive structured data or a complete student record
- **THEN** recursively formatted output SHALL not contain the original sensitive value or complete record
- **AND** the caller-owned value SHALL remain unchanged

#### Scenario: Sensitive string or exception text is supplied
- **WHEN** a message, logging argument, or exception text contains a known sensitive value
- **THEN** the formatted output SHALL redact only the sensitive portion where practical
- **AND** it SHALL retain safe surrounding text and traceback structure

#### Scenario: Unsafe secret-key values occur in an error
- **WHEN** an exception or event data contains the development `SECRET_KEY` or placeholder `SECRET_KEY`
- **THEN** formatted output SHALL not contain either value
- **AND** logging SHALL not change production secret-key validation or AI Action Confirmation behavior

### Requirement: MCP stdio logging safety
The stdio MCP server SHALL use the shared logging formatter and redaction policy.
All MCP logging output SHALL be written to stderr and SHALL never be written to
the protocol stdout stream.

#### Scenario: MCP startup and tool operation logging
- **WHEN** the MCP server starts or a student tool logs its outcome
- **THEN** its log record SHALL be emitted through the shared policy to stderr
- **AND** stdout SHALL remain available exclusively for MCP protocol messages

### Requirement: Runtime log files are not committed
Runtime log files produced by the logging policy SHALL be ignored by Git.

#### Scenario: Default runtime log file exists
- **WHEN** file logging creates `instance/logs/app.log` or its rotated backups
- **THEN** Git ignore rules SHALL exclude those runtime log files from commits

### Requirement: Existing service behavior is preserved
The logging change SHALL not alter existing REST response contracts, MCP
structured-result contracts, student CRUD rules, or AI Action Confirmation token
creation, verification, expiry, or consumption behavior.

#### Scenario: Existing API and MCP behavior after logging setup
- **WHEN** existing REST routes or MCP student tools are exercised with logging enabled
- **THEN** they SHALL retain their established success and safe-error behavior
- **AND** logging SHALL not introduce protocol output into MCP stdout

### Requirement: Login and access-control security events
Authentication and authorization flows SHALL emit structured security events through the existing shared `log_security_event()` interface and redaction policy.

#### Scenario: Authentication events use shared logging
- **WHEN** login succeeds, login fails, logout succeeds, or an inactive account attempts login
- **THEN** the system SHALL emit a security event through `log_security_event()`
- **AND** the formatted record SHALL use the shared application logging fields and redaction policy

#### Scenario: Bootstrap user events use shared logging
- **WHEN** startup bootstrap creates a default role account or skips an already existing role account
- **THEN** the system SHALL emit a security event through `log_security_event()`
- **AND** created-account events SHALL use `event` `bootstrap_user_created`
- **AND** the event SHALL include only safe metadata such as username, role, and outcome

#### Scenario: Access-control events use shared logging
- **WHEN** a request is rejected for missing login, forbidden role, CSRF failure, stale `auth_version`, or inactive account session
- **THEN** the system SHALL emit a security event through `log_security_event()`
- **AND** the event SHALL include only safe metadata such as endpoint, method, user id, role, username, or reason code

#### Scenario: Login security events do not leak sensitive values
- **WHEN** authentication or authorization security events are formatted
- **THEN** logs SHALL NOT contain plaintext passwords, password hashes, CSRF tokens, session IDs, cookie values, Authorization headers, AI confirmation tokens, API keys, raw request bodies, complete environment configuration, or complete student records

