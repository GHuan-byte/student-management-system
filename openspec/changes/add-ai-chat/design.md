## Context

The current V2 codebase provides the approved student-management stack: Flask routes, REST API, service layer, repository, SQLite, and a stdio MCP server with 10 student tools. The existing `mcp_client` module already supports async tool discovery and invocation. No AI Chat capability exists yet.

This change adds an AI Chat assistant that connects DeepSeek (via OpenAI-compatible Chat Completions API) with the existing MCP student tools. All AI configuration comes from environment variables; no API keys, model names, or API bases are hardcoded. Write operations require server-side signed confirmation tokens before execution.

## Goals / Non-Goals

**Goals:**

- Provide a floating AI Chat icon and panel on the shared `base.html` layout, visible on both Dashboard and student management pages.
- Connect DeepSeek via OpenAI-compatible Chat Completions protocol using environment-variable configuration only.
- Discover and call the existing 10 MCP student tools through `mcp_client` with session reuse.
- Support natural-language query (read) and write operations (create, update, upsert, delete, batch-delete).
- Gate all write operations behind a server-side signed confirmation token (short TTL, single-use, anti-tamper).
- Provide a clean architectural separation: `DeepSeekClient` (HTTP/API), `MCPToolAdapter` (MCP discovery/invocation), `AIActionConfirmation` (token signing/verification), `AIChatService` (orchestration).
- Keep API contract clean: `POST /api/chat` and `POST /api/chat/actions/confirm` — no model names in URLs.
- Use `sessionStorage` for chat history (user/assistant messages only), recoverable across page navigations within the same tab.
- Add tests for all modules with fake transports (no real DeepSeek calls in default tests).
- Add a live smoke script for optional real-API verification.
- Protect all secrets: API keys never appear in templates, JS, HTML source, Flask responses, MCP arguments, logs, or test snapshots.

**Non-Goals:**

- SSE streaming, WebSocket, or real-time communication — all responses are synchronous HTTP.
- Chat database persistence — sessionStorage only in this phase.
- User authentication, multi-user sessions, or per-user history.
- File upload, image input, voice input, web search, or RAG.
- Excel/CSV import or export within the chat interface.
- HTTP MCP transport — the adapter reuses the existing stdio MCP client.
- New frontend frameworks (React, Vue, etc.) — all JS is vanilla.
- Model fine-tuning, deployment, Docker, or CI/CD changes.
- Altering existing student-management page behavior, REST API contracts, MCP tool schemas, or database schema.

## Decisions

### D1. Use a separate `ai_chat.css` file for AI Chat styling

The AI Chat panel will have its own CSS file at `app/static/css/ai_chat.css` with a dedicated `ai-chat-` class prefix. It will be loaded via `<link>` in `base.html` alongside `style.css`.

Rationale:
- The AI Chat panel is structurally different from existing page layouts (floating icon, overlay panel, message bubbles, confirmation cards).
- A separate file prevents accidental style conflicts with existing `.modal`, `.sidebar`, `.panel`, `.card`, and `.button` classes.
- The `ai-chat-` prefix provides a clear namespace.

Alternative considered: Adding AI Chat styles to the existing `style.css` in a dedicated section. Rejected because the panel has ~200+ lines of unique CSS that would clutter the main stylesheet and risk selector specificity conflicts.

### D2. Use `itsdangerous` (Flask's built-in dependency) for confirmation token signing

The `AIActionConfirmation` module will use `itsdangerous.URLSafeTimedSerializer` to create and verify signed tokens. The signing key will be the Flask app's `SECRET_KEY`.

Rationale:
- `itsdangerous` is already a Flask dependency — no new package needed.
- `URLSafeTimedSerializer` provides built-in expiration, tamper detection, and payload serialization.
- The token will embed the tool name, JSON-serialized arguments, a unique action ID, and a creation timestamp.

Alternative considered: Implementing HMAC-SHA256 manually. Rejected because `itsdangerous` is already available, well-tested, and handles serialization/deserialization consistently.

### D3. Request-level MCP Session lifecycle (fixed)

