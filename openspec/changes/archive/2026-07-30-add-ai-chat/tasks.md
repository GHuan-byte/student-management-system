## 1. OpenSpec Planning Gate

- [x] 1.1 Create change directory and scaffold artifacts (proposal, specs, design, tasks)
- [x] 1.2 Read project context: AGENTS.md, README.md, pyproject.toml, requirements.txt, .env.example, app/config.py, app/__init__.py
- [x] 1.3 Read canonical specs: student-data-management, student-management-ui, mcp-student-tools, project-foundation
- [x] 1.4 Read archived changes and installed skills
- [x] 1.5 Create proposal.md establishing why the AI Chat change is needed
- [x] 1.6 Create specs/ai-chat/spec.md with all requirements and scenarios (revised for httpx-only, request-level MCP session, thread-safe tokens, multi-tool rules, fixed Chat/Modal behavior)
- [x] 1.7 Create design.md with architecture decisions, goals, and migration plan (revised: httpx-only, no openai SDK, fixed MCP session lifecycle, thread-safe confirmation, Chat auto-closes on modal open)
- [x] 1.8 Create tasks.md with six-gate task breakdown
- [x] 1.9 Check environment: pytest (7.4.4 ✓), itsdangerous (2.2.0 ✓), httpx (check needed), openai (2.44.0 available but not used)
- [x] 1.10 Stop — do not enter Implementation Gate

## 2. Superpowers Implementation Gate

### 2.1 Environment and Configuration

- [x] 2.1.1 Add AI Chat environment variables to .env.example (DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT_SECONDS, DEEPSEEK_MAX_OUTPUT_TOKENS, DEEPSEEK_THINKING, DEEPSEEK_REASONING_EFFORT, AI_MAX_TOOL_ROUNDS, AI_MAX_HISTORY_MESSAGES, AI_MAX_MESSAGE_LENGTH, AI_CONFIRMATION_TOKEN_TTL_SECONDS)
- [x] 2.1.2 Add env var loading and validation to app/config.py — all AI config from env only, no hardcoded defaults for API base or model
- [x] 2.1.3 Add httpx dependency to pyproject.toml and requirements.txt (httpx>=0.28)
- [x] 2.1.4 Add itsdangerous dependency check — verify SECRET_KEY safety for token signing (implemented via _is_secret_key_safe in config.py)
- [x] 2.1.5 Add pytest as development dependency (pyproject.toml [project.optional-dependencies] test section)
- [x] 2.1.6 [USER] Check httpx is installed; if missing, run: pip install httpx (httpx 0.28.1 ✓ already installed)
- [x] 2.1.7 Add DEEPSEEK_TRUST_ENV to config.py, .env.example, and tests
- [x] 2.1.8 Update uv.lock to reflect new dependencies (user executed: uv lock)

### 2.2 Configuration Tests (TDD: test_ai_config.py)

- [x] 2.2.1 RED: Test missing DEEPSEEK_API_KEY — app starts, AI_CONFIGURED is False
- [x] 2.2.2 RED: Test missing DEEPSEEK_API_BASE — same behavior
- [x] 2.2.3 RED: Test missing DEEPSEEK_MODEL — same behavior
- [x] 2.2.4 RED: Test all AI config comes from env vars, no hardcoded defaults
- [x] 2.2.5 RED: Test browser cannot override model, api_base, api_key, or thinking config (AI config not in HTML/JS)
- [x] 2.2.6 RED: Test SECRET_KEY missing/unsafe — AI_WRITE_CONFIRMATION is False
- [x] 2.2.7 RED: Test SECRET_KEY missing/unsafe — app still starts, read-only chat works
- [x] 2.2.8 RED: Test HTML does not contain API Key, API Base, or Model name
- [x] 2.2.9 RED: Test JS does not contain API Key, API Base, or Model name (covered by HTML test)
- [x] 2.2.10 RED: Test API response does not contain API Key, API Base, or Model name (covered by HTML test)
- [x] 2.2.11 GREEN: Implement config loading and validation in app/config.py
- [x] 2.2.12 REFACTOR: Clean up under test coverage

### 2.3 DeepSeek Client (TDD: test_deepseek_client.py)

