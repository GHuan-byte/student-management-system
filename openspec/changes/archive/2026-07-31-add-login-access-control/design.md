## Context

The current Flask app is server-rendered and uses blueprints for pages, student REST APIs, health, and AI Chat. Student data access already follows the route → service → repository → SQLite boundary. Database initialization is explicit through `flask init-db`, and the application logging change has introduced shared logging plus `log_security_event()` for future authentication and authorization events.

The system currently has no user account table, no login page, no Flask Session identity, no CSRF protection, and no role checks. The existing public behavior includes Dashboard at `/`, student management at `/students`, student APIs under `/api/students`, AI Chat under `/api/chat`, and health at `/api/health`.

## Goals / Non-Goals

**Goals:**

- Add local username/password authentication with Werkzeug password hashing and SQLite-backed users.
- Add a configurable startup bootstrap flow that can create Viewer, Staff, and Admin accounts from explicit environment configuration.
- Protect Dashboard, student pages, student APIs, AI Chat, and AI Action Confirmation with server-side authentication and role authorization.
- Add native Flask Session and synchronizer-token CSRF protection without new dependencies.
- Add role-aware Viewer, Staff, and Admin behavior while preserving existing student and AI workflows for permitted users.
- Keep any account-management CLI optional; it is not the required initial-account path for this change.
- Emit login, logout, authentication failure, session invalidation, CSRF failure, and forbidden-access security events through `log_security_event()`.

**Non-Goals:**

- No registration, password reset, email/SMS verification, OAuth, LDAP, SSO, MFA, user-management frontend, JWT, API tokens, Redis sessions, external session store, or login rate-limit platform.
- No Flask-Login, Flask-WTF, or other new third-party authentication/CSRF dependency.
- No direct stdio MCP Server identity authentication and no MCP stdio protocol change.
- No changes to student business rules, AI confirmation token safety rules, or MCP tool semantics except HTTP route access checks before those flows run.
- No user registration, user-management frontend, online password change, password recovery, or source-code default password.

## Decisions

### 1. Native Flask Session plus explicit current-user loader

Use Flask’s signed cookie session for the browser login state. Store only `user_id`, `auth_version`, and `csrf_token` in the session. Do not store password data, password hashes, complete users, complete student records, API keys, session identifiers, cookies, or a trusted long-term role copy.

Every protected request reloads the user by `user_id` from SQLite through a new `UserService` and `UserRepository`, confirms the account still exists and is active, checks `auth_version`, and uses the current database role for authorization. This keeps role changes and account disablement effective without relying on stale client-side session content.

Alternative considered: Flask-Login. Rejected because this change explicitly avoids third-party auth dependencies and the current requirements are small enough for an explicit service/guard layer.

### 2. User data follows the existing route → service → repository → SQLite boundary

Add a `users` table during explicit database initialization. Add a user repository for SQL-only operations and a user service for username normalization, password verification, password hashing, role validation, active-account checks, `auth_version`, and `last_login_at` updates. Routes and decorators must not execute SQL directly.

The `users` schema contains `id`, `username`, `password_hash`, `role`, `is_active`, `auth_version`, `created_at`, `updated_at`, and `last_login_at`. `username` is unique after normalization. `role` is constrained to `viewer`, `staff`, or `admin`. `is_active` is a boolean-like persisted state. `auth_version` defaults to `1` and is used to invalidate existing sessions. Timestamps use the project’s UTC ISO 8601 convention, and `last_login_at` is nullable until the first successful login.

Username normalization is lower-case plus surrounding whitespace trimming. The canonical normalized username is stored and used for uniqueness and login lookup.

Alternative considered: combine user operations into `StudentRepository`. Rejected because identity data is a separate domain and should not blur student CRUD responsibilities.

### 3. Configurable startup bootstrap accounts

Use startup bootstrap as the approved initial-account path. When `BOOTSTRAP_DEFAULT_USERS_ENABLED=true`, the application validates three configured accounts and creates missing users for the fixed roles `viewer`, `staff`, and `admin`. Supported configuration keys are:

- `BOOTSTRAP_DEFAULT_USERS_ENABLED`
- `BOOTSTRAP_VIEWER_USERNAME`
- `BOOTSTRAP_VIEWER_PASSWORD`
- `BOOTSTRAP_STAFF_USERNAME`
- `BOOTSTRAP_STAFF_PASSWORD`
- `BOOTSTRAP_ADMIN_USERNAME`
- `BOOTSTRAP_ADMIN_PASSWORD`

Default usernames may be overridden through configuration, but role mapping is fixed by server-side configuration code and cannot be supplied by an untrusted browser/client request. Passwords must come from explicit environment or test configuration and must not be hardcoded in Python, committed config, `.env.example`, JavaScript, HTML, or production-default test values.

The startup sequence is:

1. Create the Flask app object.
2. Load, override, normalize, and validate configuration.
3. Configure shared logging.
4. Initialize the database schema, including `users`.
5. Call `ensure_bootstrap_users()`.
6. Register services, request hooks, blueprints, CLI commands, and other entrypoints that depend on account state.

`ensure_bootstrap_users()` follows Application Factory → `UserService` → `UserRepository` → SQLite. The application factory may orchestrate the call but must not execute user SQL directly.

When enabled, bootstrap creates each missing configured account using Werkzeug password hashing. Existing accounts are skipped: startup must not create duplicates, overwrite passwords, overwrite roles, or re-enable disabled accounts. Repeated startup is idempotent. When disabled, no account is created, and the app must not silently create `admin/admin` or any other weak account.

Bootstrap and account-creation passwords use a simple minimum length rule of at least 6 characters. This is intentionally a baseline guard, not a complex enterprise password policy.

