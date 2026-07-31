# login-access-control Specification

## Purpose
TBD - created by archiving change add-login-access-control. Update Purpose after archive.
## Requirements
### Requirement: Local user account storage
The system SHALL persist local login accounts in a SQLite `users` table created by application startup schema initialization. The table SHALL include `id`, `username`, `password_hash`, `role`, `is_active`, `auth_version`, `created_at`, `updated_at`, and `last_login_at`.

#### Scenario: Users table is initialized explicitly
- **WHEN** the Flask application startup database initialization runs
- **THEN** the `users` table SHALL be created if it does not exist
- **AND** existing student data SHALL NOT be deleted

#### Scenario: User fields and constraints are enforced
- **WHEN** the `users` table is created
- **THEN** `username` SHALL be unique
- **AND** `role` SHALL be constrained to `viewer`, `staff`, or `admin`
- **AND** `is_active` SHALL represent a boolean state
- **AND** `auth_version` SHALL default to `1`
- **AND** `created_at` and `updated_at` SHALL be stored as UTC ISO 8601 timestamps

#### Scenario: User data follows the service boundary
- **WHEN** routes, guards, bootstrap startup, or optional CLI commands need user account data
- **THEN** they SHALL call a user service
- **AND** the user service SHALL call a user repository
- **AND** SQL SHALL remain inside repository or database modules

### Requirement: Password hashing and login verification
The system SHALL use Werkzeug `generate_password_hash` and `check_password_hash` for local password handling and SHALL never store or log plaintext passwords.

#### Scenario: Account creation hashes passwords
- **WHEN** a user account is created
- **THEN** the database SHALL store only `password_hash`
- **AND** it SHALL NOT store the plaintext password

#### Scenario: Login failure is generic
- **WHEN** a login attempt uses a nonexistent username, wrong password, inactive account, or otherwise invalid credentials
- **THEN** the user-facing response SHALL use a generic failure message
- **AND** it SHALL NOT reveal which condition occurred

#### Scenario: Password data is excluded from logs
- **WHEN** login or account-creation code emits logs or security events
- **THEN** it SHALL NOT include plaintext passwords or password hashes

### Requirement: Bootstrap default role accounts
The system SHALL support an optional startup bootstrap feature that creates configured default Viewer, Staff, and Admin role accounts without hardcoded passwords.

#### Scenario: Bootstrap configuration keys are supported
- **WHEN** the application configuration is loaded
- **THEN** it SHALL support `BOOTSTRAP_DEFAULT_USERS_ENABLED`, `BOOTSTRAP_VIEWER_USERNAME`, `BOOTSTRAP_VIEWER_PASSWORD`, `BOOTSTRAP_STAFF_USERNAME`, `BOOTSTRAP_STAFF_PASSWORD`, `BOOTSTRAP_ADMIN_USERNAME`, and `BOOTSTRAP_ADMIN_PASSWORD`

#### Scenario: Bootstrap disabled creates no users
- **WHEN** `BOOTSTRAP_DEFAULT_USERS_ENABLED` is false
- **THEN** application startup SHALL NOT create Viewer, Staff, Admin, `admin/admin`, or any other implicit account
- **AND** the rest of the application SHALL be able to start normally

#### Scenario: Bootstrap enabled creates missing role users
- **WHEN** `BOOTSTRAP_DEFAULT_USERS_ENABLED` is true and valid distinct usernames and passwords are configured for Viewer, Staff, and Admin
- **THEN** startup SHALL create missing users for fixed roles `viewer`, `staff`, and `admin`
- **AND** it SHALL use Werkzeug `generate_password_hash()` for each configured password
- **AND** the database SHALL NOT store plaintext passwords

#### Scenario: Default usernames may be overridden
- **WHEN** bootstrap usernames are configured
- **THEN** the system SHALL normalize and use the configured usernames
- **AND** the role mapping SHALL remain fixed as Viewer username to `viewer`, Staff username to `staff`, and Admin username to `admin`
- **AND** untrusted client input SHALL NOT be able to alter the role mapping

#### Scenario: Bootstrap is idempotent
- **WHEN** application startup runs repeatedly with the same bootstrap configuration
- **THEN** existing accounts SHALL NOT be duplicated
- **AND** existing account passwords SHALL NOT be overwritten
- **AND** existing account roles SHALL NOT be silently overwritten
- **AND** existing inactive accounts SHALL NOT be re-enabled

#### Scenario: Bootstrap startup order is enforced
- **WHEN** the Flask application starts
- **THEN** it SHALL create the Flask app, load and validate configuration, configure logging, initialize the database and `users` table, call `ensure_bootstrap_users()`, and only then register services and entrypoints that depend on account state
- **AND** `ensure_bootstrap_users()` SHALL follow Application Factory to UserService to UserRepository to SQLite
- **AND** the application factory SHALL NOT directly execute user SQL

