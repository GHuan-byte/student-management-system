"""DeepSeek HTTP client using httpx.AsyncClient."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import ALLOWED_REASONING_EFFORTS
from app.services.ai_errors import (
    AIAuthError,
    AIInvalidResponseError,
    AINotConfiguredError,
    AIRateLimitedError,
    AITimeoutError,
    AIUpstreamError,
)

CHAT_COMPLETIONS_PATH = "/chat/completions"


class DeepSeekClient:
    """Async HTTP client for OpenAI-compatible Chat Completions.

    Reads configuration from a dict (typically the Flask app config mapping
    produced by ``Config.to_mapping()``).

    Accepts an optional ``httpx.AsyncBaseTransport`` (e.g.
    ``httpx.MockTransport``) for dependency injection and test isolation.
    """

    def __init__(
        self,
        config: dict[str, Any],
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key: str | None = config.get("DEEPSEEK_API_KEY")
        self._api_base: str = self._normalize_api_base(
            config.get("DEEPSEEK_API_BASE") or ""
        )
        self._model: str = config.get("DEEPSEEK_MODEL") or ""
        self._max_tokens: int | None = config.get("DEEPSEEK_MAX_OUTPUT_TOKENS")
        self._thinking_enabled: bool = bool(config.get("DEEPSEEK_THINKING", False))
        self._reasoning_effort: str | None = config.get("DEEPSEEK_REASONING_EFFORT")
        self._timeout: float = float(
            config.get("DEEPSEEK_TIMEOUT_SECONDS") or 30
        )
        trust_env: bool = bool(config.get("DEEPSEEK_TRUST_ENV", False))

        client_kwargs: dict[str, Any] = {
            "timeout": httpx.Timeout(self._timeout),
            "trust_env": trust_env,
        }
        if transport is not None:
            client_kwargs["transport"] = transport

        self._client = httpx.AsyncClient(**client_kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        tools: list[dict[str, object]] | None = None,
    ) -> dict[str, Any]:
        """Send a Chat Completions request and return the assistant response.

        Args:
            messages: Conversation messages.
            tools: Optional OpenAI-compatible tool schemas (e.g. from
                ``MCPToolAdapter.get_openai_tools()``).  Passed as-is
                in the ``tools`` field of the request body.  The caller's
                list is not modified.

        Returns:
            A dict with ``content`` (assistant text, or ``None`` when the
            response carries ``tool_calls``).  When the upstream returns
            ``tool_calls`` they are included as a list under the ``tool_calls``
            key, preserving the original structure (``id``, ``type``,
            ``function.name``, ``function.arguments`` as a JSON string).

        Raises:
            AINotConfiguredError: When thinking is enabled but
                ``reasoning_effort`` is missing or not in the allowed set
                (``high``, ``max``).
            AITimeoutError: When the upstream request times out
                (``httpx.ReadTimeout``, ``httpx.ConnectTimeout``).
            AIAuthError: When the upstream returns 401 or 403.
            AIRateLimitedError: When the upstream returns 429.
            AIInvalidResponseError: When the upstream response is not valid
                Chat Completions JSON (malformed JSON, missing ``choices``,
                missing ``message``, or missing both ``content`` and
                ``tool_calls``).
            AIUpstreamError: When a transport-level error occurs
                (``httpx.ConnectError``, ``httpx.ProxyError``, etc.)
                or the upstream returns a 5xx status.
        """
        payload = self._build_payload(messages, tools=tools)
        url = f"{self._api_base}{CHAT_COMPLETIONS_PATH}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = await self._client.post(
                url, json=payload, headers=headers
            )
        except httpx.TimeoutException as exc:
            raise AITimeoutError() from exc
        except httpx.RequestError as exc:
            raise AIUpstreamError() from exc

        self._raise_for_upstream_status(response)
        return self._parse_response(response)

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> DeepSeekClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, object]] | None = None,
    ) -> dict[str, Any]:
        """Construct the request JSON body, including thinking params if enabled."""
        if self._thinking_enabled:
            self._validate_reasoning_effort()

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if tools is not None:
            payload["tools"] = tools
        if self._max_tokens is not None:
            payload["max_tokens"] = self._max_tokens
        if self._thinking_enabled:
            payload["thinking"] = {"type": "enabled"}
            if self._reasoning_effort:
                payload["reasoning_effort"] = self._reasoning_effort
        else:
            payload["thinking"] = {"type": "disabled"}
        return payload

    def _validate_reasoning_effort(self) -> None:
        """Raise if reasoning_effort is missing or not in the allowed set."""
        if not self._reasoning_effort or self._reasoning_effort not in ALLOWED_REASONING_EFFORTS:
            raise AINotConfiguredError()

    @staticmethod
    def _normalize_api_base(base: str) -> str:
        """Strip trailing slash so joining with ``/chat/completions`` works."""
        return base.rstrip("/")

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict[str, Any]:
        """Parse and validate the Chat Completions JSON response.

        Returns a dict with ``content`` and optionally ``tool_calls``.

        Raises:
            AIInvalidResponseError: When the response body does not conform
                to the expected Chat Completions structure.
        """
        try:
            data = response.json()
        except (ValueError, TypeError) as exc:
            raise AIInvalidResponseError() from exc

        if not isinstance(data, dict):
            raise AIInvalidResponseError()

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AIInvalidResponseError()

        choice = choices[0]
        if not isinstance(choice, dict):
            raise AIInvalidResponseError()

        message = choice.get("message")
        if not isinstance(message, dict):
            raise AIInvalidResponseError()

        result: dict[str, Any] = {}

        if "reasoning_content" in message:
            result["reasoning_content"] = message["reasoning_content"]

        if "tool_calls" in message:
            result["content"] = message.get("content")
            result["tool_calls"] = message["tool_calls"]
            return result

        if "content" in message:
            result["content"] = message["content"]
            return result

        raise AIInvalidResponseError()

    @staticmethod
    def _raise_for_upstream_status(response: httpx.Response) -> None:
        """Map upstream HTTP status codes to application errors.

        Only 401, 403, 429, and 5xx are mapped.  Other 4xx statuses fall
        through to ``response.raise_for_status()``.
        """
        status = response.status_code
        if status in (401, 403):
            raise AIAuthError()
        if status == 429:
            raise AIRateLimitedError()
        if 500 <= status <= 599:
            raise AIUpstreamError()
        response.raise_for_status()

    def __repr__(self) -> str:
        return f"<DeepSeekClient model={self._model!r}>"