Each `POST /api/chat` request creates exactly one stdio MCP Session. The following operations share that single Session:
- MCP Tool discovery (`list_tools`)
- All read-only Tool Calls within the DeepSeek Tool Loop
- Any write Tool Calls that result from confirmed actions

The Session is closed when the HTTP request ends. No long-lived or cross-request MCP Session exists.

The `mcp_client` package will receive minimal extensions to support session-level operations:
- `open_mcp_session(...)` — opens and initializes a stdio MCP session, returns the session object
- `list_tools_in_session(session, ...)` — lists tools using an open session
- `call_tool_in_session(session, tool_name, arguments, ...)` — calls a tool using an open session

Existing public methods (`list_mcp_tools_async`, `call_mcp_tool_async`, sync wrappers) remain unchanged and compatible.

Rationale:
- Starting a new MCP server subprocess for each tool call adds ~1-2s latency. Session reuse within a request eliminates this.
- The existing `mcp_session` async context manager already handles correct session lifecycle.
- Request-level sessions are simple to reason about: no shared state, no stale tools, no cleanup across requests.

Alternative considered: Long-lived persistent MCP Session shared across HTTP requests. Rejected because it adds lifecycle complexity, stale-tool risks, and process management overhead that this phase does not need.

### D4. Use `httpx` as the only DeepSeek HTTP client implementation

The `DeepSeekClient` SHALL use `httpx` as its only HTTP library. No fallback to `openai` SDK, `requests`, or any other HTTP library exists.

Rationale:
1. This project only needs the OpenAI-compatible Chat Completions protocol. The full OpenAI Python SDK is unnecessary overhead.
2. Tool calls, thinking, `reasoning_content`, and custom error mapping require precise control over the raw request and response JSON — wrapping through an SDK adds indirection.
3. `httpx.MockTransport` (or injectable `Transport`) provides clean fake-transport support for Superpowers TDD, enabling test isolation without real network access.
4. A single implementation path ensures development, test, and Evidence Gate environments all verify the same production code.
5. If `httpx` is missing, the system must stop and report — no silent fallback masks environment issues.

Alternative considered: OpenAI Python SDK. Rejected because it adds unnecessary coupling, makes thinking/reasoning_content handling opaque, and creates a maintenance burden for a protocol that is fully documented and straightforward to call with `httpx`.

### D5. Thread-safe confirmation token with concurrent replay protection

Each pending write action gets a signed token via `itsdangerous.URLSafeTimedSerializer`:
```json
{
  "action_id": "uuid-string",
  "tool_name": "add_student",
  "arguments": {"student_number": "00001", ...},
  "created_at": 1234567890.0
}
```

Token rules:
- TTL: `AI_CONFIRMATION_TOKEN_TTL_SECONDS` (default 120 seconds)
- Single-use: consumed token is removed from the in-memory store
- Anti-tamper: verified via `itsdangerous` signature and payload serialization
- Anti-replay: `action_id` tracked in an in-memory `set[action_id]` protected by a `threading.Lock`

Concurrent safety:
1. Both pending action creation and consumed-action tracking are protected by a single `threading.Lock`.
2. Confirmation flow inside the lock: verify `action_id` not consumed → check expiration (via `URLSafeTimedSerializer`) → verify signature → mark consumed → execute MCP write tool.
3. Token is marked consumed **before** the MCP tool executes. If the MCP tool fails, the token remains consumed — the user must re-request the operation.
4. Two concurrent confirmation requests for the same token: at most one proceeds to MCP execution; the other gets `token_already_used`.
5. `SECRET_KEY` validation: when `SECRET_KEY` is missing, empty, or still at the development default (`"dev-secret-change-in-production"`), write confirmation raises `ai_confirmation_not_configured`. The app starts, read-only chat works, but writes are `fail-closed`.

**Memory boundary** — The consumed-action-id set is:

- Per-instance (not shared across instances)
- In-memory only (lost on application restart)
- Not synchronized across multiple worker processes
- Suitable for single-process development; production multi-worker deployments require Redis or a database unique constraint