Development may opt in through local `.env`. Testing must use isolated config and temporary databases, never development or production secrets. Production defaults to `BOOTSTRAP_DEFAULT_USERS_ENABLED=false`; production bootstrap is allowed only when explicitly configured and validated.

Alternative considered: require `flask create-admin` as the only initial-account path. Rejected by the updated product decision because manual CLI setup is more awkward for local acceptance of all three roles and does not exercise the intended startup account lifecycle.

Alternative considered: ship hardcoded default passwords. Rejected because it creates committed credentials and unsafe production behavior.

### 4. Route guards and unified API failures

Implement explicit login-required and role-required guards for pages and APIs. HTML page requests without login redirect to `/login` with a safe site-local `next` path. API requests without login return unified JSON `401`. API requests with insufficient role return unified JSON `403`. Page authorization failures return a safe `403` HTML page rather than redirecting to an unrelated page.

Public routes are limited to `/login`, `/api/health`, and static files. POST `/logout` requires login and CSRF.

Alternative considered: a global `before_request` allow/deny table only. Rejected as the sole mechanism because individual route role requirements need to be explicit and testable. A shared `before_request` may still load current user and enforce CSRF, but endpoint permissions should be declared close to routes or through a central named policy map.

### 5. Native synchronizer-token CSRF

Generate a random CSRF token and store it in the signed Flask session. Login forms and protected pages expose the token through hidden fields and/or a safe meta tag. Unsafe HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`) validate either form token or `X-CSRF-Token` using constant-time comparison. `GET`, `HEAD`, and `OPTIONS` do not require CSRF.

CSRF failure returns `403` and emits a security event without logging token values.

Alternative considered: Flask-WTF. Rejected because no new dependency is allowed.

### 6. Role model and AI action classification

Use the roles `viewer`, `staff`, and `admin` with a fixed permission matrix:

- Viewer: read pages, list/detail/search/sort/paginate/stats, read-only AI Chat.
- Staff: Viewer plus create/update/upsert students and AI add/edit confirmations.
- Admin: Staff plus single delete, batch delete, and AI delete confirmations.

`/api/chat` must require login. If a chat request only produces a read-only response, all roles may use it. If it produces a pending write action, the pending action may be shown only if the current role is allowed for that actual tool/action type. `/api/chat/actions/confirm` must re-authenticate the current user, verify CSRF, reload current role from the database, verify the confirmation token, classify the embedded tool name/action type, and only then execute the permitted action. It must not trust a role captured when the pending action was created.

Alternative considered: rely on frontend-hidden controls and pending-action metadata. Rejected because forged browser requests must not bypass server-side authorization.

### 7. Security-event logging without sensitive payloads

Use `log_security_event()` for successful login, failed login, logout, CSRF failure, forbidden access, disabled-account login attempt, stale session invalidation, bootstrap user creation, and safe bootstrap skip summaries. Events may include safe metadata such as normalized username, user id, role, route/endpoint, outcome, and reason codes, but must not include passwords, password hashes, CSRF tokens, session cookies, confirmation tokens, API keys, full student records, full environment configuration, or raw request bodies.

The existing shared logging sanitizer remains the redaction boundary; this change must not weaken application logging or make security events bypass it.

### 8. Cookie and secret configuration

Configure a clear session cookie name, `HttpOnly=true`, `SameSite=Lax`, bounded permanent lifetime, and `SESSION_COOKIE_SECURE=true` in production. Production must continue to reject missing or development-default `SECRET_KEY` values. Login success clears any existing session before setting the new minimal identity and CSRF data to prevent session fixation. Logout clears the session.

## Risks / Trade-offs

- **Native auth/CSRF code can drift if scattered** → Keep authentication, CSRF, and role checks in small shared helpers/services with focused tests.
- **Role changes may not affect active sessions if role is trusted from session** → Reload current user and role from the database on every protected request; store only `user_id` and `auth_version` in session.
- **CSRF rollout can break existing JavaScript mutations** → Add a shared token source in `base.html` and update `students.js` and `ai_chat.js` unsafe requests together.
- **AI pending actions can become a privilege-escalation path** → Re-check current role at confirmation time based on the signed token’s embedded tool name and arguments before execution.
- **Login failures can leak account existence** → Use generic user-facing errors for nonexistent users, wrong passwords, inactive users, and stale credentials while logging only safe reason codes.
- **Bootstrap configuration can leak passwords through logs or examples** → Never log passwords or password hashes; keep `.env.example` passwords empty; validate without echoing secret values.
- **Bootstrap can accidentally overwrite operator-managed accounts** → Skip existing accounts without changing password, role, active state, or `auth_version`.
- **Bootstrap can create unsafe accounts when misconfigured** → Fail safely when enabled with missing usernames/passwords, duplicate normalized usernames, invalid usernames, or weak passwords; default production bootstrap to disabled.

## Migration Plan

1. Extend schema initialization to create `users` without deleting existing `students` data.
2. Add user repository/service and tests against isolated temporary SQLite databases.
3. Add bootstrap configuration parsing, validation, and `ensure_bootstrap_users()` through the user service.
4. Add auth/CSRF helpers and route protections with Flask test-client coverage.
5. Update templates and JavaScript to include CSRF tokens, role-aware UI affordances, and POST logout.
6. Optionally keep or add CLI account-management helpers, but do not make them required for completion.
7. Run focused tests first, then full regression and `git diff --check` before implementation completion.

Rollback is file-level: because schema changes are additive, reverting application code disables login behavior but does not require deleting user rows. A manual database rollback may drop `users` only after confirming no production identity data must be retained.

## Open Questions

- None for planning. The design chooses startup bootstrap as the required initial-account path, a safe `403` HTML page for authorized-but-forbidden page requests, and safe site-local `next` redirects for unauthenticated HTML requests.
