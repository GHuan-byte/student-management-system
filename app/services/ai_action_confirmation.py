"""AI Action Confirmation — server-side signed token for write actions.

Uses ``itsdangerous.URLSafeTimedSerializer`` to create and verify
short-lived, tamper-proof tokens that gate MCP write operations.

.. warning::

    URLSafeTimedSerializer provides **integrity** and **signature**
    verification but **not** confidentiality.  Never embed secrets
    (API keys, auth headers, database paths, MCP sessions, or
    reasoning_content) in the token payload.
"""

from __future__ import annotations

from typing import Any

from itsdangerous import URLSafeTimedSerializer
from itsdangerous.exc import BadData, BadSignature, SignatureExpired

from app.config import _is_secret_key_safe
from app.services.ai_errors import (
    AIConfirmationExpiredError,
    AIConfirmationInvalidError,
    AIConfirmationInvalidPayloadError,
    AIConfirmationNotConfiguredError,
)

SALT = "ai-action-confirmation"

# ---------------------------------------------------------------------------
# Forbidden token fields
#
# URLSafeTimedSerializer signs the payload but does NOT encrypt it.
# These fields must never appear in the token.
# ---------------------------------------------------------------------------

FORBIDDEN_TOKEN_KEYS: frozenset[str] = frozenset({
    "api_key",
    "authorization",
    "authorization_header",
    "database_path",
    "mcp_session",
    "reasoning_content",
})


def _has_forbidden_keys(value: Any) -> bool:
    """Recursively check for forbidden keys in a JSON-like structure.

    Rules:
    - ``dict``: check each key (case-insensitive), then recurse into value.
    - ``list``/``tuple``: recurse into each element.
    - Other types: allowed (no sub-structure to inspect).

    Returns:
        True if any forbidden key is found.

    The function does **not** modify the input.
    """
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in FORBIDDEN_TOKEN_KEYS:
                return True
            if _has_forbidden_keys(v):
                return True
    elif isinstance(value, (list, tuple)):
        for item in value:
            if _has_forbidden_keys(item):
                return True
    return False


def _validate_payload(payload: Any) -> None:
    """Validate that *payload* is a dict and contains no forbidden keys.

    Raises:
        AIConfirmationInvalidPayloadError: If validation fails.
    """
    if not isinstance(payload, dict):
        raise AIConfirmationInvalidPayloadError()

    if _has_forbidden_keys(payload):
        raise AIConfirmationInvalidPayloadError()


class AIActionConfirmation:
    """Create and verify signed confirmation tokens for write actions.

    The constructor validates the signing key and TTL immediately
    (fail-closed).  Token payload is a plain ``dict`` containing at
    minimum ``tool_name``, ``arguments``, and a unique ``action_id``.
    """

    __slots__ = ("_serializer", "_token_ttl")

    def __init__(self, secret_key: str, token_ttl_seconds: int) -> None:
        self._validate_config(secret_key, token_ttl_seconds)
        self._serializer = URLSafeTimedSerializer(
            secret_key=secret_key,
            salt=SALT,
        )
        self._token_ttl = token_ttl_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_token(self, payload: dict[str, object]) -> str:
        """Create a signed token for the given payload.

        Args:
            payload: Must be a dict.  Not modified by this method.

        Returns:
            A URL-safe signed token string.

        Raises:
            AIConfirmationInvalidPayloadError: If *payload* is not a dict,
                contains forbidden fields, or is not JSON-serializable.
        """
        _validate_payload(payload)
        try:
            return self._serializer.dumps(payload)
        except (TypeError, ValueError):
            raise AIConfirmationInvalidPayloadError()

    def verify_token(self, token: str) -> dict[str, object]:
        """Verify and return the payload from a signed token.

        Args:
            token: The token string returned by ``create_token``.

        Returns:
            A new dict with the original payload data.

        Raises:
            AIConfirmationExpiredError: If the token has exceeded its TTL.
            AIConfirmationInvalidError: If the token is tampered, malformed,
                or otherwise invalid (signature error).
            AIConfirmationInvalidPayloadError: If the decoded payload is not a
                dict or contains forbidden fields.
        """
        try:
            result = self._serializer.loads(token, max_age=self._token_ttl)
            _validate_payload(result)
            return result
        except SignatureExpired:
            raise AIConfirmationExpiredError()
        except BadSignature:
            raise AIConfirmationInvalidError()
        except BadData:
            raise AIConfirmationInvalidError()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_config(secret_key: str, token_ttl_seconds: int) -> None:
        """Fail-closed: reject unsafe keys and non-positive TTL values.

        Raises:
            AIConfirmationNotConfiguredError: If config is unsafe.
        """
        if not _is_secret_key_safe(secret_key):
            raise AIConfirmationNotConfiguredError()
        if token_ttl_seconds <= 0:
            raise AIConfirmationNotConfiguredError()