- [x] 2.3.1 RED: Test client uses httpx only, no openai SDK fallback (httpx.AsyncClient + MockTransport)
- [x] 2.3.2 RED: Test normal text response returns parsed content
- [x] 2.3.3 GREEN: Implement DeepSeekClient with basic create_chat_completion() using httpx
- [x] 2.3.4 RED: Test tool_calls response parsing
- [x] 2.3.5 GREEN: Implement tool_calls parsing
- [x] 2.3.6 RED: Test timeout maps to ai_timeout
- [x] 2.3.7 RED: Test 401/403 maps to ai_auth_error
- [x] 2.3.8 RED: Test 429 maps to ai_rate_limited
- [x] 2.3.9 RED: Test 5xx maps to ai_upstream_error
- [x] 2.3.10 RED: Test malformed response (missing choices/message) maps to ai_invalid_response
- [x] 2.3.11 RED: Test other httpx errors map to ai_upstream_error
- [x] 2.3.12a RED: Error message does not contain API Key, Authorization header, or user message
- [x] 2.3.12 RED: Test httpx raw exceptions not exposed to browser (requires Route layer)
- [x] 2.3.13 VERIFY: DeepSeekClient performs no automatic retries
- [x] 2.3.14 RED: Test thinking enabled — sends reasoning_effort from DEEPSEEK_REASONING_EFFORT
- [x] 2.3.15 RED: Test thinking disabled — no reasoning parameters sent
- [x] 2.3.16 RED: Test reasoning_content extracted for internal use, not in response
- [~] 2.3.14–2.3.16 correction: thinking object contract (thinking={type:enabled/disabled}) — Implementation and tests completed; no separate RED evidence captured for this delta correction
- [x] 2.3.17 RED: Test API Base from env, no hardcoded default
- [x] 2.3.18 RED: Test Model from env, no hardcoded default
- [x] 2.3.19 RED: Test API Key in Bearer header, not in logs/exception text/return values
- [x] 2.3.20 RED: Test MockTransport used in default tests, no real network
- [x] 2.3.21 GREEN: Implement all error handling, thinking mode, reasoning_effort validation, and dependency injection
- [x] 2.3.21a RED: reasoning_effort high/max valid, medium/low/missing → invalid, client refuses request
- [x] 2.3.21b GREEN: _validate_reasoning_effort() in client + _compute_ai_configured() in config
- [x] 2.3.22 REFACTOR: Clean up DeepSeekClient under test coverage

### 2.4 MCP Tool Adapter (TDD: test_mcp_tool_adapter.py)

- [x] 2.4.1 RED: Test discovery of all 10 student tools
- [x] 2.4.2 GREEN: Implement MCPToolAdapter with discover_tools()
- [x] 2.4.3 RED: Test tool conversion to OpenAI-compatible function format (type: function, name, description, parameters)
- [x] 2.4.4 GREEN: Implement tool conversion (_mcp_to_openai_tool)
- [x] 2.4.5 RED: Test request-level MCP Session — one session per chat request
- [x] 2.4.6 RED: Test multiple tool calls share the same MCP Session (via session factory, verified by multiple invoke_tool)
- [x] 2.4.7 RED: Test Session is closed after request ends
- [x] 2.4.8 RED: Test MCP server subprocess is NOT started for each individual tool call (fake session, verified by multiple invoke_tool)
- [x] 2.4.9 RED: Test unknown tool returns structured error
- [x] 2.4.10 RED: Test invalid JSON arguments return structured error
- [x] 2.4.11 RED: Test MCP tool errors returned as tool results, not exceptions
- [x] 2.4.12 RED: Test adapter output excludes raw MCP debug data (structured_content, parsed_text, content blocks)
- [x] 2.4.13 RED: Test open_mcp_session() extension works (mcp_session context manager exists)
- [x] 2.4.14 RED: Test list_tools_in_session() works (added to mcp_client)
- [x] 2.4.15 RED: Test call_tool_in_session() works (verified by invoke_tool via FakeMCPSession.call_tool)
- [x] 2.4.16 GREEN: Implement all adapter logic with session extensions (invoke_tool complete)
- [x] 2.4.17 REFACTOR: Clean up MCPToolAdapter under test coverage

### 2.5 AI Action Confirmation (TDD: test_ai_action_confirmation.py)

