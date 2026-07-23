## ADDED Requirements

### Requirement: AI Chat configuration from environment variables
The system SHALL read all DeepSeek and AI Chat configuration from environment variables only. No API key, API base URL, or model name SHALL be hardcoded in Python, HTML, JavaScript, CSS, tests, or documentation examples.

#### Scenario: All AI config comes from environment variables
- **WHEN** the AI Chat service initializes
- **THEN** it SHALL read `DEEPSEEK_API_KEY`, `DEEPSEEK_API_BASE`, `DEEPSEEK_MODEL`, `DEEPSEEK_TIMEOUT_SECONDS`, `DEEPSEEK_MAX_OUTPUT_TOKENS`, `DEEPSEEK_THINKING`, `DEEPSEEK_REASONING_EFFORT`, `AI_MAX_TOOL_ROUNDS`, `AI_MAX_HISTORY_MESSAGES`, `AI_MAX_MESSAGE_LENGTH`, and `AI_CONFIRMATION_TOKEN_TTL_SECONDS` from environment variables

#### Scenario: Missing API Key does not crash the app
- **WHEN** `DEEPSEEK_API_KEY` is not set and the Flask app starts
- **THEN** the app SHALL start normally
- **AND** the Dashboard and student management pages SHALL render correctly
- **AND** sending a chat message SHALL return a structured `ai_not_configured` error without leaking which specific variable is missing

#### Scenario: Missing API Base or Model has the same behavior
- **WHEN** `DEEPSEEK_API_BASE` or `DEEPSEEK_MODEL` is not set
- **THEN** the app SHALL start normally
- **AND** sending a chat message SHALL return `ai_not_configured`

#### Scenario: No hardcoded fallback values
- **WHEN** `DEEPSEEK_API_BASE` or `DEEPSEEK_MODEL` is not set
- **THEN** the system SHALL NOT silently fall back to a default API base or default model name
- **AND** the `ai_not_configured` error SHALL be returned

#### Scenario: API Key never leaks to client-side
- **WHEN** any chat response is rendered
- **THEN** the API Key SHALL NOT appear in HTML source, JavaScript variables, Flask response JSON, sessionStorage, localStorage, logs, tracebacks, or MCP arguments

### Requirement: AI Chat API routes
The system SHALL provide `POST /api/chat` and `POST /api/chat/actions/confirm` endpoints using business-semantic paths. No model name SHALL appear in the URL.

#### Scenario: POST /api/chat accepts messages
- **WHEN** a client sends `POST /api/chat` with a JSON body containing `messages` (non-empty array of `{role, content}` objects)
- **THEN** the response SHALL use the unified JSON response structure
- **AND** `data.reply` SHALL contain the AI-generated text
- **AND** `data.requires_confirmation` SHALL indicate whether a write action needs confirmation
- **AND** `data.pending_action` SHALL contain the confirmation details when required

#### Scenario: Server validates all messages before truncation
- **WHEN** a client sends `POST /api/chat` with messages
- **THEN** the server SHALL validate all messages (roles, content, length) first
- **AND** SHALL NOT allow illegal messages to escape detection by being in the truncated tail
- **AND** after full validation, truncate to the most recent `AI_MAX_HISTORY_MESSAGES` entries
- **AND** ensure the last `user` message is always retained after truncation

#### Scenario: Last message must be user role
- **WHEN** a client sends `POST /api/chat` where the last message is not `user`
- **THEN** the server SHALL return `validation_error` with status 400

#### Scenario: POST /api/chat rejects invalid input
- **WHEN** a client sends `POST /api/chat` with a non-JSON body, missing `messages`, empty `messages`, non-array `messages`, blank user message, or messages with illegal roles
- **THEN** the response SHALL return `validation_error` with status 400

#### Scenario: POST /api/chat rejects system or tool roles from browser
- **WHEN** a client sends `POST /api/chat` with a message role of `system`, `developer`, or `tool`
- **THEN** the response SHALL return `validation_error` with status 400

