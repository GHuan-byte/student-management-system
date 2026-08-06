## ADDED Requirements

### Requirement: AI produces structured student actions
The system SHALL have the AI express student operations as controlled structured
actions with an approved `action_type` and server-validated `payload`/`target`,
instead of any free-form execution. The AI SHALL NOT emit JavaScript, arbitrary
CSS selectors, SQL, or script for the browser to run.

#### Scenario: Approved action types only
- **WHEN** the AI produces a student operation
- **THEN** the resulting action type SHALL be one of `create_student`,
  `update_student`, `delete_student`, `search_students`, `get_student`, or
  `count_students`
- **AND** any other operation SHALL be rejected without execution

#### Scenario: Write versus read classification
- **WHEN** the AI produces `create_student`, `update_student`, or `delete_student`
- **THEN** the action SHALL be classified as a write action with
  `requires_confirmation: true`
- **WHEN** the AI produces `search_students`, `get_student`, or `count_students`
- **THEN** the action SHALL be classified as a read action with
  `requires_confirmation: false`

#### Scenario: Payload and target are server-validated
- **WHEN** the AI produces an action payload or target
- **THEN** the server SHALL validate fields, types, ranges, and uniqueness using the
  existing `StudentService` rules
- **AND** `update_student` and `delete_student` SHALL reference a unique existing
  student by `student_id` or `student_number`

#### Scenario: AI cannot inject executable content
- **WHEN** the AI message or tool arguments are processed
- **THEN** the system SHALL NOT evaluate or execute any JavaScript produced by the
  AI
- **AND** the system SHALL NOT execute arbitrary CSS selectors, SQL, or URLs returned
  by the AI

### Requirement: Chat response includes a browser-safe guided action object
The system SHALL include a browser-safe `action` object in the chat response so the
frontend JSON-driven controller can play the matching animation. The `action` object
SHALL include `action_id`, `action_type`, `payload`, `target`, `target_page`,
`status`, `created_at`, and `expires_at`, and SHALL NOT include the confirmation
token or any secret. The `payload` SHALL use semantic student field names only.

#### Scenario: Write response includes the action object and token
- **WHEN** a write action is returned to the browser after a chat request
- **THEN** `data.action` SHALL contain `action_id`, `action_type`, `payload`,
  `target`, `target_page`, `status`, `created_at`, and `expires_at`
- **AND** `data.reply` SHALL be a deterministic Chinese message (for example
  "已准备添加学生，请确认。")
- **AND** `data.requires_confirmation` SHALL be `true`
- **AND** `data.confirmation_token` SHALL be a separate top-level field
- **AND** the existing `pending_action` summary fields SHALL remain available for the
  chat confirmation card

#### Scenario: Action object never contains secrets or executable content
- **WHEN** an action object is returned to the browser
- **THEN** it SHALL NOT contain the `confirmation_token`, API keys, `SECRET_KEY`,
  internal signing keys, or full raw student records
- **AND** it SHALL NOT contain JavaScript, DOM selectors, CSS selectors, SQL, URLs,
  or executable code strings

#### Scenario: Read actions are returned as guided actions without tokens
- **WHEN** a read action (`search_students`, `get_student`, `count_students`) is
  produced as a guided action
- **THEN** `data.action` SHALL be returned with `requires_confirmation: false`
- **AND** it SHALL NOT include a `confirmation_token`

### Requirement: AI action query endpoint for cross-page recovery
The system SHALL provide a server endpoint to re-fetch safe display data for a
pending action by `action_id` so the frontend can recover an in-progress action
after navigating from the Dashboard to `/students` or after a page refresh. The
endpoint SHALL NOT re-issue the confirmation token.

#### Scenario: GET returns safe display data to the same user
- **WHEN** an authenticated user requests `GET /api/chat/actions/<action_id>` for an
  action they created
- **THEN** the server SHALL return the browser-safe action object (`action_id`,
  `action_type`, `payload`, `target`, `target_page`, `status`,
  `requires_confirmation`, `created_at`, `expires_at`)
- **AND** it SHALL NOT return the `confirmation_token`
- **AND** the response SHALL use the unified JSON response structure
- **AND** the response SHALL set `Cache-Control: no-store`

#### Scenario: GET token rules are strict
- **WHEN** a GET query is evaluated
- **THEN** the `action_id` SHALL be server-generated and unpredictable
- **AND** the endpoint SHALL require an authenticated session
- **AND** an action belonging to another user SHALL return not-found or forbidden
- **AND** executed, expired, cancelled, or unknown actions SHALL NOT be returned as
  executable
- **AND** the endpoint SHALL NOT re-issue the confirmation token