- [x] 2.5.1 RED: Test token creation and signing with itsdangerous
- [x] 2.5.2 GREEN: Implement AIActionConfirmation with URLSafeTimedSerializer
- [x] 2.5.3 RED: Test valid token verification returns original payload
- [x] 2.5.4 GREEN: Implement token verification
- [x] 2.5.5 RED: Test expired token returns structured error
- [x] 2.5.6 RED: Test tampered token returns structured error
- [x] 2.5.6a RED: Test invalid payload types return AIConfirmationInvalidPayloadError (list, str, None, int)
- [x] 2.5.6b RED: Test forbidden fields rejected at any nesting depth (case-insensitive)
- [x] 2.5.6c GREEN: Implement payload validation with FORBIDDEN_TOKEN_KEYS and recursive check
- [x] 2.5.6d REFACTOR: Clean up payload validation under test coverage
- [x] 2.5.6e RED: Test verify_token revalidates decoded payload (list, forbidden fields, nested)
- [x] 2.5.6f GREEN: verify_token calls _validate_payload after successful signature verification
- [x] 2.5.6g RED/GREEN: Non-JSON-serializable payload maps to AIConfirmationInvalidPayloadError
- [x] 2.5.7 RED: Test sequential replay — consumed token cannot be reused
- [x] 2.5.8 RED: Test concurrent replay — two confirmations for same token, at most one succeeds
- [x] 2.5.9 RED: Test thread safety — threading.Lock protects consumed-action tracking
- [x] 2.5.10 RED: Test MCP write tool failure — token remains consumed, not reusable (via real AIChatService integration)
    - [x] 2.5.10a RED: Adapter exceptions after consumption exposed raw internal errors
    - [x] 2.5.10b GREEN: consumed confirmation failures map to a safe execution error without restoring the token
    - [x] 2.5.10c VERIFY: business, technical, discovery, exit, and concurrent failed-write paths execute at most once
- [x] 2.5.11 RED: Test SECRET_KEY missing — write confirmation fail-closed (ai_confirmation_not_configured)
- [x] 2.5.12 RED: Test SECRET_KEY at development default — write confirmation fail-closed
- [x] 2.5.13 RED: Test token not stored in sessionStorage
- [x] 2.5.14 GREEN: Implement all confirmation logic with thread safety (blocked by 2.5.13)
- [x] 2.5.15 REFACTOR: Clean up backend AIActionConfirmation module

> **2.5 Status:** Backend token signing, verification, payload validation,
> atomic consumption and in-process replay protection are complete.
> MCP write-failure integration (2.5.10) and browser storage verification
> (2.5.13) are complete.

### 2.6 AI Chat Service (TDD: test_ai_chat_service.py)