#### Scenario: POST /api/chat/actions/confirm executes the pending action
- **WHEN** a client sends `POST /api/chat/actions/confirm` with a valid `confirmation_token`
- **THEN** the server SHALL verify the token signature, expiration, and consumption status atomically under a lock
- **AND** mark the token as consumed before executing the MCP write tool
- **AND** execute only the tool name and arguments embedded in the original signed token
- **AND** SHALL NOT use any arguments re-submitted by the browser
- **AND** SHALL NOT call DeepSeek again after confirming
- **AND** return a deterministic Chinese reply in `data.reply` (e.g., "学生新增成功。")
- **AND** return safe business data in `data.action_result` without structured_content, parsed_text, or raw content blocks
- **AND** SHALL NOT return `reasoning_content`

#### Scenario: Confirm response structure
- **WHEN** a confirm request succeeds
- **THEN** the response SHALL contain:
  - `data.reply`: deterministic Chinese confirmation text
  - `data.requires_confirmation`: false
  - `data.pending_action`: null
  - `data.action_result`: object with `success` and safe business `data` only

#### Scenario: POST /api/chat/actions/confirm rejects invalid tokens
- **WHEN** a client sends a tampered, expired, or already-consumed `confirmation_token`
- **THEN** the server SHALL return a structured error (`invalid_token`, `token_expired`, or `token_already_used`)

#### Scenario: Concurrent confirm requests for same token — at most one succeeds
- **WHEN** two concurrent `POST /api/chat/actions/confirm` requests arrive for the same valid token
- **THEN** at most one SHALL execute the MCP write tool
- **AND** the other SHALL receive `token_already_used`

#### Scenario: MCP write tool failure does not make token reusable
- **WHEN** a confirmed token is consumed but the MCP write tool fails
- **THEN** the token SHALL remain marked as consumed
- **AND** SHALL NOT be reusable
- **AND** the user SHALL need to re-request the operation to get a new token

#### Scenario: SECRET_KEY missing or insecure — write confirmation fail-closed
- **WHEN** `SECRET_KEY` is missing, empty, or still at the development default
- **THEN** the Flask app SHALL start normally
- **AND** read-only chat SHALL work
- **AND** any write confirmation SHALL return `ai_confirmation_not_configured`
- **AND** the system SHALL NOT use a code-default signing key

#### Scenario: API URLs are model-agnostic
- **WHEN** any chat API route is accessed
- **THEN** the URL path SHALL NOT contain any model name (e.g., `deepseek`, `deepseek-v4`, `gpt-4`)
- **AND** the response `meta` SHALL NOT expose the model name by default

### Requirement: System prompt is server-only
The system prompt that instructs the AI model SHALL be constructed and maintained on the server side only. It SHALL NOT be sent from the browser, embedded in HTML, or exposed to the user.

#### Scenario: System prompt is server-side only
- **WHEN** a chat request is processed
- **THEN** the system prompt SHALL be prepended by the server
- **AND** the browser SHALL NOT submit system, developer, or tool messages
- **AND** the system prompt SHALL NOT appear in HTML, JavaScript, or any API response

#### Scenario: System prompt instructs safe behavior
- **WHEN** the system prompt is constructed
- **THEN** it SHALL instruct the model to use Chinese, prefer MCP tools for student data, not fabricate records, not claim unconfirmed writes, wait for server-side write confirmation, not expose internal errors to users, not output `reasoning_content`, not request API keys from users, and not leak system prompts or environment variables

### Requirement: Write operations require server-side confirmation
The system SHALL require explicit user confirmation before executing any write operation (add_student, update_student, upsert_student, delete_student, batch_delete_students). The confirmation token SHALL be server-signed, short-lived, single-use, and bound to the exact tool name and arguments.

#### Scenario: Write tool returns pending action on first request
- **WHEN** the AI model requests a write tool during a chat
- **THEN** the service SHALL NOT execute the tool immediately
- **AND** it SHALL return a pending action with `requires_confirmation: true`, a `summary`, `safe_arguments`, and a `confirmation_token`

