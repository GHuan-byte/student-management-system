## ADDED Requirements

### Requirement: Login-protected server-rendered pages
The Dashboard and student-management pages SHALL require login while preserving the existing Flask-rendered page model.

#### Scenario: Dashboard redirects unauthenticated user
- **WHEN** an unauthenticated browser requests `GET /`
- **THEN** the system SHALL redirect to `/login` with a safe site-local `next` value

#### Scenario: Student page redirects unauthenticated user
- **WHEN** an unauthenticated browser requests `GET /students`
- **THEN** the system SHALL redirect to `/login` with a safe site-local `next` value

#### Scenario: Authenticated user can render pages
- **WHEN** an authenticated Viewer, Staff, or Admin requests `GET /` or `GET /students`
- **THEN** the system SHALL render the existing server-side template flow
- **AND** it SHALL include the current username, current role, and CSRF token for browser interactions

### Requirement: Login page UI
The system SHALL provide a server-rendered login page that fits the existing visual language while using a simple centered card layout.

#### Scenario: Login form contains required controls
- **WHEN** `GET /login` renders for an unauthenticated user
- **THEN** the page SHALL show the system name, username field, password field, login button, generic error area, CSRF hidden field, and accessible labels

#### Scenario: Login copy is safe and readable
- **WHEN** the login page displays an error
- **THEN** the message SHALL be generic
- **AND** it SHALL NOT reveal whether a username exists
- **AND** user-visible Chinese text SHALL be readable and not mojibake

### Requirement: Role-aware browser controls
The browser UI SHALL hide unavailable student-management controls based on the current role while relying on backend authorization as the enforcement boundary.

#### Scenario: Viewer controls are read-only
- **WHEN** a Viewer renders the student-management page
- **THEN** create, edit, single-delete, and batch-delete entry points SHALL be hidden or disabled
- **AND** read-only list, search, sort, pagination, stats, and AI Chat entry points SHALL remain usable

#### Scenario: Staff controls exclude delete
- **WHEN** a Staff user renders the student-management page
- **THEN** create and edit entry points SHALL be available
- **AND** single-delete and batch-delete entry points SHALL be hidden or disabled

#### Scenario: Admin controls include all student actions
- **WHEN** an Admin renders the student-management page
- **THEN** create, edit, single-delete, and batch-delete entry points SHALL be available

### Requirement: Logout UI
The shared authenticated layout SHALL display the current username and role and provide a POST-only logout control.

#### Scenario: Authenticated layout shows identity
- **WHEN** an authenticated page renders
- **THEN** the top area SHALL show the current username and role

#### Scenario: Logout uses POST with CSRF
- **WHEN** a user activates logout
- **THEN** the browser SHALL submit `POST /logout` with a CSRF token
- **AND** logout SHALL NOT be implemented as a GET navigation

### Requirement: Browser unsafe requests include CSRF
Existing vanilla JavaScript browser requests that mutate student data or confirm AI actions SHALL include the CSRF token using `X-CSRF-Token`.

#### Scenario: Student mutations include CSRF header
- **WHEN** `students.js` sends create, update, single-delete, or batch-delete requests
- **THEN** it SHALL include `X-CSRF-Token`

#### Scenario: AI Chat unsafe requests include CSRF header
- **WHEN** `ai_chat.js` sends `POST /api/chat` or `POST /api/chat/actions/confirm`
- **THEN** it SHALL include `X-CSRF-Token`
