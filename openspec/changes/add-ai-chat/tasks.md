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
- [ ] 2.3.4 RED: Test tool_calls response parsing
- [ ] 2.3.5 GREEN: Implement tool_calls parsing
- [ ] 2.3.6 RED: Test timeout maps to ai_timeout
- [ ] 2.3.7 RED: Test 401/403 maps to ai_auth_error
- [ ] 2.3.8 RED: Test 429 maps to ai_rate_limited
- [ ] 2.3.9 RED: Test 5xx maps to ai_upstream_error
- [ ] 2.3.10 RED: Test malformed response (missing choices/message) maps to ai_invalid_response
- [ ] 2.3.11 RED: Test other httpx errors map to ai_upstream_error
- [ ] 2.3.12 RED: Test httpx raw exceptions not exposed to browser
- [ ] 2.3.13 RED: Test automatic retry is NOT implemented
- [ ] 2.3.14 RED: Test thinking enabled — sends reasoning_effort from DEEPSEEK_REASONING_EFFORT
- [ ] 2.3.15 RED: Test thinking disabled — no reasoning parameters sent
- [ ] 2.3.16 RED: Test reasoning_content extracted for internal use, not in response
- [x] 2.3.17 RED: Test API Base from env, no hardcoded default
- [x] 2.3.18 RED: Test Model from env, no hardcoded default
- [x] 2.3.19 RED: Test API Key in Bearer header, not in logs/exception text/return values
- [x] 2.3.20 RED: Test MockTransport used in default tests, no real network
- [ ] 2.3.21 GREEN: Implement all error handling, thinking mode, and dependency injection
- [x] 2.3.22 REFACTOR: Clean up DeepSeekClient under test coverage

### 2.4 MCP Tool Adapter (TDD: test_mcp_tool_adapter.py)

- [ ] 2.4.1 RED: Test discovery of all 10 student tools
- [ ] 2.4.2 GREEN: Implement MCPToolAdapter with list_tools()
- [ ] 2.4.3 RED: Test tool conversion to OpenAI-compatible function format (type: function, name, description, parameters)
- [ ] 2.4.4 GREEN: Implement tool conversion
- [ ] 2.4.5 RED: Test request-level MCP Session — one session per chat request
- [ ] 2.4.6 RED: Test multiple tool calls share the same MCP Session
- [ ] 2.4.7 RED: Test Session is closed after request ends
- [ ] 2.4.8 RED: Test MCP server subprocess is NOT started for each individual tool call
- [ ] 2.4.9 RED: Test unknown tool returns structured error
- [ ] 2.4.10 RED: Test invalid JSON arguments return structured error
- [ ] 2.4.11 RED: Test MCP tool errors returned as tool results, not exceptions
- [ ] 2.4.12 RED: Test raw MCP debug data (structured_content, parsed_text, content blocks) not shown to users
- [ ] 2.4.13 RED: Test open_mcp_session() extension works
- [ ] 2.4.14 RED: Test list_tools_in_session() works
- [ ] 2.4.15 RED: Test call_tool_in_session() works
- [ ] 2.4.16 GREEN: Implement all adapter logic with session extensions
- [ ] 2.4.17 REFACTOR: Clean up MCPToolAdapter

### 2.5 AI Action Confirmation (TDD: test_ai_action_confirmation.py)

- [ ] 2.5.1 RED: Test token creation and signing with itsdangerous
- [ ] 2.5.2 GREEN: Implement AIActionConfirmation with URLSafeTimedSerializer
- [ ] 2.5.3 RED: Test valid token verification returns original payload
- [ ] 2.5.4 GREEN: Implement token verification
- [ ] 2.5.5 RED: Test expired token returns structured error
- [ ] 2.5.6 RED: Test tampered token returns structured error
- [ ] 2.5.7 RED: Test sequential replay — consumed token cannot be reused
- [ ] 2.5.8 RED: Test concurrent replay — two confirmations for same token, at most one succeeds
- [ ] 2.5.9 RED: Test thread safety — threading.Lock protects consumed-action tracking
- [ ] 2.5.10 RED: Test MCP write tool failure — token remains consumed, not reusable
- [ ] 2.5.11 RED: Test SECRET_KEY missing — write confirmation fail-closed (ai_confirmation_not_configured)
- [ ] 2.5.12 RED: Test SECRET_KEY at development default — write confirmation fail-closed
- [ ] 2.5.13 RED: Test token not stored in sessionStorage
- [ ] 2.5.14 GREEN: Implement all confirmation logic with thread safety
- [ ] 2.5.15 REFACTOR: Clean up AIActionConfirmation

### 2.6 AI Chat Service (TDD: test_ai_chat_service.py)