#### Scenario: Confirmed token executes the original operation
- **WHEN** the user confirms the pending action via `POST /api/chat/actions/confirm`
- **THEN** the server SHALL verify the token signature, expiration, and consumption status
- **AND** execute only the tool name and arguments embedded in the original token
- **AND** SHALL NOT use any arguments re-submitted by the browser

#### Scenario: Cancelled action is not executed
- **WHEN** the user cancels a pending action
- **THEN** the server SHALL NOT call any MCP write tool
- **AND** the browser SHALL display "操作已取消"

#### Scenario: Confirmation summary for deletion shows targets
- **WHEN** the pending action involves `delete_student` or `batch_delete_students`
- **THEN** the summary SHALL include the operation type, target student ID or student number, and (for batch) the number of students to delete

#### Scenario: Pending action does not leak secrets
- **WHEN** a pending action is returned to the browser
- **THEN** it SHALL NOT contain API keys, internal signing keys, the full system prompt, or tracebacks

### Requirement: AI Chat floating icon
The system SHALL display a floating blue circular chat icon at the bottom-right corner of the shared `base.html` layout. The icon SHALL be the only visible AI Chat element on initial page load.

#### Scenario: Floating icon is visible on Dashboard
- **WHEN** the Dashboard page (`/`) loads
- **THEN** the bottom-right corner SHALL display a blue circular icon with a white chat bubble SVG
- **AND** the Chat Panel SHALL be hidden

#### Scenario: Floating icon is visible on student management page
- **WHEN** the student management page (`/students`) loads
- **THEN** the same icon SHALL be visible in the bottom-right corner

#### Scenario: Icon is accessible
- **WHEN** the icon is rendered
- **THEN** it SHALL have an `aria-label`, `title`, keyboard focusability, and support Enter/Space to open the panel

#### Scenario: Icon does not obscure critical UI
- **WHEN** the icon is visible
- **THEN** it SHALL NOT overlap the student table action buttons, pagination controls, modal dialogs, or page navigation

#### Scenario: AI Chat CSS and JS loaded once from base.html
- **WHEN** any page that extends `base.html` is rendered
- **THEN** `ai_chat.css` SHALL be loaded once via `<link>` in the shared layout
- **AND** `_ai_chat.html` SHALL be included once via `{% include %}` in the shared layout
- **AND** `ai_chat.js` SHALL be loaded once via `<script>` in the shared layout
- **AND** dashboard.html and students.html SHALL NOT independently load AI Chat resources
- **AND** exactly one AI Chat icon and one Chat Panel SHALL exist per page

#### Scenario: AI Chat resources are not duplicated on subpages
- **WHEN** a Dashboard or students page is rendered
- **THEN** the page SHALL contain exactly one `<link>` for `ai_chat.css`
- **AND** exactly one `<script>` for `ai_chat.js`
- **AND** exactly one AI Chat icon element
- **AND** exactly one Chat Panel element

### Requirement: AI Chat panel
The system SHALL provide a floating chat panel that opens when the user clicks the blue icon. The panel SHALL support the full chat interaction workflow.

#### Scenario: Panel opens on icon click
- **WHEN** the user clicks the floating icon
- **THEN** the Chat Panel SHALL slide or fade in
- **AND** the icon SHALL either remain visible (as a close button) or be hidden — the design SHALL choose one behavior

#### Scenario: Panel closes on close button or Escape
- **WHEN** the user clicks the close button or presses Escape
- **THEN** the Chat Panel SHALL close
- **AND** the icon SHALL return to its initial state

#### Scenario: Panel does not auto-close on error
- **WHEN** an API error occurs during a chat request
- **THEN** the panel SHALL remain open
- **AND** the error SHALL be displayed in the message area

#### Scenario: Panel contains all required UI elements
- **WHEN** the panel is open
- **THEN** it SHALL contain a title ("AI 助手"), close button, clear-session button, message area, input field, send button, loading indicator, error display area, and confirmation card area