#### Scenario: Bootstrap validation fails safely
- **WHEN** bootstrap is enabled and any required username or password is missing, any normalized usernames duplicate each other, a username is invalid, or a password is shorter than 6 characters
- **THEN** application startup SHALL fail safely
- **AND** the error message and logs SHALL NOT include passwords, password hashes, or full environment configuration

#### Scenario: Environment files do not contain usable passwords
- **WHEN** `.env.example` documents bootstrap configuration
- **THEN** it SHALL include usernames and empty password placeholders only
- **AND** it SHALL NOT include usable default passwords

#### Scenario: Environment-specific bootstrap policy
- **WHEN** the app runs in development
- **THEN** local `.env` may explicitly enable bootstrap
- **WHEN** the app runs in testing
- **THEN** tests SHALL use isolated configuration and temporary databases rather than development or production passwords
- **WHEN** the app runs in production
- **THEN** bootstrap SHALL default to disabled
- **AND** production SHALL NOT use any source-code default password

### Requirement: Login and logout routes
The system SHALL provide `GET /login`, `POST /login`, and `POST /logout` for browser authentication.

#### Scenario: Login page for unauthenticated user
- **WHEN** an unauthenticated browser requests `GET /login`
- **THEN** the system SHALL render a login form
- **AND** the form SHALL include a CSRF token
- **AND** it SHALL NOT disclose whether any username exists

#### Scenario: Login page for authenticated user
- **WHEN** an authenticated browser requests `GET /login`
- **THEN** the system SHALL redirect to `/`

#### Scenario: Successful login establishes a fresh session
- **WHEN** a user submits valid credentials and a valid CSRF token to `POST /login`
- **THEN** the system SHALL clear any previous session state
- **AND** it SHALL store only minimal identity data and a CSRF token in the new session
- **AND** it SHALL update `last_login_at`
- **AND** it SHALL redirect to `/` by default or to a safe site-local `next` path

#### Scenario: Login rejects open redirects
- **WHEN** `POST /login` receives an absolute, scheme-relative, cross-site, or otherwise unsafe `next` value
- **THEN** the system SHALL ignore that value
- **AND** it SHALL redirect to the safe default path `/`

#### Scenario: Logout clears session
- **WHEN** an authenticated user submits `POST /logout` with a valid CSRF token
- **THEN** the system SHALL clear the session
- **AND** it SHALL redirect to `/login`

#### Scenario: Logout is not GET
- **WHEN** a browser sends `GET /logout`
- **THEN** the system SHALL NOT log out the user through that request

### Requirement: Flask Session and secure cookie policy
The system SHALL use Flask Session for browser login state with bounded, secure cookie settings.

#### Scenario: Session stores only minimal identity data
- **WHEN** a user is authenticated
- **THEN** the session SHALL store `user_id`, `auth_version`, and `csrf_token`
- **AND** it SHALL NOT store passwords, password hashes, full user objects, full student records, API keys, cookies, session IDs, or a trusted long-term role copy

#### Scenario: Protected request reloads current user
- **WHEN** a protected page or API request is processed
- **THEN** the system SHALL load the current user from SQLite by `user_id`
- **AND** it SHALL confirm the user exists, is active, and has a matching `auth_version`
- **AND** it SHALL use the current database role for authorization

#### Scenario: Disabled or stale session is invalidated
- **WHEN** the session references a missing user, inactive user, or stale `auth_version`
- **THEN** the system SHALL clear the session
- **AND** the request SHALL be treated as unauthenticated

#### Scenario: Cookie settings are safe
- **WHEN** the Flask app is configured
- **THEN** the session cookie SHALL have an explicit name
- **AND** `SESSION_COOKIE_HTTPONLY` SHALL be true
- **AND** `SESSION_COOKIE_SAMESITE` SHALL be `Lax`
- **AND** the permanent session lifetime SHALL be bounded
- **AND** `SESSION_COOKIE_SECURE` SHALL be true in production

#### Scenario: Production secret key is strong
- **WHEN** the app runs in production configuration
- **THEN** a missing, empty, development-default, or placeholder `SECRET_KEY` SHALL be rejected

### Requirement: CSRF protection for unsafe HTTP requests
The system SHALL provide a native synchronizer-token CSRF mechanism without adding third-party dependencies.

#### Scenario: CSRF token is issued
- **WHEN** the login page or a protected page renders
- **THEN** the page SHALL provide a CSRF token through a hidden form field, a safe meta tag, or both
- **AND** the token SHALL be stored in the signed Flask session

#### Scenario: Unsafe requests require CSRF
- **WHEN** a request uses `POST`, `PUT`, `PATCH`, or `DELETE`
- **THEN** the system SHALL validate a submitted CSRF token from form data or the `X-CSRF-Token` header
- **AND** token comparison SHALL use a constant-time comparison

#### Scenario: Safe requests do not require CSRF
- **WHEN** a request uses `GET`, `HEAD`, or `OPTIONS`
- **THEN** the system SHALL NOT require a CSRF token

