## Why

The current V2 student management system already provides a complete Flask UI, REST API, and MCP student tools, but it lacks an AI-powered natural language interface. Adding an AI Chat assistant that connects DeepSeek with the existing MCP student tools will let users query, create, update, and delete student records through conversational Chinese, significantly improving usability for non-technical operators.

## What Changes

- Add a new AI Chat Service layer that orchestrates chat requests, tool call loops, write-operation confirmation tokens, and final user replies.
- Add a DeepSeek client module that sends OpenAI-compatible Chat Completions requests using httpx and environment-variable configuration only.
- Add an MCP Tool Adapter that discovers existing MCP tools via `mcp_client`, converts them to OpenAI-compatible function tools, and calls them during chat sessions with session reuse.
- Add an AI Action Confirmation module that creates short-lived signed confirmation tokens to gate all write operations.
- Add a new `POST /api/chat` route for sending messages and `POST /api/chat/actions/confirm` for confirming pending write operations.
- Add a floating AI Chat icon and panel to the shared `base.html` template, visible on both Dashboard and student management pages.
- Add `app/static/js/ai_chat.js` for client-side chat behavior (open/close, sessionStorage, message rendering, confirmation UI).
- Add `app/static/css/ai_chat.css` for AI Chat panel styling with an independent class prefix.
- Add a `_ai_chat.html` template fragment for the floating icon and panel HTML.
- Add test files for configuration, DeepSeek client, MCP adapter, AI Chat service, action confirmation, chat routes, and page rendering.
- Add a live smoke script `scripts/deepseek_chat_smoke.py` for optional real-API verification.
- Add new environment variables for DeepSeek and AI Chat configuration.
- Do **not** add SSE streaming, WebSocket, chat database persistence, user authentication, multi-user sessions, file uploads, image inputs, voice, web search, RAG, Excel I/O, HTTP MCP transport, or new frontend frameworks.

## Capabilities

### New Capabilities
- `ai-chat`: AI Chat assistant that connects DeepSeek with existing MCP student tools, supporting natural-language query, create, update, upsert, delete, and batch-delete operations with server-side confirmation for all writes.

### Modified Capabilities
- `student-management-ui`: The shared `base.html` layout will gain a floating AI Chat icon and panel. The interaction contract of existing student pages must remain unchanged.

## Impact

- **New code areas**: `app/services/ai_chat_service.py`, `app/services/deepseek_client.py`, `app/services/mcp_tool_adapter.py`, `app/services/ai_action_confirmation.py`, `app/routes/chat.py`, `app/templates/_ai_chat.html`, `app/static/js/ai_chat.js`, `app/static/css/ai_chat.css`, `scripts/deepseek_chat_smoke.py`, and new test files under `tests/`
- **Modified files**: `app/__init__.py` (register new blueprint), `app/config.py` (add AI config support), `app/templates/base.html` (include AI Chat fragment via `{% include %}` and load both CSS and JS), `.env.example` (add AI env vars), `pyproject.toml` (add `httpx` dependency), `requirements.txt` (add `httpx`)
- **API changes**: New endpoints `POST /api/chat` and `POST /api/chat/actions/confirm` with unified JSON response contract
- **Dependency impact**: Requires `httpx>=0.28` as direct production dependency. No `openai` Python SDK dependency. `itsdangerous` is already provided by Flask and does not need a separate declaration.
- **No schema changes**: No new database tables, no student table changes