Rationale:
- In-memory is sufficient for single-process development.
- The set is small (only pending action IDs within their TTL window).
- No automatic cleanup thread — entries persist until restart, which is safe because TTL-based expiration is already enforced by `URLSafeTimedSerializer`.
- Multi-worker and distributed replay protection is out of scope for this phase.

Rationale:
- Thread lock prevents race conditions in Flask's default threaded mode.
- Marking consumed before execution prevents the race where two confirmations both validate but then both execute.
- Even MCP failure does not unmark consumed — the user re-requests, getting a fresh token.

Alternative considered: Using a database for consumed-token tracking. Rejected because in-memory is sufficient for this phase; the store is ephemeral and lost on restart, which is acceptable.

### D6. MCP Tool Adapter discovers tools once per chat request

At the start of each `POST /api/chat` request, the adapter opens one stdio MCP Session, discovers tools once via `list_tools_in_session`, and saves the discovered tool name set. The same session is used for all subsequent tool calls within that request.

Tool call rules:
1. **Multiple read-only tools**: Execute in response order, each with its `tool_call_id`, continue Tool Loop.
2. **Mixed read+write tools**: Execute read-only tools that appear **before** the first write tool. Stop at the first write tool. Generate one Pending Action. Return at most one Pending Action per response.
3. **Multiple write tools**: Do not execute any. Return `ai_multiple_write_actions` error. The model must request one write at a time.
4. **Unknown tools**: Do not execute. Return structured tool result.

Rationale:
- Tool schemas are stable for the lifetime of the MCP server process.
- Discovery-once per request is simple and avoids stale schema concerns.
- If a tool schema changes between requests, the next request picks it up.

### D7. Chat history stored in `sessionStorage` only

The browser stores an array of `{role, content}` objects under a single `sessionStorage` key. Only `user` and `assistant` roles are saved. No `system`, `developer`, `tool`, `reasoning_content`, confirmation tokens, tool arguments, MCP raw results, API keys, API bases, or model names are stored.

History is truncated to `AI_MAX_HISTORY_MESSAGES` entries on save and on restore. Pending confirmation states do not enter history. Closing the panel does not clear history; only the clear-session button removes the `sessionStorage` key.

Server-side message validation order:
1. Verify body is a JSON object.
2. Verify `messages` is a non-empty array.
3. Verify each message has `role` and `content`.
4. Validate all roles — reject `system`, `developer`, `tool`, and unknown roles.
5. Validate all content (non-blank for `user` role).
6. Validate single message length against `AI_MAX_MESSAGE_LENGTH`.
7. Confirm the last message role is `user`.
8. Only after full validation, truncate to the most recent `AI_MAX_HISTORY_MESSAGES` entries, ensuring the last `user` message is always retained.

Rationale:
- `sessionStorage` is cleared when the tab closes — no long-term persistence needed.
- Full validation before truncation prevents illegal messages from escaping detection by being in the "tail" that gets dropped.

### D8. Flask app continues to work without AI configuration

All AI env vars are optional for app startup. When `DEEPSEEK_API_KEY`, `DEEPSEEK_API_BASE`, or `DEEPSEEK_MODEL` are missing, the Flask app starts normally. The AI Chat icon is still visible, but sending a message returns a structured `ai_not_configured` error.

Similarly, when `SECRET_KEY` is missing, empty, or still at the development default, write confirmation fails with `ai_confirmation_not_configured`, but read-only chat and the rest of the app continue to work.

Rationale:
- Operators should be able to use the student management UI even if AI is not configured.
- The error is user-friendly and does not leak which specific variable is missing.

### D9. Student modal opens → AI Chat Panel auto-closes (fixed)

When the student create/edit modal opens, the AI Chat Panel automatically closes. Chat history is preserved in `sessionStorage`. The Chat Panel does not re-open when the modal closes. The floating icon remains visible but has a lower `z-index` than the student modal backdrop (`z-index: 80`).

Rationale:
- A single fixed behavior eliminates ambiguity between the two previously proposed options.
- Auto-closing prevents the Chat Panel from covering or competing with the essential create/edit workflow.
- Not re-opening on modal close respects the user's choice to have closed the panel.

