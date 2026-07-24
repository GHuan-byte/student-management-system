"""AIChatService — orchestrates DeepSeek and MCP tools for AI Chat.

Each ``chat()`` call:
1. Opens a request-level ``MCPToolAdapter`` context.
2. Discovers MCP tools and passes them to DeepSeek as OpenAI-compatible
   function schemas.
3. Enters a Tool Loop:
   a. Calls ``DeepSeekClient.create_chat_completion()`` with tools.
   b. If the response is plain text (no tool_calls), returns it.
   c. Checks the tool round count against ``max_tool_rounds``.
   d. Pre-scans for write tools — rejects the entire batch if found.
   e. Executes or safely handles each tool in the batch.
   f. Appends assistant + tool-result messages and loops.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from app.services.ai_errors import (
    AIToolRoundLimitError,
    AIWriteConfirmationRequiredError,
)

# ---------------------------------------------------------------------------
# Tool classification
# ---------------------------------------------------------------------------

WRITE_TOOL_NAMES: frozenset[str] = frozenset({
    "add_student",
    "update_student",
    "upsert_student",
    "delete_student",
    "batch_delete_students",
})

READ_TOOL_NAMES: frozenset[str] = frozenset({
    "list_students",
    "search_students",
    "get_student_by_id",
    "get_student_by_number",
    "count_students",
})

KNOWN_TOOL_NAMES: frozenset[str] = READ_TOOL_NAMES | WRITE_TOOL_NAMES


class AIChatService:
    """Orchestrates DeepSeek LLM calls with MCP student tool execution.

    Usage::

        service = AIChatService(
            deepseek_client_factory=lambda: DeepSeekClient(config),
            mcp_adapter_factory=lambda: MCPToolAdapter(database_path=...),
            max_tool_rounds=5,
        )
        result = await service.chat(messages)
    """

    def __init__(
        self,
        deepseek_client_factory: Callable[[], Any],
        mcp_adapter_factory: Callable[[], Any],
        *,
        max_tool_rounds: int = 5,
    ) -> None:
        self._deepseek_factory = deepseek_client_factory
        self._adapter_factory = mcp_adapter_factory
        self._max_tool_rounds = max_tool_rounds

    async def chat(
        self,
        messages: list[dict[str, object]],
    ) -> dict[str, object]:
        """Process a chat request through DeepSeek and optional MCP tools.

        Args:
            messages: Conversation history ending with a ``user`` message.

        Returns:
            A dict with ``success`` and ``reply`` keys.
        """
        deepseek = self._deepseek_factory()

        # A copy so we never mutate the caller's list.
        internal_messages = list(messages)

        async with self._adapter_factory() as adapter:
            await adapter.discover_tools()
            openai_tools = adapter.get_openai_tools()

            tool_rounds = 0

            while True:
                response = await deepseek.create_chat_completion(
                    internal_messages,
                    tools=openai_tools,
                )

                tool_calls = response.get("tool_calls")
                if not tool_calls:
                    # Plain text response — done
                    return self._text_result(response)

                # --- Round-limit check (before executing this batch) ---
                if tool_rounds >= self._max_tool_rounds:
                    raise AIToolRoundLimitError()

                tool_rounds += 1

                # --- Pre-scan: reject any write tool in this batch ---
                tool_names = [tc["function"]["name"] for tc in tool_calls]
                if any(name in WRITE_TOOL_NAMES for name in tool_names):
                    raise AIWriteConfirmationRequiredError()

                # --- Build the assistant message ---
                assistant_msg = self._build_assistant_message(response)
                internal_messages.append(assistant_msg)

                # --- Execute / handle each tool ---
                for tc in tool_calls:
                    tool_name = tc["function"]["name"]
                    arguments = tc["function"]["arguments"]
                    tool_call_id = tc["id"]

                    if tool_name not in KNOWN_TOOL_NAMES:
                        tool_result = {
                            "success": False,
                            "error": {
                                "code": "unknown_tool",
                                "message": "请求的工具不可用",
                            },
                        }
                    else:
                        tool_result = await adapter.invoke_tool(
                            tool_name, arguments,
                        )

                    result_msg = self._build_tool_result_message(
                        tool_call_id, tool_name, tool_result,
                    )
                    internal_messages.append(result_msg)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _text_result(response: dict[str, Any]) -> dict[str, object]:
        """Extract a safe text result from a DeepSeek response."""
        return {
            "success": True,
            "reply": response.get("content") or "",
        }

    @staticmethod
    def _build_assistant_message(response: dict[str, Any]) -> dict[str, object]:
        """Build the assistant message carrying tool_calls and reasoning."""
        msg: dict[str, object] = {
            "role": "assistant",
            "content": response.get("content"),
            "tool_calls": response["tool_calls"],
        }
        if "reasoning_content" in response:
            msg["reasoning_content"] = response["reasoning_content"]
        return msg

    @staticmethod
    def _build_tool_result_message(
        tool_call_id: str,
        tool_name: str,
        tool_result: dict[str, object],
    ) -> dict[str, object]:
        """Build a ``role=tool`` message from a sanitized adapter result."""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": json.dumps(tool_result, ensure_ascii=False),
        }