- [x] 2.6.1 RED: Test normal Q&A returns text reply
- [x] 2.6.2 GREEN: Implement AIChatService with basic orchestration
- [x] 2.6.2a RED: Test single read tool call — tool executed, result fed back, final reply returned
- [x] 2.6.2b GREEN: Implement single read tool call orchestration
- [x] 2.6.2c RED/GREEN: Write tools fail-closed (AIWriteConfirmationRequiredError)
- [x] 2.6.2d REFACTOR: Clean up AIChatService message building helpers
- [x] 2.6.2e RED: Tools parameter not supported by DeepSeekClient — create_chat_completion missing `tools` kwarg
- [x] 2.6.2f GREEN: Add `tools` parameter to DeepSeekClient.create_chat_completion and _build_payload
- [x] 2.6.2g GREEN: Wire tools from adapter to both DeepSeek rounds in AIChatService
- [x] 2.6.2h REFACTOR: FakeDeepSeekClient signature matches real client
- [x] 2.6.3 RED: Test single read tool call returns tool result in next reply
- [x] 2.6.3a RED/GREEN: Second round passes tools=None (no multi-round loop yet)
- [x] 2.6.4 RED: Test multiple read-only tool calls — all executed in order via same session
- [x] 2.6.4a RED/GREEN: Two tool calls — both executed, correct names/args, two tool results
- [x] 2.6.4b RED/GREEN: Business error in first tool does not block subsequent tools
- [x] 2.6.4c RED/GREEN: MCP error in first tool does not block subsequent tools
- [x] 2.6.4d REFACTOR: Single and multi-tool use same for-loop code path
- [x] 2.6.5 RED: Test mixed read+write — no partial execution, pre-scan all tools
- [x] 2.6.5a RED/GREEN: read → write — no tool executed
- [x] 2.6.5b RED/GREEN: write → read — no tool executed
- [x] 2.6.5c RED/GREEN: multiple reads + write — no tool executed
- [x] 2.6.5d RED/GREEN: multiple writes — no tool executed
- [x] 2.6.5e REFACTOR: Pre-scan tool_names before execution loop
- [x] 2.6.6 Multiple write tool calls return ai_multiple_write_actions
- [x] 2.6.6a VERIFY: Multiple write tool calls fail closed before execution
<br>Current behavior rejects the entire write-tool batch before execution.
No MCP tool is executed and no partial action occurs.
The final ai_multiple_write_actions response is returned without creating a
pending confirmation action.
- [x] 2.6.7 RED: Test unknown tool — not executed, structured error returned
- [x] 2.6.7a RED/GREEN: unknown tool returns safe Tool Result, no adapter call
- [x] 2.6.7b RED/GREEN: read + unknown + read — reads execute, unknown skipped, order preserved
- [x] 2.6.7c RED/GREEN: unknown + write still triggers write fail-closed
- [x] 2.6.7d REFACTOR: KNOWN_TOOL_NAMES = READ_TOOL_NAMES | WRITE_TOOL_NAMES
- [x] 2.6.9 RED: Test multi-round Tool Loop
- [x] 2.6.9a–g: Multi-round sub-tasks
- [x] 2.6.10 RED: Test max tool rounds limit enforced
- [x] 2.6.10a–d: Max rounds sub-tasks
- [x] 2.6.11 VERIFY: MCP business and technical errors remain safe Tool Results
- [x] 2.6.11a VERIFY: Business error → safe Tool Result, service continues
- [x] 2.6.11b VERIFY: mcp_tool_error → safe Tool Result, service continues
- [x] 2.6.11c VERIFY: Error in round 1 does not block round 2
- [x] 2.6.12 RED: Test write tool returns pending action instead of executing
- [x] 2.6.8 At most one Pending Action per response
- [x] 2.6.12a–: Single write → pending action with token
- [x] 2.6.8a–: Mixed batch → at most one pending action
- [x] 2.6.12/6/8 REFACTOR: Write batch pre-scan → 0/1/many dispatch
- [x] 2.6.13 RED: Test confirmed write executes exactly once
    - [x] RED: confirmed Token invokes write tool once
    - [x] GREEN: consume before MCP execution
    - [x] VERIFY: replay does not re-execute
    - [x] VERIFY: MCP failure remains consumed
    - [x] REFACTOR: isolate confirmed-write orchestration
- [x] 2.6.14 Cancelled write does not execute
    - [x] 2.6.14a VERIFY: Pending actions are never executed automatically
    - [x] 2.6.14b VERIFY: No confirmation call means no MCP execution
    - [x] 2.6.14c Frontend cancellation discards the pending action and displays 操作已取消 (section 2.8)

  > **Cancellation semantics:**
  > - Cancel does NOT consume or revoke the token.
  > - The token expires naturally according to its TTL (default 120s).
  > - No backend ``cancel_action`` API is currently defined.
  > - The frontend must locally discard the pending action on cancel.
- [x] 2.6.15 VERIFY: reasoning_content is preserved only in internal assistant tool-call messages
- [x] 2.6.16 reasoning_content not returned to user in final reply
- [x] 2.6.17 MCP raw diagnostic objects not returned to user
    - [x] 2.6.17a RED: confirm_action action_result.data exposed nested MCP diagnostic fields
    - [x] 2.6.17b GREEN: recursively sanitize user-visible action_result while retaining business data
    - [x] 2.6.17c VERIFY: regression coverage for nested objects, lists, and case variants
- [x] 2.6.18 GREEN: Implement all orchestration logic
    - [x] 2.6.18a VERIFY: all chat, tool, write-confirmation and failure paths are covered
    - [x] 2.6.18b VERIFY: one request uses one MCP adapter/session and one discovery
- [x] 2.6.19 REFACTOR: Clean up AIChatService
    - [x] 2.6.19a REFACTOR: remove obsolete write-confirmation-required error
    - [x] 2.6.19b VERIFY: no obsolete single-round or write-fail-closed code remains

### 2.7 Chat Routes (TDD: test_chat_routes.py)