Alternative considered: Keeping the Chat Panel open but at a lower z-index. Rejected because the panel content could still visually distract from the modal workflow.

### D10. reasoning_content passes through internally during Tool Loop

When `DEEPSEEK_THINKING` is enabled and the upstream assistant response contains both `tool_calls` and `reasoning_content`:

1. The `DeepSeekClient` extracts `reasoning_content` from the upstream response.
2. `AIChatService` preserves the full assistant message (with `reasoning_content`) for the next DeepSeek request in the same Tool Loop, following the upstream-compatible protocol for returning assistant context.
3. `reasoning_content` is included in the internal assistant message sent back to DeepSeek on the next round.
4. `reasoning_content` is NOT included in the final user-facing reply.
5. `reasoning_content` is NOT saved to `sessionStorage`, browser history, or logs.
6. Once the Tool Loop ends, `reasoning_content` is discarded.

Rationale:
- Some upstream models require `reasoning_content` to be echoed in subsequent requests for correct multi-turn behavior.
- The `reasoning_content` is an internal protocol detail, not user-facing content.

### D11. Thinking request uses object contract (not boolean)

The `thinking` field in the Chat Completions request MUST be an object, not a boolean.

- **Enabled**: `{"thinking": {"type": "enabled"}, "reasoning_effort": "high"}`
- **Disabled**: `{"thinking": {"type": "disabled"}}`

`reasoning_effort` is only sent when thinking is enabled. Allowed values are `high` and `max`. Disabled state explicitly sends `thinking.type=disabled` — the field is never omitted.

Rationale:
- The upstream API requires `thinking` as an object to distinguish between disabled thinking and the absence of thinking configuration.
- A boolean `thinking: true/false` is not supported by the upstream contract.

### D12. Confirmation token payload validation — no secrets in signed data

`URLSafeTimedSerializer` provides integrity and signature verification but does **not** provide confidentiality. The token payload is Base64-encoded and signed — anyone who sees the token can decode it.

Therefore the `AIActionConfirmation.create_token()` method enforces:

1. Payload must be a `dict` — lists, strings, `None`, and numbers are rejected.
2. Payload must not contain any of the following fields at any nesting depth (case-insensitive key matching):
   - `api_key`
   - `authorization`
   - `authorization_header`
   - `database_path`
   - `mcp_session`
   - `reasoning_content`
3. Validation recurses into nested `dict` values and `list`/`tuple` elements.
4. Non-dict payloads raise `AIConfirmationInvalidPayloadError` (`ai_confirmation_invalid_payload`).
5. Forbidden-field payloads raise the same error.
6. Error messages never contain the forbidden field names, their values, the `SECRET_KEY`, the token string, or any student data.

**Rationale:**
- The token is signed, not encrypted. Anyone with access to the token (network trace, browser dev tools, logs) can decode the Base64 payload.
- Even though the browser is the only consumer in normal flow, the content is visible — secrets must never enter the payload.
- Recursive case-insensitive checking ensures no secret field can slip through via nesting or casing variations.

**Not in scope for this decision:**
- Token consumption, replay protection, or `threading.Lock` — covered by D5.
- The consumer of `verify_token()` (the confirm route) is responsible for extracting only the intended `tool_name` and `arguments` for execution — payload validation does not replace that check.

Alternative considered: Omitting `thinking` entirely when disabled. Rejected because the upstream API requires explicit opt-out via `thinking.type=disabled`. Omitting the field leaves the behavior undefined.

### D12. reasoning_effort validation at config and client layers

The allowed `reasoning_effort` values are `high` and `max` only. Validation occurs at two levels:

**Config layer** (`app/config.py`):
- When `DEEPSEEK_THINKING` is true, `AI_CONFIGURED` also requires `DEEPSEEK_REASONING_EFFORT` to be one of `{"high", "max"}`.
- When `DEEPSEEK_REASONING_EFFORT` is missing, empty, or any value other than `high`/`max`, `AI_CONFIGURED` is `False`.
- The allowed set is defined as a module-level constant (`ALLOWED_REASONING_EFFORTS`) importable by other modules.