#### Scenario: Other users cannot read the action
- **WHEN** a user requests an action that belongs to another user
- **THEN** the server SHALL return a not-found or forbidden error
- **AND** SHALL NOT expose the action or its token

#### Scenario: Executed, expired, cancelled, or missing actions are not retrievable
- **WHEN** a user requests an action that is already executed, expired, cancelled, or
  unknown
- **THEN** the server SHALL return a structured error
- **AND** SHALL NOT return a usable `confirmation_token`

### Requirement: AI action cancel endpoint
The system SHALL provide a server endpoint to cancel a pending action so that a
user cancel is enforced server-side and cannot later be confirmed with a still-valid
token.

#### Scenario: Cancel marks the action cancelled
- **WHEN** an authenticated user cancels an action via
  `POST /api/chat/actions/<action_id>/cancel`
- **THEN** the action SHALL transition to `cancelled`
- **AND** the server SHALL reject any later confirmation for that `action_id`
- **AND** no write SHALL be executed

#### Scenario: Cancel of an already executed action is rejected
- **WHEN** a user attempts to cancel an action that is already executed
- **THEN** the server SHALL return a structured error
- **AND** SHALL NOT change the executed result

### Requirement: Guided confirmation executes by action_id with server-held token
The system SHALL provide `POST /api/chat/actions/<action_id>/confirm` for the guided
flow, where the server holds the confirmation token and the browser does not need to
carry it across pages. The endpoint SHALL enforce CSRF, session, ownership, state,
and tool-role checks before consuming the token and executing the write through the
existing backend chain.

#### Scenario: Confirm by action_id succeeds for the owning user
- **WHEN** the owning user confirms `POST /api/chat/actions/<action_id>/confirm` with
  a valid CSRF token while the action is `waiting_confirmation`
- **THEN** the server SHALL verify the action exists, belongs to the user, and is in
  `waiting_confirmation`
- **AND** it SHALL check the tool-role authorization for the action's operation type
- **AND** it SHALL consume the server-held token via `consume_token`
- **AND** execute the write through the existing MCP → `StudentService` chain
- **AND** return `action_id`, `status`, and `action_result` in the response

#### Scenario: Non-owners, other users, and wrong states are rejected
- **WHEN** a confirmation is attempted by another user, or for an action in
  `cancelled`, `expired`, `succeeded`, `failed`, or `executing` state
- **THEN** the server SHALL return a structured error
- **AND** SHALL NOT execute any write

#### Scenario: Token does not cross page boundaries in the guided flow
- **WHEN** the guided flow continues from the Dashboard to `/students`
- **THEN** the `confirmation_token` SHALL NOT be written to `sessionStorage` or
  `localStorage`
- **AND** the GET endpoint SHALL NOT return it
- **AND** confirmation on `/students` SHALL use the server-held token via the
  action_id confirm endpoint

### Requirement: action_id and confirmation token are bound
The system SHALL bind the confirmation token to the `action_id`, the operation type,
and the server-validated arguments, and SHALL reject any confirmation where these do
not match.

#### Scenario: Token binds action_id, operation, and arguments
- **WHEN** a confirmation token is created for a write action
- **THEN** it SHALL embed `action_id`, `tool_name` (mapping to `action_type`), and
  the server-validated `arguments`
- **AND** the action store SHALL keep the token keyed by `action_id`

#### Scenario: Mismatched action_id or operation type is rejected
- **WHEN** a confirmation token's `action_id` does not match the confirmed action, or
  its `tool_name` does not map to the action's `action_type`
- **THEN** the server SHALL reject the confirmation with a structured error
- **AND** SHALL NOT execute any write

#### Scenario: Consumed token cannot execute again
- **WHEN** a token has been consumed
- **THEN** the server SHALL reject any later confirmation
- **AND** SHALL NOT execute the write again

### Requirement: Confirmation token never enters sessionStorage
The system SHALL keep the confirmation token out of `sessionStorage` and
`localStorage` even during the guided cross-page animation flow. The token SHALL
live only in server state and in the in-memory JavaScript state of the current tab,
and SHALL be re-fetched from the server by `action_id` when needed after navigation.

#### Scenario: Token is not persisted to browser storage
- **WHEN** a pending write action is in progress, including during cross-page
  animation
- **THEN** the `confirmation_token` SHALL NOT be written to `sessionStorage` or
  `localStorage`
- **AND** the browser SHALL obtain the token from the server by `action_id` when the
  animation resumes on `/students`

#### Scenario: Minimal action reference only
- **WHEN** an action reference is stored in `sessionStorage` for recovery
- **THEN** it SHALL contain only non-sensitive fields such as `action_id`,
  `action_type`, `target`, and `status`
- **AND** it SHALL NOT contain the token, full payload, or complete student records