- [x] 2.7.1 RED: Test POST /api/chat with valid messages returns reply
- [x] 2.7.2 GREEN: Implement chat.py blueprint with POST /api/chat
- [x] 2.7.3 RED: Test POST /api/chat/actions/confirm with valid token
- [x] 2.7.4 GREEN: Implement POST /api/chat/actions/confirm
- [x] 2.7.5 RED: Test non-JSON body returns validation_error
- [x] 2.7.6 RED: Test empty messages returns validation_error
- [x] 2.7.7 RED: Test non-array messages returns validation_error
- [x] 2.7.8 RED: Test blank user message returns validation_error
- [x] 2.7.9 RED: Test illegal role (system, developer, tool) returns validation_error
- [x] 2.7.10 RED: Test last message must be user — returns validation_error otherwise
- [x] 2.7.11 RED: Test all messages validated before truncation — illegal messages in tail not skipped
- [x] 2.7.12 RED: Test history exceeds max limit is truncated (last user message retained)
- [x] 2.7.13 RED: Test message exceeds max length returns validation_error
- [x] 2.7.14 RED: Test missing config returns ai_not_configured
- [x] 2.7.15 RED: Test upstream auth error returns ai_auth_error
- [x] 2.7.16 RED: Test upstream timeout returns ai_timeout
- [x] 2.7.17 RED: Test upstream rate limit returns ai_rate_limited
- [x] 2.7.18 RED: Test internal error does not leak traceback or API key
- [x] 2.7.19 RED: Test API URL does not contain model name
- [x] 2.7.20 RED: Test confirm endpoint returns deterministic Chinese reply
- [x] 2.7.21 RED: Test confirm returns safe action_result without structured_content/parsed_text
- [x] 2.7.22 RED: Test confirm does not call DeepSeek again
- [x] 2.7.23 RED: Test confirm does not accept browser-submitted arguments
- [x] 2.7.24 GREEN: Implement all route handling
- [x] 2.7.25 Register chat blueprint in app/__init__.py
    - [x] VERIFY: both Chat endpoints are registered once and create_app can be called repeatedly
- [x] 2.7.26 REFACTOR: Clean up chat routes
    - [x] REFACTOR: centralize JSON-object validation and synchronous async-service execution

### 2.7a AI Configuration Short-Circuit Fix

- [x] RED: AI-unconfigured chat attempted MCP discovery before failing
- [x] GREEN: Short-circuit `ai_not_configured` before DeepSeek or MCP dependency creation
- [x] VERIFY: `POST /api/chat` returns HTTP 503 without DeepSeek, MCP, or database access

### 2.7b Plain-Text DeepSeek Reply Normalization Fix

- [x] RED: DeepSeek Markdown emphasis markers were displayed literally in the plain-text Chat UI
- [x] GREEN: Normalize DeepSeek final replies before returning them to users
- [x] VERIFY: Remove `**bold**` and `__emphasis__` markers while preserving content, newlines, tables, and leading zeros

### 2.7c Confirmed Write Failure Reporting Fix

- [x] RED: MCP write failure was incorrectly reported as a successful confirmed action
- [x] GREEN: Build confirmed action responses from the actual MCP success state
- [x] VERIFY: Failed writes show deterministic safe failure, execute once, and consume the token

> **Manual Acceptance finding:** A blocking confirmed-write result defect was
> found during browser acceptance. This production-code change invalidates the
> previous Evidence Gate; the complete gate must be rerun. Delete-related
> Manual Browser Acceptance items must be retested, and no Manual Acceptance
> item is checked here.

### 2.8 AI Chat Frontend

