"""DeepSeek HTTP client using httpx.AsyncClient."""

from __future__ import annotations

from typing import Any

import httpx

from app.services.ai_errors import AITimeoutError, AIUpstreamError

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
    ) -> dict[str, Any]:
        """Send a Chat Completions request and return the assistant response.

        Returns a dict with ``content`` (assistant text, or ``None`` when the
        response carries ``tool_calls``).  When the upstream returns
        ``tool_calls`` they are included as a list under the ``tool_calls``
        key, preserving the original structure (``id``, ``type``,
        ``function.name``, ``function.arguments`` as a JSON string).

        Raises:
            AITimeoutError: When the upstream request times out
                (``httpx.ReadTimeout``, ``httpx.ConnectTimeout``).
            AIUpstreamError: When a transport-level error occurs
                (``httpx.ConnectError``, ``httpx.ProxyError``, etc.).
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if self._max_tokens is not None:
            payload["max_tokens"] = self._max_tokens

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

        response.raise_for_status()
        data: dict[str, Any] = response.json()

        choice = data["choices"][0]
        message = choice["message"]
        result: dict[str, Any] = {"content": message.get("content")}
        if "tool_calls" in message:
            result["tool_calls"] = message["tool_calls"]
        return result

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

    @staticmethod
    def _normalize_api_base(base: str) -> str:
        """Strip trailing slash so joining with ``/chat/completions`` works."""
        return base.rstrip("/")

    def __repr__(self) -> str:
        return f"<DeepSeekClient model={self._model!r}>"
