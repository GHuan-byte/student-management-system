## Why

The V2 student management system currently exposes its Dashboard, student pages, student APIs, and AI Chat HTTP entrypoints without application-level login or role checks. This change adds a small, dependency-free Flask authentication and access-control layer so the existing student workflows can be protected before broader operational use.

## What Changes

- Add a server-rendered login page plus POST-only login/logout behavior.
- Add a SQLite `users` table, password hashing with Werkzeug, active-account checks, and `auth_version`-based session invalidation.
- Add Flask Session configuration, safe session contents, secure cookie policy, and a native synchronizer-token CSRF mechanism for unsafe HTTP requests.
- Add Viewer, Staff, and Admin roles with server-side authorization for pages, student APIs, AI Chat, and AI Action Confirmation execution.
- Add a configurable startup bootstrap path that can create default Viewer, Staff, and Admin accounts from environment-provided usernames and passwords.
- Keep an interactive account-management CLI as optional or future-supporting tooling only; it is not required as the initial account creation path for this change.
- Use the existing application logging security-event interface for login, logout, authentication failure, and forbidden-access events without logging passwords, hashes, CSRF tokens, session IDs, cookies, or complete student records.
- Keep direct stdio MCP Server identity/authentication out of scope; it remains a separate trust boundary and its protocol behavior is not changed.
- No new third-party authentication, CSRF, token, session, or role-management dependencies are introduced.

## Out of Scope

- User registration, password reset, password recovery, online password change, email or phone verification, OAuth, LDAP, SSO, MFA, JWT, API tokens, login rate-limit platform, user-management frontend, and external session storage.
- Flask-Login, Flask-WTF, Redis, or any new third-party authentication/session/CSRF dependency.
- Direct stdio MCP Server authentication or any MCP stdio protocol change.
- Changes to student business rules, MCP tool semantics, AI Action Confirmation token semantics, or application logging behavior beyond the explicit HTTP access-control and security-event logging requirements.
- Any usable default password in Python source, committed config, `.env.example`, JavaScript, HTML, tests, or planning artifacts.

## Capabilities

### New Capabilities
- `login-access-control`: Defines local user accounts, password hashing, configurable default role-account bootstrap, Flask Session authentication, CSRF protection, role-based authorization, and security-event logging for login/access-control behavior.

### Modified Capabilities
- `student-data-management`: Student REST API endpoints become login-protected and role-authorized while preserving existing CRUD contracts for permitted users.
- `student-management-ui`: Dashboard and student-management pages become login-protected and display role-aware navigation/actions while preserving the existing server-rendered UI model.
- `ai-chat`: AI Chat HTTP routes become login-protected, CSRF-protected where unsafe, and role-authorized for read-only versus write-confirmation execution.
- `application-logging`: Authentication and authorization flows now emit security events through the existing shared logging interface and redaction policy.

## Impact

- Affected areas include Flask app setup, config, `.env.example`, database schema initialization, user repository/service/auth helpers, bootstrap-user startup flow, page and API route decorators or guards, templates, vanilla JavaScript request headers, AI Chat confirmation flow, optional CLI commands, and tests.
- Existing public endpoints remain limited to `/login`, `/api/health`, and static files.
- Existing student CRUD, AI Action Confirmation, MCP stdio protocol, and logging behavior must be preserved except where explicitly protected by HTTP authentication, authorization, and CSRF rules.
- Runtime database files, secrets, passwords, session cookies, CSRF tokens, API keys, and local evidence files remain excluded from Git and logs.
- `.env.example` may document bootstrap usernames and empty password placeholders, but it must not contain usable default passwords.