#### Scenario: Enter sends, Shift+Enter inserts newline
- **WHEN** the user presses Enter in the input field
- **THEN** the message SHALL be sent
- **WHEN** the user presses Shift+Enter
- **THEN** a newline SHALL be inserted

#### Scenario: Blank messages are not sent
- **WHEN** the input contains only whitespace
- **THEN** the send button SHALL be disabled
- **AND** pressing Enter SHALL NOT send the message

#### Scenario: Duplicate send is prevented during request
- **WHEN** a chat request is in progress
- **THEN** the send button SHALL be disabled
- **AND** pressing Enter SHALL NOT trigger a new request

#### Scenario: Close does not clear history
- **WHEN** the panel is closed and reopened
- **THEN** the previous messages SHALL be restored from sessionStorage

### Requirement: Chat history in sessionStorage
The browser SHALL store chat history in `sessionStorage` and restore it on page navigation within the same tab. Only user and assistant role messages SHALL be stored.

#### Scenario: User and assistant messages are saved
- **WHEN** a chat response is received
- **THEN** the user message and the assistant reply SHALL be appended to the `sessionStorage` chat history array

#### Scenario: Sensitive data is not saved
- **WHEN** chat history is saved to `sessionStorage`
- **THEN** it SHALL NOT include system prompts, tool messages, tool arguments, confirmation tokens, `reasoning_content`, MCP raw results, API keys, API bases, or model names

#### Scenario: Clear session button removes history
- **WHEN** the user clicks the clear-session button
- **THEN** the `sessionStorage` key SHALL be removed
- **AND** the message area SHALL be cleared

#### Scenario: History is restored on page navigation
- **WHEN** the user navigates from Dashboard to /students or back
- **THEN** the chat history from `sessionStorage` SHALL be restored in the panel

### Requirement: MCP Tool Adapter
The system SHALL provide an `MCPToolAdapter` that discovers existing MCP student tools, converts them to OpenAI-compatible function tools, and invokes them during chat requests with session reuse.

#### Scenario: Adapter discovers all 10 student tools
- **WHEN** the adapter lists tools
- **THEN** it SHALL discover exactly `list_students`, `search_students`, `get_student_by_id`, `get_student_by_number`, `count_students`, `add_student`, `update_student`, `upsert_student`, `delete_student`, and `batch_delete_students`

#### Scenario: Tools are converted to OpenAI-compatible format
- **WHEN** tools are converted
- **THEN** each tool SHALL have `type: "function"` and a `function` object with `name`, `description`, and `parameters` matching the MCP input schema

#### Scenario: Adapter reuses MCP session per request
- **WHEN** multiple tool calls happen within one chat request
- **THEN** the adapter SHALL reuse the same MCP session
- **AND** SHALL NOT start a new MCP server subprocess for each individual tool call

#### Scenario: Unknown tool is rejected
- **WHEN** the AI model requests a tool not in the discovered set
- **THEN** the adapter SHALL return a structured error

#### Scenario: MCP tool errors are returned as tool results
- **WHEN** an MCP tool call fails
- **THEN** the error SHALL be returned as a tool result to the model
- **AND** SHALL NOT cause an unhandled exception

#### Scenario: Raw MCP debug data is not shown to users
- **WHEN** a tool result is processed
- **THEN** the user SHALL only see the AIChatService-formatted reply
- **AND** SHALL NOT see `structured_content`, `parsed_text`, raw content blocks, or tracebacks

### Requirement: DeepSeek Client uses httpx only
The system SHALL provide a `DeepSeekClient` that uses `httpx` as its only HTTP library to send OpenAI-compatible Chat Completions requests. No fallback to `openai` SDK, `requests`, or any other HTTP library exists. If `httpx` is not installed, the system SHALL stop and report the missing dependency.

#### Scenario: Client sends standard chat completion request
- **WHEN** a chat request is made
- **THEN** the client SHALL send messages to `{DEEPSEEK_API_BASE}/chat/completions` with model `DEEPSEEK_MODEL`
- **AND** the request SHALL use Bearer Authentication with `DEEPSEEK_API_KEY`
- **AND** the API Key SHALL NOT appear in logs, exception text, return values, or test snapshots

