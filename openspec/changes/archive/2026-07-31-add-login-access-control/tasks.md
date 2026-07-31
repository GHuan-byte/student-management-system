## 1. Data Model and Configuration

- [x] 1.1 Add `users` table schema initialization with required fields, role constraints, unique normalized username, `is_active`, `auth_version`, timestamps, and `last_login_at`
- [x] 1.2 Add session and cookie configuration values including explicit cookie name, HttpOnly, SameSite=Lax, bounded lifetime, production secure-cookie behavior, and production `SECRET_KEY` validation
- [x] 1.3 Add bootstrap configuration parsing for `BOOTSTRAP_DEFAULT_USERS_ENABLED`, per-role usernames, and per-role passwords without hardcoded password defaults
- [x] 1.4 Update `.env.example` with bootstrap usernames and empty password placeholders only
- [x] 1.5 Add tests proving startup database initialization creates `users` without deleting existing `students` data
- [x] 1.6 Add tests proving production rejects missing, development-default, or placeholder `SECRET_KEY` values
- [x] 1.7 Add tests proving production defaults `BOOTSTRAP_DEFAULT_USERS_ENABLED=false`

## 2. User Repository, Service, and Bootstrap Accounts

- [x] 2.1 Add a `UserRepository` that keeps all user SQL inside repository/database modules
- [x] 2.2 Add a `UserService` for username normalization, role validation, password minimum-length validation, password hashing, password verification, active-account checks, `auth_version`, and `last_login_at`
- [x] 2.3 Add `ensure_bootstrap_users()` through Application Factory 鈫?UserService 鈫?UserRepository 鈫?SQLite
- [x] 2.4 Ensure startup order is app creation, config load/override/normalize/validate, logging setup, database/users initialization, bootstrap users, then dependent service and entrypoint registration
- [x] 2.5 Add tests for username uniqueness/normalization, role constraints, password hashing, generic login failure, inactive-account rejection, and `auth_version` session invalidation data
- [x] 2.6 Add tests proving bootstrap disabled creates no account and does not create weak implicit defaults
- [x] 2.7 Add tests proving bootstrap enabled creates Viewer, Staff, and Admin accounts with correct roles
- [x] 2.8 Add tests proving bootstrap passwords are saved as hashes, not plaintext, and all three configured passwords can authenticate
- [x] 2.9 Add tests proving repeated startup creates no duplicate users and does not overwrite existing passwords, roles, disabled state, or caller-owned config data
- [x] 2.10 Add tests proving missing bootstrap passwords, duplicate normalized usernames, invalid usernames, and weak passwords fail safely without leaking passwords
- [x] 2.11 Add tests proving testing uses isolated temporary databases and test-only bootstrap config
- [x] 2.12 Treat account-management CLI as optional; if implemented, add tests proving it is not required for initial roles and never accepts plaintext password arguments
- [x] 2.13 Add tests proving bootstrapped Viewer, Staff, and Admin accounts retain the approved role permission matrix

## 3. Authentication, Session, and CSRF Infrastructure

- [x] 3.1 Add current-user loading that clears stale sessions and reloads active user/role from SQLite for protected requests
- [x] 3.2 Add login-required and role-required guards for pages and APIs with HTML redirects for unauthenticated pages and unified JSON 401/403 for APIs
- [x] 3.3 Add native synchronizer-token CSRF generation and validation for `POST`, `PUT`, `PATCH`, and `DELETE`
- [x] 3.4 Add safe site-local `next` validation that rejects open redirects
- [x] 3.5 Add tests for minimal session contents, session fixation prevention, stale `auth_version`, inactive user handling, API/page auth responses, CSRF success/failure, and open redirect rejection

## 4. Login and Logout Pages

- [x] 4.1 Add `GET /login`, `POST /login`, and POST-only `/logout` routes
- [x] 4.2 Add the server-rendered login template with system name, username, password, submit button, generic error area, CSRF hidden field, and accessible labels
- [x] 4.3 Update the authenticated shared layout to show current username, role, CSRF token source, and POST logout control
- [x] 4.4 Add tests for login page rendering, authenticated `/login` redirect, successful login, failed login generic response, logout behavior, and `GET /logout` not logging out

## 5. Student Page and Student API Authorization