#### Scenario: CSRF failure is safe
- **WHEN** an unsafe request has a missing or invalid CSRF token
- **THEN** the system SHALL return a safe `403`
- **AND** it SHALL NOT log the submitted token or session token

#### Scenario: Login and logout are protected
- **WHEN** a browser submits `POST /login` or `POST /logout`
- **THEN** the system SHALL require a valid CSRF token

### Requirement: Role-based authorization
The system SHALL enforce Viewer, Staff, and Admin authorization on the server for every protected page, student API, and AI Chat HTTP entrypoint.

#### Scenario: Viewer permissions
- **WHEN** a user has role `viewer`
- **THEN** the user SHALL be allowed to access the Dashboard, student list, student detail, search, pagination, sorting, statistics, and read-only AI Chat
- **AND** the user SHALL be forbidden from creating, editing, upserting, deleting, batch deleting, or executing AI write actions

#### Scenario: Staff permissions
- **WHEN** a user has role `staff`
- **THEN** the user SHALL have Viewer permissions
- **AND** the user SHALL be allowed to create, edit, and upsert students
- **AND** the user SHALL be allowed to execute AI add/edit confirmations
- **AND** the user SHALL be forbidden from single delete, batch delete, and user-account management

#### Scenario: Admin permissions
- **WHEN** a user has role `admin`
- **THEN** the user SHALL have all student-management permissions including create, edit, upsert, single delete, batch delete, and AI write confirmation execution

#### Scenario: Frontend hiding is not sufficient
- **WHEN** a browser forges a request to a forbidden endpoint
- **THEN** the backend SHALL re-check the current role
- **AND** it SHALL reject the request if the role is not allowed

### Requirement: HTTP authentication responses
The system SHALL distinguish browser page authentication behavior from API authentication behavior.

#### Scenario: Unauthenticated protected page redirects
- **WHEN** an unauthenticated browser requests `/` or `/students`
- **THEN** the system SHALL redirect to `/login`
- **AND** it SHALL preserve only a safe site-local `next` path

#### Scenario: Unauthenticated API returns JSON 401
- **WHEN** an unauthenticated client requests a protected API endpoint
- **THEN** the system SHALL return the unified JSON response structure with status `401`
- **AND** it SHALL NOT redirect to an HTML login page

#### Scenario: Unauthorized API returns JSON 403
- **WHEN** an authenticated user requests an API endpoint without the required role
- **THEN** the system SHALL return the unified JSON response structure with status `403`

#### Scenario: Unauthorized page returns safe 403 page
- **WHEN** an authenticated user requests a page that their role cannot access
- **THEN** the system SHALL return a safe `403` HTML page

#### Scenario: Public routes remain public
- **WHEN** a client requests `/login`, `/api/health`, or a static file
- **THEN** the system SHALL NOT require login for that request

### Requirement: Optional account-management CLI
The system MAY provide Flask CLI account-management helpers, but CLI account creation SHALL NOT be required as the initial account creation path for this Change.

#### Scenario: Bootstrap is sufficient for initial roles
- **WHEN** this Change is complete
- **THEN** the required initial Viewer, Staff, and Admin accounts SHALL be creatable through startup bootstrap configuration
- **AND** manual acceptance SHALL NOT require running `flask create-admin`

#### Scenario: Optional CLI does not accept plaintext password arguments
- **WHEN** optional account-management CLI commands are provided
- **THEN** they SHALL NOT accept plaintext passwords as command-line arguments

#### Scenario: Optional CLI cannot weaken bootstrap rules
- **WHEN** optional account-management CLI commands are provided
- **THEN** they SHALL preserve password hashing, username normalization, role validation, and no-secret-logging rules

### Requirement: Authentication security events
The system SHALL emit structured security events for authentication and authorization behavior using the existing `log_security_event()` interface.

#### Scenario: Login and logout events are recorded
- **WHEN** a login succeeds, login fails, or logout succeeds
- **THEN** the system SHALL emit a security event with a stable event name
- **AND** it SHALL include only safe metadata

#### Scenario: Authorization and CSRF events are recorded
- **WHEN** a request is forbidden, rejected for CSRF, or invalidated because of inactive account or stale `auth_version`
- **THEN** the system SHALL emit a security event with a stable event name
- **AND** it SHALL include only safe metadata

#### Scenario: Bootstrap events are recorded safely
- **WHEN** startup bootstrap creates a configured role account
- **THEN** the system SHALL emit a security event with `event` `bootstrap_user_created`
- **AND** it SHALL include safe metadata such as username, role, and outcome
- **WHEN** startup bootstrap skips an existing configured account
- **THEN** the system MAY emit a safe summary event
- **AND** it SHALL NOT log passwords, password hashes, cookies, sessions, CSRF tokens, API keys, or full environment configuration

#### Scenario: Security events do not leak secrets
- **WHEN** authentication or authorization security events are formatted
- **THEN** they SHALL NOT contain passwords, password hashes, CSRF tokens, session IDs, cookie values, AI confirmation tokens, API keys, raw request bodies, full environment configuration, or complete student records

