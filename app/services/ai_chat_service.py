"""AIChatService — orchestrates DeepSeek and MCP tools for AI Chat.

Each ``chat()`` call:
1. Opens a request-level ``MCPToolAdapter`` context.
2. Discovers MCP tools and passes them to DeepSeek as OpenAI-compatible
   function schemas.
3. Enters a Tool Loop:
   a. Calls ``DeepSeekClient.create_chat_completion()`` with tools.
   b. If the response is plain text (no tool_calls), returns it.
   c. Checks the tool round count against ``max_tool_rounds``.
   d. Counts write tools in the batch:
      - 0 writes → execute read/unknown tools and continue loop
      - 1 write → generate Pending Action with signed token
      - 2+ writes → raise ``AIMultipleWriteActionsError``
   e. Appends assistant + tool-result messages and loops.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from app.services.ai_errors import (
    AIConfirmationInvalidPayloadError,
    AIConfirmationNotConfiguredError,
    AIMultipleWriteActionsError,
    AIToolRoundLimitError,
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

# ---------------------------------------------------------------------------
# Summary mapping
# ---------------------------------------------------------------------------

TOOL_SUMMARIES: dict[str, str] = {
    "add_student": "新增学生",
    "update_student": "修改学生",
    "upsert_student": "新增或修改学生",
    "delete_student": "删除学生",
    "batch_delete_students": "批量删除学生",
}


class AIChatService:
    """Orchestrates DeepSeek LLM calls with MCP student tool execution.

    Usage::

        service = AIChatService(
            deepseek_client_factory=lambda: DeepSeekClient(config),
            mcp_adapter_factory=lambda: MCPToolAdapter(database_path=...),
            action_confirmation=AIActionConfirmation(...),
            action_id_factory=uuid.uuid4,
            max_tool_rounds=5,
        )
        result = await service.chat(messages)
    """

    def __init__(
        self,
        deepseek_client_factory: Callable[[], Any],
        mcp_adapter_factory: Callable[[], Any],
        *,
        action_confirmation: Any | None = None,
        action_id_factory: Callable[[], str] | None = None,
        max_tool_rounds: int = 5,
    ) -> None:
        self._deepseek_factory = deepseek_client_factory
        self._adapter_factory = mcp_adapter_factory
        self._action_confirmation = action_confirmation
        self._action_id_factory = action_id_factory or (lambda: uuid.uuid4().hex)
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
                    return self._text_result(response)

                # --- Round-limit check ---
                if tool_rounds >= self._max_tool_rounds:
                    raise AIToolRoundLimitError()

                tool_rounds += 1

                # --- Count write tools ---
                write_calls = [
                    tc for tc in tool_calls
                    if tc["function"]["name"] in WRITE_TOOL_NAMES
                ]

                if len(write_calls) > 1:
                    raise AIMultipleWriteActionsError()

                if len(write_calls) == 1:
                    return self._build_pending_action(write_calls[0])

                # --- No write tools — execute read/unknown and loop ---
                assistant_msg = self._build_assistant_message(response)
                internal_messages.append(assistant_msg)

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

    async def confirm_action(
        self,
        confirmation_token: str,
    ) -> dict[str, object]:
        """Consume a confirmation token and execute the confirmed write tool.

        Args:
            confirmation_token: A signed token previously returned by
                ``_build_pending_action``.

        Returns:
            A dict with ``success`` and ``reply``.  The result structure
            is safe for returning to the browser via a Flask route.

        Raises:
            AIConfirmationNotConfiguredError: If ``action_confirmation``
                is ``None``.
            AIConfirmationExpiredError: If the token has exceeded its TTL.
            AIConfirmationInvalidError: If the token is tampered or malformed.
            AIConfirmationInvalidPayloadError: If the token payload is
                structurally invalid or the tool is not a write tool.
            AIConfirmationReplayError: If the token has already been consumed.
        """
        if self._action_confirmation is None:
            raise AIConfirmationNotConfiguredError()

        # Step 1: consume the token (atomic verify + mark consumed)
        payload = self._action_confirmation.consume_token(confirmation_token)

        # Step 2: validate payload fields for write execution
        tool_name = payload.get("tool_name")
        arguments = payload.get("arguments")
        action_id = payload.get("action_id")

        self._validate_confirmed_write_payload(
            tool_name=tool_name,
            arguments=arguments,
            action_id=action_id,
        )

        # Step 3: execute the write tool via MCP
        async with self._adapter_factory() as adapter:
            await adapter.discover_tools()
            result = await adapter.invoke_tool(tool_name, arguments)

        # Step 4: build safe response
        return self._build_confirmed_action_result(result, tool_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_confirmed_write_payload(
        *,
        tool_name: Any,
        arguments: Any,
        action_id: Any,
    ) -> None:
        """Validate that the consumed token payload is safe to execute.

        Checks:
        - ``tool_name`` is a non-empty string in ``WRITE_TOOL_NAMES``.
        - ``arguments`` is a dict.
        - ``action_id`` is a non-empty string.

        Raises:
            AIConfirmationInvalidPayloadError: If any check fails.
        """
        if not isinstance(tool_name, str) or not tool_name:
            raise AIConfirmationInvalidPayloadError()
        if tool_name not in WRITE_TOOL_NAMES:
            raise AIConfirmationInvalidPayloadError()
        if not isinstance(arguments, dict):
            raise AIConfirmationInvalidPayloadError()
        if not isinstance(action_id, str) or not action_id.strip():
            raise AIConfirmationInvalidPayloadError()

    @staticmethod
    def _build_confirmed_action_result(
        result: dict[str, object],
        tool_name: str,
    ) -> dict[str, object]:
        """Build a safe response from the MCP invoke_tool result.

        The response contains a deterministic Chinese reply and the
        sanitized result data, without raw MCP debug fields.
        """
        summary = TOOL_SUMMARIES.get(tool_name, tool_name)
        success = result.get("success", False)
        action_result: dict[str, object] = {
            "success": success,
        }
        if success and "data" in result:
            action_result["data"] = result["data"]

        return {
            "success": True,
            "reply": f"{summary}成功。",
            "requires_confirmation": False,
            "pending_action": None,
            "action_result": action_result,
        }

    def _build_pending_action(
        self,
        tool_call: dict[str, Any],
    ) -> dict[str, object]:
        """Build a Pending Action response for a single write tool.

        Creates a signed confirmation token and returns the pending-action
        structure without executing any MCP tool.
        """
        tool_name = tool_call["function"]["name"]
        arguments_raw = tool_call["function"]["arguments"]

        # Parse arguments to a dict for the token payload
        try:
            if isinstance(arguments_raw, str):
                arguments = json.loads(arguments_raw)
            else:
                arguments = arguments_raw
        except (json.JSONDecodeError, TypeError):
            return {
                "success": False,
                "reply": "工具参数格式无效",
            }

        # Non-dict arguments are invalid — reject without creating a token
        if not isinstance(arguments, dict):
            return {
                "success": False,
                "reply": "工具参数格式无效",
            }

        action_id = self._action_id_factory()

        # Build token payload
        payload: dict[str, object] = {
            "tool_name": tool_name,
            "arguments": arguments,
            "action_id": action_id,
        }

        confirmation_token = ""
        if self._action_confirmation is not None:
            confirmation_token = self._action_confirmation.create_token(payload)

        summary = TOOL_SUMMARIES.get(tool_name, tool_name)
        safe_arguments = json.dumps(arguments, ensure_ascii=False)

        return {
            "success": True,
            "reply": f"需要确认后才能执行：{summary}",
            "requires_confirmation": True,
            "confirmation_token": confirmation_token,
            "pending_action": {
                "summary": summary,
                "safe_arguments": safe_arguments,
            },
        }

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