- [x] 5.1 Protect `/` and `/students` so unauthenticated users redirect to `/login` with a safe `next`
- [x] 5.2 Enforce Viewer/Staff/Admin authorization on `GET /api/students`, `GET /api/students/<id>`, `GET /api/students/stats`, `POST /api/students`, `PUT /api/students/<id>`, `DELETE /api/students/<id>`, and `POST /api/students/batch-delete`
- [x] 5.3 Update `students.js` unsafe student mutation requests to send `X-CSRF-Token`
- [x] 5.4 Update the student-management UI so Viewer hides create/edit/delete/batch-delete controls, Staff hides delete/batch-delete controls, and Admin sees all controls
- [x] 5.5 Add tests proving forbidden student API requests return 403 and do not call student service write/delete operations
- [x] 5.6 Add tests proving permitted roles preserve existing student API response contracts

## 6. AI Chat and Action Confirmation Authorization

- [x] 6.1 Require login and CSRF for `POST /api/chat` and `POST /api/chat/actions/confirm`
- [x] 6.2 Allow read-only AI Chat for Viewer, Staff, and Admin while preserving existing AI Chat validation and error contracts
- [x] 6.3 Classify AI pending and confirmed write actions by actual MCP tool/action type
- [x] 6.4 Enforce Viewer denial for all AI write execution, Staff allowance for add/edit/upsert only, Staff denial for delete/batch-delete, and Admin allowance for all AI write confirmations
- [x] 6.5 Ensure confirmation reloads current user, active state, `auth_version`, and current role before verifying/executing the signed token
- [x] 6.6 Update `ai_chat.js` unsafe requests to send `X-CSRF-Token`
- [x] 6.7 Add tests proving AI writes are never executed before confirmation and role checks cannot be bypassed through forged frontend requests or stale pending-action role data

## 7. Security Event Logging

- [x] 7.1 Emit `log_security_event()` records for successful login, failed login, logout, inactive-account login attempt, CSRF failure, forbidden access, stale session invalidation, bootstrap user creation, and safe bootstrap skip summaries
- [x] 7.2 Add tests proving bootstrap creation uses `event=bootstrap_user_created` with username, role, and outcome
- [x] 7.3 Add tests proving security events use shared logging fields and do not leak passwords, password hashes, CSRF tokens, session IDs, cookie values, AI confirmation tokens, API keys, raw request bodies, full environment configuration, or complete student records
- [x] 7.4 Confirm authentication logging does not alter existing application logging, MCP stdout/stderr behavior, or student/AI response contracts

## 8. End-to-End Verification

- [x] 8.1 Run focused tests for user repository/service, bootstrap accounts, auth guards, CSRF, login/logout, role authorization, AI authorization, optional CLI behavior, and security logging
- [x] 8.2 Run the full pytest suite with isolated temporary paths
- [x] 8.3 Run OpenSpec strict validation for `add-login-access-control`
- [x] 8.4 Run `git diff --check`
- [x] 8.5 Review git diff and confirm only approved implementation, tests, and planning artifacts changed

## 9. Manual Acceptance

- [x] 9.1 [USER] Configure local `.env` with bootstrap enabled and explicit Viewer, Staff, and Admin usernames/passwords, then start the application
- [x] 9.2 [USER] Manually verify the `users` table contains automatically created Viewer, Staff, and Admin accounts with correct roles and only password hashes
- [x] 9.3 [USER] Restart the application and verify bootstrap is idempotent: no duplicate users, no password overwrite, no role overwrite, and no disabled account re-enable
- [x] 9.4 [USER] Manually verify unauthenticated `/` and `/students` redirect to `/login`, each bootstrapped role account can log in, and logout clears access
- [x] 9.5 [USER] Manually verify Viewer can read pages/data but cannot create, edit, delete, batch-delete, or execute AI write actions
- [x] 9.6 [USER] Manually verify Staff can create/edit/upsert but cannot delete, batch-delete, or execute AI delete confirmations
- [x] 9.7 [USER] Manually verify Admin can perform approved student management actions including delete and batch delete
- [x] 9.8 [USER] Manually verify CSRF failures return safe 403 responses and do not leak CSRF/session/cookie data to logs
- [x] 9.9 [USER] Manually verify representative bootstrap, login, logout, forbidden, and CSRF security logs are readable, shared-format, and free of passwords, hashes, tokens, cookies, full environment configuration, and complete student records