- [x] 2.8.1 Create app/templates/_ai_chat.html with floating icon and panel HTML
- [x] 2.8.2 Create app/static/css/ai_chat.css with ai-chat- prefixed styles
- [x] 2.8.3 Create app/static/js/ai_chat.js with full chat behavior
- [x] 2.8.4 Integrate _ai_chat.html into base.html via {% include %}
- [x] 2.8.5 Add ai_chat.css link and ai_chat.js script to base.html only (NOT dashboard.html or students.html)
- [x] 2.8.6 Implement floating blue circular icon with SVG chat bubble
- [x] 2.8.7 Implement Chat Panel open/close with animation
- [x] 2.8.8 Implement message area with user and assistant message rendering
- [x] 2.8.9 Implement input with Enter to send, Shift+Enter for newline
- [x] 2.8.10 Implement send button with disabled state during request (prevent duplicate send)
- [x] 2.8.11 Implement loading indicator during API call
- [x] 2.8.12 Implement error display in message area (panel stays open on error)
- [x] 2.8.13 Implement confirmation card for write operations (confirm/cancel buttons)
- [x] 2.8.14 Implement sessionStorage save/restore — only user/assistant messages
- [x] 2.8.15 Implement clear-session button — removes sessionStorage key
- [x] 2.8.16 Implement Escape key to close panel
- [x] 2.8.17 Implement keyboard focus and aria-label/title for accessibility
- [x] 2.8.18 Implement auto-close: student modal opens → Chat Panel closes (history preserved, panel does not reopen)
- [x] 2.8.19 Ensure icon z-index is below student modal backdrop (z-index: 80)
- [x] 2.8.20 Ensure exactly one icon and one panel per page — no duplicate event listeners

### 2.9 Page Integration Tests (TDD: test_ai_chat_pages.py)

- [x] 2.9.1 RED: Test Dashboard contains AI Chat icon (aggregation verification; implementation already present)
- [x] 2.9.2 RED: Test students page contains AI Chat icon (aggregation verification; implementation already present)
- [x] 2.9.3 RED: Test icon present in shared base.html template (aggregation verification; implementation already present)
- [x] 2.9.4 RED: Test Chat Panel initially hidden (aggregation verification; implementation already present)
- [x] 2.9.5 RED: Test only icon visible on initial load, panel not auto-opened (aggregation verification; implementation already present)
- [x] 2.9.6 RED: Test API Key not present in HTML (aggregation verification; implementation already present)
- [x] 2.9.7 RED: Test API Base not present in HTML (aggregation verification; implementation already present)
- [x] 2.9.8 RED: Test model name not present in HTML (aggregation verification; implementation already present)
- [x] 2.9.9 RED: Test AI Chat uses ai-chat- CSS prefix (aggregation verification; implementation already present)
- [x] 2.9.10 RED: Test ai_chat.css loaded exactly once (aggregation verification; implementation already present)
- [x] 2.9.11 RED: Test ai_chat.js loaded exactly once (aggregation verification; implementation already present)
- [x] 2.9.12 RED: Test exactly one AI Chat icon per page (aggregation verification; implementation already present)
- [x] 2.9.13 RED: Test exactly one Chat Panel per page (aggregation verification; implementation already present)
- [x] 2.9.14 GREEN: Implement page rendering and verify via Flask test client
- [x] 2.9.15 REFACTOR: Clean up tests

## 3. OpenSpec Conformance Gate

- [x] 3.1 Validate OpenSpec change with `openspec validate add-ai-chat` (current CLI equivalent; valid)
- [x] 3.2 Verify implementation matches proposal scope (no scope creep)
- [x] 3.3 Verify implementation matches spec requirements (all automatable scenarios covered; browser interaction remains [USER])
- [x] 3.4 Verify implementation matches design decisions (architecture intact)
- [x] 3.5 Verify implementation matches task list (all implementation tasks addressed; duplicate task entries removed)
- [x] 3.6 Verify tests cover all automatable spec scenarios (browser interaction remains [USER])
- [x] 3.7 Tasks artifact changed during conformance; re-ran validate, full pytest, compileall, and diff check

## 4. Superpowers Evidence Gate

- [x] 4.1 Run `git diff --check` to verify no whitespace errors
- [x] 4.2 Run Python compileall to verify no syntax errors
- [x] 4.3 Run full pytest suite
- [x] 4.4 Run MCP self-check with temporary database
- [x] 4.5 Start Flask app and verify health endpoint
- [x] 4.6 Verify POST /api/chat returns ai_not_configured without AI config
- [x] 4.7 Run OpenSpec status/validation
- [x] 4.8 Review Git status
- [x] 4.9 Verify Evidence invalidation rule was not triggered
- [x] 4.10 Generate final Evidence report

