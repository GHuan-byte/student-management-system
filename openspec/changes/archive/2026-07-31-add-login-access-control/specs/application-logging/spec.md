## ADDED Requirements

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