#### Scenario: Client uses httpx exclusively
- **WHEN** the client sends a request
- **THEN** it SHALL use `httpx` as the HTTP library
- **AND** it SHALL NOT use `openai` SDK, `requests`, or any other HTTP library
- **AND** it SHALL support dependency injection via `httpx.Client`, `httpx.AsyncClient`, or `httpx.Transport` for test isolation

#### Scenario: Default tests use MockTransport, no real network
- **WHEN** running default pytest tests
- **THEN** the `DeepSeekClient` SHALL use `httpx.MockTransport` or an injectable transport
- **AND** SHALL NOT access real network or real API endpoints

#### Scenario: Client parses normal text response
- **WHEN** the upstream returns a normal text response
- **THEN** the client SHALL return the assistant message content

#### Scenario: Client parses tool_calls response
- **WHEN** the upstream returns a response with `tool_calls`
- **THEN** the client SHALL return the tool call data including `id`, `type`, `function.name`, and `function.arguments`

#### Scenario: Client handles timeout
- **WHEN** the upstream request times out
- **THEN** the client SHALL raise a timeout error mapped to `ai_timeout`

#### Scenario: Client handles 401/403
- **WHEN** the upstream returns 401 or 403
- **THEN** the client SHALL map it to `ai_auth_error`

#### Scenario: Client handles 429
- **WHEN** the upstream returns 429
- **THEN** the client SHALL map it to `ai_rate_limited`

#### Scenario: Client handles 5xx
- **WHEN** the upstream returns a 5xx status
- **THEN** the client SHALL map it to `ai_upstream_error`

#### Scenario: Client handles malformed response
- **WHEN** the upstream returns a response missing `choices` or `message`
- **THEN** the client SHALL map it to `ai_invalid_response`

#### Scenario: Client does not expose httpx internals to browser
- **WHEN** an httpx error occurs
- **THEN** the client SHALL NOT return raw httpx exceptions, complete response bodies, headers, or URLs to the browser
- **AND** all errors SHALL be mapped to structured `ai_*` error codes

#### Scenario: Client does not implement automatic retry
- **WHEN** a request fails due to network error or upstream error
- **THEN** the client SHALL NOT automatically retry the request
- **AND** it SHALL return the appropriate error code

#### Scenario: Thinking mode is controlled by env var
- **WHEN** `DEEPSEEK_THINKING` is true
- **THEN** the client SHALL include `reasoning_effort` from `DEEPSEEK_REASONING_EFFORT` in the request
- **WHEN** `DEEPSEEK_THINKING` is false or unset
- **THEN** the client SHALL NOT send reasoning-related parameters

#### Scenario: reasoning_content is extracted for internal use only
- **WHEN** the upstream returns `reasoning_content`
- **THEN** the client SHALL extract it for internal use
- **AND** it SHALL NOT appear in Flask responses, HTML, JavaScript, sessionStorage, logs, or test snapshots
- **AND** it SHALL only be used for internal assistant message re-send during Tool Loop

### Requirement: AIChatService orchestration
The system SHALL provide an `AIChatService` that orchestrates the chat request loop: construct system prompt, call DeepSeek, handle tool calls, manage tool rounds, and handle write confirmation.

#### Scenario: Service handles normal Q&A
- **WHEN** the user asks a simple question
- **THEN** the service SHALL return the AI's text reply

#### Scenario: Service handles single read tool call
- **WHEN** the AI decides to call one read tool
- **THEN** the service SHALL execute it and return the result in the next AI response

#### Scenario: Service handles multiple read-only tool calls
- **WHEN** the AI calls multiple read-only tools in one response
- **THEN** the service SHALL execute them in response order
- **AND** use the same MCP Session for all calls
- **AND** return each tool result with the corresponding `tool_call_id`
- **AND** continue the Tool Loop