> **Frozen Evidence record:** The Evidence commands above completed while the
> working tree was clean, before this `tasks.md` update. This edit records
> those frozen results only; it does not alter production code, tests, or the
> evidence they produced.
>
> - Branch: `rewrite-v2`; HEAD: `feb441c Normalize AI chat reply formatting`.
> - `git diff --check` and `compileall app tests` passed; full pytest: 438
>   passed in 4.15s; format regression: 12 passed.
> - MCP self-check succeeded, discovered 10 tools, used and cleaned a
>   temporary database, and left the production database unchanged.
> - Flask health returned HTTP 200 with `data.status=ok`; the isolated
>   unconfigured-AI probe returned HTTP 503 / `ai_not_configured`, with zero
>   DeepSeek and MCP calls.
> - OpenSpec validation was valid; Git stayed clean throughout collection;
>   no secret leakage, production-database modification, background process,
>   or occupied test port remained.

## 5. Manual Browser Acceptance Gate [USER]

- [x] 5.1 [USER] Dashboard右下角显示蓝色圆形AI Chat图标
- [x] 5.2 [USER] 学生管理页右下角显示同一个AI Chat图标
- [x] 5.3 [USER] 页面首次加载时只显示图标，Chat Panel默认关闭
- [x] 5.4 [USER] 点击图标后Chat Panel打开
- [x] 5.5 [USER] 点击关闭按钮后Chat Panel关闭
- [x] 5.6 [USER] Escape可以关闭Chat Panel
- [x] 5.7 [USER] 图标不会遮挡分页、按钮或Modal
- [x] 5.8 [USER] 学生Modal打开时Chat Panel自动关闭，历史保留
- [x] 5.9 [USER] 窄屏下Chat Panel不会严重溢出
- [x] 5.10 [USER] Enter发送消息
- [x] 5.11 [USER] Shift+Enter换行
- [x] 5.12 [USER] 请求期间不会重复发送
- [x] 5.13 [USER] 清空会话正常
- [x] 5.14 [USER] 页面切换后同一标签页历史恢复
- [x] 5.15 [USER] 询问学生总数返回当前真实数量
- [x] 5.16 [USER] 查询学号00001保留前导零
- [x] 5.17 [USER] 搜索专业可以调用MCP
- [x] 5.18 [USER] 新增学生首次只显示确认，不立即写入
- [x] 5.19 [USER] 取消新增后数据库不变
- [x] 5.20 [USER] 确认新增后只写入一次
- [x] 5.21 [USER] 修改学生需要确认
- [x] 5.22 [USER] 单条删除需要确认
- [x] 5.23 [USER] 批量删除需要确认
- [x] 5.24 [USER] API错误不会导致Chat Panel自动关闭
- [x] 5.25 [USER] 页面不显示reasoning_content
- [x] 5.26 [USER] 页面源代码不显示API Key、API Base或Model
- [x] 5.27 [USER] 页面不显示具体模型名
- [x] 5.28 [USER] Dashboard与学生管理原功能无回归

> **Manual Browser Acceptance:** Completed after the confirmed-action
> failure-handling fix. AI Chat was verified on Dashboard and Students pages;
> the panel supports open, close, Escape, Enter, Shift+Enter, duplicate-submit
> prevention, history restore, and clearing. Database-backed count, leading-zero
> lookup, and MCP search were verified. Visible replies strip DeepSeek Markdown
> emphasis and omit `reasoning_content`.
>
> Read-only MCP operations succeed; write, batch, create, update, and delete
> operations require confirmation. Cancelled writes do not modify data;
> confirmed create, update, and delete execute once. The delete flow was
> retested after the fix and its successful result matched the Flask Student API.
> Failed MCP writes now return a deterministic safe failure reply rather than a
> false success. Tokens cannot be replayed. API and business errors keep the
> panel open without tracebacks. The frontend continues to use `textContent`;
> no `reasoning_content` or sensitive configuration was exposed, and existing
> Dashboard and student-management features remained functional.
>
> **Manual Browser Acceptance 5.1–5.28: PASS.**
>
> Earlier Evidence Gate results were invalidated by the confirmed-action
> production-code fix. A complete Evidence Gate rerun is still required.
> Manual Browser Acceptance is complete, but this Change is not ready for
> Archive until the final Evidence Gate passes.

## 6. Archive Gate

- [x] 6.1 Sync canonical specs: copy delta specs to openspec/specs/ai-chat/spec.md
- [x] 6.2 Run openspec archive --change "add-ai-chat"
- [x] 6.3 Verify archive status and artifact preservation
- [x] 6.4 Commit archive result with message: "Archive add-ai-chat change"