**Client layer** (`app/services/deepseek_client.py`):
- `DeepSeekClient._build_payload` checks `_reasoning_effort` against the allowed set when `_thinking_enabled`.
- If `_reasoning_effort` is not in `{"high", "max"}`, the client raises a configuration error and does NOT send an HTTP request.
- When `_thinking_enabled` is `False`, `_reasoning_effort` is ignored entirely — any value is accepted but never sent upstream.

Rationale:
- Dual-layer validation ensures that even if the config layer is bypassed (e.g., direct client construction with raw config), invalid effort values never reach the upstream API.
- The config layer presents a unified `AI_CONFIGURED` state to the application, so routes can make a single check.

## Risks / Trade-offs

- [MCP session lifecycle in Flask sync handlers] → The `MCPToolAdapter` must manage async MCP sessions inside Flask's sync request handlers. Mitigation: use `asyncio.run()` to drive the async MCP session for the duration of the request, terminating cleanly before the response.
- [`asyncio.run()` within gunicorn/eventlet] → If the Flask app runs under an async server, nested event loops can fail. Mitigation: detect existing event loops and raise a clear error; document that the default `python run.py` (Werkzeug dev server) is the supported startup mode.
- [Long tool loops exceed HTTP timeout] → A chat request with multiple tool rounds could take tens of seconds. Mitigation: set `AI_MAX_TOOL_ROUNDS` (default 5–10) and a per-call timeout on the DeepSeek client via `DEEPSEEK_TIMEOUT_SECONDS`.
- [Concurrent confirmation race] → Mitigation: thread lock with mark-consumed-before-execute pattern. At most one confirmation succeeds per token.
- [In-memory confirmation token store lost on restart] → Pending confirmations are lost if the process restarts. Mitigation: acceptable for this phase; the user simply re-requests the operation.
- [DeepSeek API rate limits or downtime] → The AI Chat will return structured errors (`ai_rate_limited`, `ai_upstream_error`) rather than crashing. The chat panel remains open.
- [Sensitive data in logs] → The `DeepSeekClient` and `AIChatService` must never log the full request/response payload, API key, or student record contents. Mitigation: log only message length, tool name, and error codes.
- [Chat Panel interferes with student modal] → Fixed: when the student modal opens, the Chat Panel auto-closes. The icon remains visible but with lower z-index than the modal backdrop.

## Migration Plan

1. Add environment variables to `.env.example` and `app/config.py`.
2. Implement `DeepSeekClient` with fake transport support.
3. Implement `MCPToolAdapter` with MCP session reuse.
4. Implement `AIActionConfirmation` with token signing.
5. Implement `AIChatService` orchestrating the tool loop.
6. Add `app/routes/chat.py` with `POST /api/chat` and `POST /api/chat/actions/confirm`.
7. Add `app/templates/_ai_chat.html` with floating icon and panel.
8. Add `app/static/css/ai_chat.css` with `ai-chat-` prefixed styles.
9. Add `app/static/js/ai_chat.js` with full chat behavior.
10. Wire everything into `base.html` only — AI Chat CSS, JS, and template fragment are included via the shared layout. Dashboard and students pages automatically inherit the AI Chat through template inheritance, without per-page resource loading.
11. Register the chat blueprint in `app/__init__.py`.
12. Add tests for each module.
13. Add live smoke script.
14. Rollback: remove the new files and revert changes to existing files; no schema migration needed.

## Open Questions

None. All decisions from the first planning revision have been resolved:
- HTTP library: **httpx** (fixed, no fallback)
- MCP Session lifecycle: **request-level session** (fixed, no long-lived option)
- Chat/Modal z-index: **Modal opens → Chat Panel auto-closes** (fixed, no dual-option)
- Confirmation token: **thread-safe, fail-closed on weak SECRET_KEY** (fixed)
- Tool call rules: **read-only batch, mixed stops at first write, multiple writes rejected** (fixed)
- Frontend loading: **base.html shared only** (fixed)