#### Scenario: Service rejects mixed read+write with single pending action
- **WHEN** the AI calls both read and write tools in one response
- **THEN** the service SHALL execute read-only tools that appear before the first write tool
- **AND** stop at the first write tool
- **AND** generate exactly one Pending Action for that write tool
- **AND** SHALL NOT execute any write tool

#### Scenario: Service rejects multiple write tools
- **WHEN** the AI calls two or more write tools in one response
- **THEN** the service SHALL NOT execute any write tool
- **AND** return `ai_multiple_write_actions`
- **AND** indicate that only one write can be confirmed at a time

#### Scenario: Service rejects unknown tools
- **WHEN** the AI requests a tool not in the discovered set
- **THEN** the service SHALL return a structured tool result or error
- **AND** SHALL NOT attempt to call it through MCP

#### Scenario: Each response returns at most one Pending Action
- **WHEN** the service processes a tool response that would generate multiple Pending Actions
- **THEN** it SHALL return at most one Pending Action
- **AND** return `ai_multiple_write_actions` for the rest

#### Scenario: Service enforces maximum tool rounds
- **WHEN** the number of tool call rounds exceeds `AI_MAX_TOOL_ROUNDS`
- **THEN** the service SHALL stop the loop and return a message indicating the limit was reached

#### Scenario: Write tools return pending action on first request
- **WHEN** the AI requests a write tool
- **THEN** the service SHALL return a pending action with confirmation details instead of executing the tool

#### Scenario: Confirmed write executes exactly once
- **WHEN** the user confirms a pending write
- **THEN** the service SHALL execute the original tool and arguments exactly once
- **AND** SHALL NOT allow the same token to be used again

#### Scenario: Cancel does not execute
- **WHEN** the user cancels a pending action
- **THEN** the service SHALL NOT execute any write tool
- **AND** SHALL return a cancellation message

#### Scenario: reasoning_content passes through internally during Tool Loop
- **WHEN** the upstream response includes both `tool_calls` and `reasoning_content`
- **THEN** the service SHALL preserve the full assistant message (including `reasoning_content`) for internal Tool Loop continuation
- **AND** SHALL include `reasoning_content` in the assistant message sent to DeepSeek on the next round
- **AND** SHALL NOT include `reasoning_content` in the final user-facing reply
- **AND** SHALL NOT save `reasoning_content` to sessionStorage, logs, or browser history

#### Scenario: reasoning_content is discarded after Tool Loop ends
- **WHEN** the Tool Loop completes
- **THEN** `reasoning_content` from the final turn SHALL be discarded
- **AND** SHALL NOT appear in any stored message history

### Requirement: Chat routes error handling
The system SHALL return structured JSON errors for all failure modes without leaking internal details.

#### Scenario: Upstream auth error
- **WHEN** the DeepSeek API returns 401 or 403
- **THEN** the chat route SHALL return `ai_auth_error`

#### Scenario: Upstream timeout
- **WHEN** the DeepSeek API request times out
- **THEN** the chat route SHALL return `ai_timeout`

#### Scenario: Upstream rate limit
- **WHEN** the DeepSeek API returns 429
- **THEN** the chat route SHALL return `ai_rate_limited`

#### Scenario: Upstream server error
- **WHEN** the DeepSeek API returns 5xx
- **THEN** the chat route SHALL return `ai_upstream_error`

#### Scenario: Internal error does not leak internals
- **WHEN** an unexpected exception occurs
- **THEN** the error response SHALL NOT contain tracebacks, API keys, API bases, database paths, MCP commands, or environment secrets

### Requirement: AI Chat auto-closes when student modal opens
The system SHALL automatically close the AI Chat Panel when the student create/edit modal opens. Chat history SHALL be preserved.

#### Scenario: Chat Panel auto-closes on modal open
- **WHEN** the student create/edit modal opens
- **THEN** the AI Chat Panel SHALL automatically close
- **AND** chat history SHALL be preserved in sessionStorage
- **AND** the Chat Panel SHALL NOT automatically re-open when the modal closes