- [ ] 2.6.1 RED: Test normal Q&A returns text reply
- [ ] 2.6.2 GREEN: Implement AIChatService with basic orchestration
- [ ] 2.6.3 RED: Test single read tool call returns tool result in next reply
- [ ] 2.6.4 RED: Test multiple read-only tool calls — all executed in order via same session
- [ ] 2.6.5 RED: Test mixed read+write — read tools before first write execute, write generates Pending Action
- [ ] 2.6.6 RED: Test multiple write tools — none execute, returns ai_multiple_write_actions
- [ ] 2.6.7 RED: Test unknown tool — not executed, structured error returned
- [ ] 2.6.8 RED: Test at most one Pending Action per response
- [ ] 2.6.9 RED: Test multi-round Tool Loop
- [ ] 2.6.10 RED: Test max tool rounds limit enforced
- [ ] 2.6.11 RED: Test MCP tool error does not crash service
- [ ] 2.6.12 RED: Test write tool returns pending action instead of executing
- [ ] 2.6.13 RED: Test confirmed write executes exactly once
- [ ] 2.6.14 RED: Test cancelled write does not execute
- [ ] 2.6.15 RED: Test reasoning_content passes through internally during Tool Loop
- [ ] 2.6.16 RED: Test reasoning_content not returned to user in final reply
- [ ] 2.6.17 RED: Test MCP raw diagnostic objects not returned to user
- [ ] 2.6.18 GREEN: Implement all orchestration logic
- [ ] 2.6.19 REFACTOR: Clean up AIChatService

### 2.7 Chat Routes (TDD: test_chat_routes.py)

- [ ] 2.7.1 RED: Test POST /api/chat with valid messages returns reply
- [ ] 2.7.2 GREEN: Implement chat.py blueprint with POST /api/chat
- [ ] 2.7.3 RED: Test POST /api/chat/actions/confirm with valid token
- [ ] 2.7.4 GREEN: Implement POST /api/chat/actions/confirm
- [ ] 2.7.5 RED: Test non-JSON body returns validation_error
- [ ] 2.7.6 RED: Test empty messages returns validation_error
- [ ] 2.7.7 RED: Test non-array messages returns validation_error
- [ ] 2.7.8 RED: Test blank user message returns validation_error
- [ ] 2.7.9 RED: Test illegal role (system, developer, tool) returns validation_error
- [ ] 2.7.10 RED: Test last message must be user — returns validation_error otherwise
- [ ] 2.7.11 RED: Test all messages validated before truncation — illegal messages in tail not skipped
- [ ] 2.7.12 RED: Test history exceeds max limit is truncated (last user message retained)
- [ ] 2.7.13 RED: Test message exceeds max length returns validation_error
- [ ] 2.7.14 RED: Test missing config returns ai_not_configured
- [ ] 2.7.15 RED: Test upstream auth error returns ai_auth_error
- [ ] 2.7.16 RED: Test upstream timeout returns ai_timeout
- [ ] 2.7.17 RED: Test upstream rate limit returns ai_rate_limited
- [ ] 2.7.18 RED: Test internal error does not leak traceback or API key
- [ ] 2.7.19 RED: Test API URL does not contain model name
- [ ] 2.7.20 RED: Test confirm endpoint returns deterministic Chinese reply
- [ ] 2.7.21 RED: Test confirm returns safe action_result without structured_content/parsed_text
- [ ] 2.7.22 RED: Test confirm does not call DeepSeek again
- [ ] 2.7.23 RED: Test confirm does not accept browser-submitted arguments
- [ ] 2.7.24 GREEN: Implement all route handling
- [ ] 2.7.25 Register chat blueprint in app/__init__.py
- [ ] 2.7.26 REFACTOR: Clean up chat routes

### 2.8 AI Chat Frontend

- [ ] 2.8.1 Create app/templates/_ai_chat.html with floating icon and panel HTML
- [ ] 2.8.2 Create app/static/css/ai_chat.css with ai-chat- prefixed styles
- [ ] 2.8.3 Create app/static/js/ai_chat.js with full chat behavior
- [ ] 2.8.4 Integrate _ai_chat.html into base.html via {% include %}
- [ ] 2.8.5 Add ai_chat.css link and ai_chat.js script to base.html only (NOT dashboard.html or students.html)
- [ ] 2.8.6 Implement floating blue circular icon with SVG chat bubble
- [ ] 2.8.7 Implement Chat Panel open/close with animation
- [ ] 2.8.8 Implement message area with user and assistant message rendering
- [ ] 2.8.9 Implement input with Enter to send, Shift+Enter for newline
- [ ] 2.8.10 Implement send button with disabled state during request (prevent duplicate send)
- [ ] 2.8.11 Implement loading indicator during API call
- [ ] 2.8.12 Implement error display in message area (panel stays open on error)
- [ ] 2.8.13 Implement confirmation card for write operations (confirm/cancel buttons)
- [ ] 2.8.14 Implement sessionStorage save/restore — only user/assistant messages
- [ ] 2.8.15 Implement clear-session button — removes sessionStorage key
- [ ] 2.8.16 Implement Escape key to close panel
- [ ] 2.8.17 Implement keyboard focus and aria-label/title for accessibility
- [ ] 2.8.18 Implement auto-close: student modal opens → Chat Panel closes (history preserved, panel does not reopen)
- [ ] 2.8.19 Ensure icon z-index is below student modal backdrop (z-index: 80)
- [ ] 2.8.20 Ensure exactly one icon and one panel per page — no duplicate event listeners

