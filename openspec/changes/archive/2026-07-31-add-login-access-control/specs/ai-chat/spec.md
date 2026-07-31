## ADDED Requirements

### Requirement: AI Chat HTTP authentication and CSRF
The AI Chat HTTP routes SHALL require a current authenticated Flask user and SHALL validate CSRF for unsafe requests before processing browser chat payloads.

#### Scenario: Unauthenticated chat request is rejected
- **WHEN** an unauthenticated client sends `POST /api/chat`
- **THEN** the system SHALL return unified JSON status `401`
- **AND** it SHALL NOT call the AI Chat service

#### Scenario: Chat request without CSRF is rejected
- **WHEN** an authenticated client sends `POST /api/chat` without a valid CSRF token
- **THEN** the system SHALL return status `403`
- **AND** it SHALL NOT call the AI Chat service

#### Scenario: Authenticated read-only chat is allowed for all roles
- **WHEN** an authenticated Viewer, Staff, or Admin sends a valid read-only chat request with a valid CSRF token
- **THEN** the request SHALL be allowed to reach the existing AI Chat service flow

### Requirement: AI write action role authorization
AI write suggestions and confirmations SHALL be authorized by the current user role and the actual embedded MCP tool/action type.

#### Scenario: Viewer cannot receive executable write action
- **WHEN** a Viewer chat request would produce a pending write action
- **THEN** the system SHALL reject or suppress executable write confirmation behavior for that user
- **AND** it SHALL NOT execute the write action

#### Scenario: Staff may confirm add and edit actions
- **WHEN** a Staff user confirms a valid pending AI action for add, update, or upsert
- **THEN** the system SHALL allow the confirmation to proceed after token and CSRF validation

#### Scenario: Staff may not confirm delete actions
- **WHEN** a Staff user confirms a valid pending AI action for single delete or batch delete
- **THEN** the system SHALL return status `403`
- **AND** it SHALL NOT execute the MCP write tool

#### Scenario: Admin may confirm delete actions
- **WHEN** an Admin confirms a valid pending AI action for single delete or batch delete
- **THEN** the system SHALL allow the confirmation to proceed after token and CSRF validation

#### Scenario: Confirmation reloads current authorization
- **WHEN** `POST /api/chat/actions/confirm` receives a confirmation token
- **THEN** the system SHALL reload the current user from the database
- **AND** it SHALL confirm active status and `auth_version`
- **AND** it SHALL classify the tool/action embedded in the signed token
- **AND** it SHALL NOT rely only on a role captured when the pending action was created

#### Scenario: Existing confirmation safety remains
- **WHEN** AI write confirmation is authorized
- **THEN** the system SHALL still verify token signature, expiration, single-use consumption, and embedded tool arguments before execution
- **AND** it SHALL NOT execute any write before explicit confirmation

### Requirement: AI Chat preserves stdout and MCP trust boundary
HTTP authentication SHALL NOT change direct stdio MCP Server identity behavior or the MCP protocol.

#### Scenario: Direct MCP stdio remains out of scope
- **WHEN** the stdio MCP server is started directly
- **THEN** it SHALL NOT require Flask Session authentication
- **AND** its protocol behavior SHALL remain governed by the existing MCP stdio capability