#### Scenario: Floating icon z-index is below modal backdrop
- **WHEN** a student modal is open
- **THEN** the AI Chat floating icon SHALL have a lower z-index than the modal backdrop
- **AND** the icon SHALL NOT block clicks on modal elements

#### Scenario: Modal open does not clear chat history
- **WHEN** the student modal opens and closes
- **THEN** the Chat Panel history SHALL remain intact in sessionStorage
- **AND** the Panel SHALL remain closed after the modal closes

### Requirement: AI Chat uses independent CSS namespace
All AI Chat styles SHALL use a dedicated CSS class prefix to prevent conflicts with existing page styles.

#### Scenario: AI Chat uses ai-chat- prefix
- **WHEN** any AI Chat CSS class is defined
- **THEN** it SHALL use the `ai-chat-` prefix (e.g., `ai-chat-icon`, `ai-chat-panel`, `ai-chat-message`)
- **AND** it SHALL NOT reuse ambiguous global class names like `.modal`, `.sidebar`, `.card`, or `.button` for structurally different elements

### Requirement: Thinking and reasoning_content
The `reasoning_content` field returned by the upstream API SHALL be handled server-side only and SHALL NOT be exposed to the browser.

#### Scenario: reasoning_content is server-side only
- **WHEN** the upstream response includes `reasoning_content`
- **THEN** the server SHALL extract it for internal processing
- **AND** it SHALL NOT be included in the Flask response JSON
- **AND** it SHALL NOT be stored in sessionStorage
- **AND** it SHALL NOT appear in HTML, JavaScript, or logs

#### Scenario: Thinking is controlled by environment
- **WHEN** `DEEPSEEK_THINKING` is set to a truthy value
- **THEN** the client SHALL configure the request to enable thinking
- **WHEN** `DEEPSEEK_THINKING` is not set or is falsy
- **THEN** the client SHALL NOT send thinking-related parameters

#### Scenario: reasoning_content is passed through in Tool Loop rounds
- **WHEN** `DEEPSEEK_THINKING` is enabled and the upstream assistant message contains both `tool_calls` and `reasoning_content`
- **THEN** the full assistant message (including `reasoning_content`) SHALL be preserved for the next DeepSeek round
- **AND** after the Tool Loop completes, the final `reasoning_content` SHALL be discarded
- **AND** SHALL NOT appear in the stored browser history or the final reply

## MODIFIED Requirements

### Requirement: Student page is server-rendered
The existing requirement in `student-management-ui` spec is unchanged. The student page SHALL continue to render through Flask templates. The AI Chat panel SHALL be included via the shared `base.html` layout and SHALL NOT affect the student page's server-rendering contract.

#### Scenario: Student page still renders through Flask
- **WHEN** a browser requests `GET /students`
- **THEN** the system SHALL return an HTML page for student management
- **AND** the page SHALL still be rendered through Flask templates
- **AND** the AI Chat panel SHALL be added via the shared layout without changing the student page template structure

### Requirement: Dashboard uses the shared administration layout
The existing requirement in `student-management-ui` spec is unchanged. The Dashboard SHALL continue to use the shared layout. The AI Chat icon and panel SHALL be added to `base.html` and thus be available on both Dashboard and student pages.

#### Scenario: Dashboard still uses shared layout with AI Chat
- **WHEN** a browser requests `GET /`
- **THEN** the rendered page SHALL use the shared administration layout
- **AND** the AI Chat icon SHALL be rendered as part of the shared layout

### Requirement: Closed modal remains hidden
The existing requirement in `student-management-ui` spec is unchanged. The student modal SHALL remain visually independent. The AI Chat panel SHALL close automatically when the student modal opens, and SHALL NOT cause the student modal to open or close.

#### Scenario: AI Chat does not affect student modal state
- **WHEN** the student modal is closed
- **THEN** it SHALL remain hidden regardless of AI Chat panel state
- **WHEN** the student modal opens
- **THEN** the AI Chat panel SHALL close automatically
- **AND** the modal SHALL remain open regardless of any prior Chat Panel state