### 2.9 Page Integration Tests (TDD: test_ai_chat_pages.py)

- [ ] 2.9.1 RED: Test Dashboard contains AI Chat icon
- [ ] 2.9.2 RED: Test students page contains AI Chat icon
- [ ] 2.9.3 RED: Test icon present in shared base.html template
- [ ] 2.9.4 RED: Test Chat Panel initially hidden
- [ ] 2.9.5 RED: Test only icon visible on initial load, panel not auto-opened
- [ ] 2.9.6 RED: Test API Key not present in HTML
- [ ] 2.9.7 RED: Test API Base not present in HTML
- [ ] 2.9.8 RED: Test model name not present in HTML
- [ ] 2.9.9 RED: Test AI Chat uses ai-chat- CSS prefix
- [ ] 2.9.10 RED: Test ai_chat.css loaded exactly once
- [ ] 2.9.11 RED: Test ai_chat.js loaded exactly once
- [ ] 2.9.12 RED: Test exactly one AI Chat icon per page
- [ ] 2.9.13 RED: Test exactly one Chat Panel per page
- [ ] 2.9.14 GREEN: Implement page rendering and verify via Flask test client
- [ ] 2.9.15 REFACTOR: Clean up tests

## 3. OpenSpec Conformance Gate

- [ ] 3.1 Run openspec verify --change "add-ai-chat" to check completeness
- [ ] 3.2 Verify implementation matches proposal scope (no scope creep)
- [ ] 3.3 Verify implementation matches spec requirements (all scenarios covered)
- [ ] 3.4 Verify implementation matches design decisions (architecture intact)
- [ ] 3.5 Verify implementation matches task list (all tasks addressed)
- [ ] 3.6 Verify tests cover all spec scenarios (test matrix complete)
- [ ] 3.7 If any code or test changed after conformance check, re-run relevant tests and re-check

## 4. Superpowers Evidence Gate

- [ ] 4.1 Run `git diff --check` to verify no whitespace errors
- [ ] 4.2 Run Python compileall to verify no syntax errors
- [ ] 4.3 Run full pytest suite
- [ ] 4.4 Run MCP self-check with temporary database
- [ ] 4.5 Start Flask app and verify health endpoint
- [ ] 4.6 Start Flask app and verify POST /api/chat returns ai_not_configured (no API key)
- [ ] 4.7 Run `openspec status --change "add-ai-chat"` and verify all artifacts done
- [ ] 4.8 Run `git status` and review changed files
- [ ] 4.9 If any file was modified after evidence collection started, invalidate all evidence and re-run from 4.1
- [ ] 4.10 Generate final evidence report with real command output

## 5. Manual Browser Acceptance Gate [USER]

- [ ] 5.1 [USER] Dashboard右下角显示蓝色圆形AI Chat图标
- [ ] 5.2 [USER] 学生管理页右下角显示同一个AI Chat图标
- [ ] 5.3 [USER] 页面首次加载时只显示图标，Chat Panel默认关闭
- [ ] 5.4 [USER] 点击图标后Chat Panel打开
- [ ] 5.5 [USER] 点击关闭按钮后Chat Panel关闭
- [ ] 5.6 [USER] Escape可以关闭Chat Panel
- [ ] 5.7 [USER] 图标不会遮挡分页、按钮或Modal
- [ ] 5.8 [USER] 学生Modal打开时Chat Panel自动关闭，历史保留
- [ ] 5.9 [USER] 窄屏下Chat Panel不会严重溢出
- [ ] 5.10 [USER] Enter发送消息
- [ ] 5.11 [USER] Shift+Enter换行
- [ ] 5.12 [USER] 请求期间不会重复发送
- [ ] 5.13 [USER] 清空会话正常
- [ ] 5.14 [USER] 页面切换后同一标签页历史恢复
- [ ] 5.15 [USER] 询问学生总数返回当前真实数量
- [ ] 5.16 [USER] 查询学号00001保留前导零
- [ ] 5.17 [USER] 搜索专业可以调用MCP
- [ ] 5.18 [USER] 新增学生首次只显示确认，不立即写入
- [ ] 5.19 [USER] 取消新增后数据库不变
- [ ] 5.20 [USER] 确认新增后只写入一次
- [ ] 5.21 [USER] 修改学生需要确认
- [ ] 5.22 [USER] 单条删除需要确认
- [ ] 5.23 [USER] 批量删除需要确认
- [ ] 5.24 [USER] API错误不会导致Chat Panel自动关闭
- [ ] 5.25 [USER] 页面不显示reasoning_content
- [ ] 5.26 [USER] 页面源代码不显示API Key、API Base或Model
- [ ] 5.27 [USER] 页面不显示具体模型名
- [ ] 5.28 [USER] Dashboard与学生管理原功能无回归

## 6. Archive Gate

- [ ] 6.1 Sync canonical specs: copy delta specs to openspec/specs/ai-chat/spec.md
- [ ] 6.2 Run openspec archive --change "add-ai-chat"
- [ ] 6.3 Verify archive status and artifact preservation
- [ ] 6.4 Commit archive result with message: "Archive add-ai-chat change"
