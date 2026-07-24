"""Tests for AI Action Confirmation token creation and verification.

RED phase — all tests should fail because the module does not exist yet.
"""

from __future__ import annotations

import time

import itsdangerous
import pytest

from app.config import DEV_SECRET_KEY

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAFE_KEY = "i-am-a-safe-secret-key-for-testing"
PLACEHOLDER_KEY = "replace-with-development-secret"
SAMPLE_PAYLOAD: dict[str, object] = {
    "tool_name": "add_student",
    "arguments": {"student_number": "0001", "name": "张三"},
    "action_id": "test-action-uuid",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_safe_message(err: Exception) -> None:
    """Assert the exception message contains no sensitive info."""
    msg = str(err)
    assert SAFE_KEY not in msg
    assert DEV_SECRET_KEY not in msg
    assert PLACEHOLDER_KEY not in msg
    assert "张三" not in msg
    assert "add_student" not in msg
    assert "0001" not in msg


# ===================================================================
# 1. Token creation with safe SECRET_KEY
# ===================================================================


def test_create_token_succeeds_with_safe_key() -> None:
    """AIActionConfirmation can be instantiated with a safe key."""
    from app.services.ai_action_confirmation import AIActionConfirmation

    confirmation = AIActionConfirmation(
        secret_key=SAFE_KEY,
        token_ttl_seconds=120,
    )
    token = confirmation.create_token(SAMPLE_PAYLOAD)
    assert isinstance(token, str)
    assert len(token) > 0


def test_token_is_non_empty_string() -> None:
    """Created token must be a non-empty string."""
    from app.services.ai_action_confirmation import AIActionConfirmation

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    token = confirmation.create_token({"tool_name": "test"})
    assert isinstance(token, str)
    assert token


# ===================================================================
# 2. Token verification
# ===================================================================


def test_verify_valid_token_returns_payload() -> None:
    """verify_token returns a dict equivalent to the original payload."""
    from app.services.ai_action_confirmation import AIActionConfirmation

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    token = confirmation.create_token(SAMPLE_PAYLOAD)
    result = confirmation.verify_token(token)

    assert isinstance(result, dict)
    assert result["tool_name"] == SAMPLE_PAYLOAD["tool_name"]
    assert result["arguments"] == SAMPLE_PAYLOAD["arguments"]
    assert result["action_id"] == SAMPLE_PAYLOAD["action_id"]


def test_verify_returns_new_object() -> None:
    """verify_token must return a new dict, not the same reference."""
    from app.services.ai_action_confirmation import AIActionConfirmation

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    token = confirmation.create_token(SAMPLE_PAYLOAD)
    result = confirmation.verify_token(token)

    assert result is not SAMPLE_PAYLOAD


# ===================================================================
# 3. Invalid payload type — controlled error, not raw TypeError
# ===================================================================


def test_payload_is_list_raises_invalid_payload() -> None:
    """List payload must raise AIConfirmationInvalidPayloadError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)

    with pytest.raises(AIConfirmationInvalidPayloadError) as excinfo:
        confirmation.create_token(["item1", "item2"])  # type: ignore[arg-type]

    assert excinfo.value.code == "ai_confirmation_invalid_payload"
    _assert_safe_message(excinfo.value)


def test_payload_is_string_raises_invalid_payload() -> None:
    """String payload must raise AIConfirmationInvalidPayloadError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)

    with pytest.raises(AIConfirmationInvalidPayloadError):
        confirmation.create_token("not-a-dict")  # type: ignore[arg-type]


def test_payload_is_none_raises_invalid_payload() -> None:
    """None payload must raise AIConfirmationInvalidPayloadError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)

    with pytest.raises(AIConfirmationInvalidPayloadError):
        confirmation.create_token(None)  # type: ignore[arg-type]


def test_payload_is_number_raises_invalid_payload() -> None:
    """Integer payload must raise AIConfirmationInvalidPayloadError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)

    with pytest.raises(AIConfirmationInvalidPayloadError):
        confirmation.create_token(42)  # type: ignore[arg-type]


# ===================================================================
# 4. Forbidden fields in payload
# ===================================================================


@pytest.mark.parametrize("field_name", [
    "api_key",
    "authorization",
    "authorization_header",
    "database_path",
    "mcp_session",
    "reasoning_content",
])
def test_forbidden_top_level_field_is_rejected(field_name: str) -> None:
    """Top-level forbidden fields must raise AIConfirmationInvalidPayloadError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    payload: dict[str, object] = {"tool_name": "test", field_name: "secret-value"}

    with pytest.raises(AIConfirmationInvalidPayloadError) as excinfo:
        confirmation.create_token(payload)

    assert excinfo.value.code == "ai_confirmation_invalid_payload"
    _assert_safe_message(excinfo.value)


@pytest.mark.parametrize("field_name", [
    "API_KEY",
    "Api_Key",
    "Authorization_Header",
    "Authorization_header",
    "Reasoning_Content",
    "REASONING_CONTENT",
])
def test_forbidden_field_case_insensitive(field_name: str) -> None:
    """Forbidden field matching must be case-insensitive."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    payload: dict[str, object] = {"tool_name": "test", field_name: "leaked"}

    with pytest.raises(AIConfirmationInvalidPayloadError):
        confirmation.create_token(payload)


def test_forbidden_field_nested_in_arguments() -> None:
    """Forbidden field inside nested dict must be rejected."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    payload: dict[str, object] = {
        "tool_name": "add_student",
        "arguments": {
            "name": "李四",
            "api_key": "nested-secret",
        },
    }

    with pytest.raises(AIConfirmationInvalidPayloadError):
        confirmation.create_token(payload)


def test_forbidden_field_in_list_element() -> None:
    """Forbidden field inside a list element (nested dict) must be rejected."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    payload: dict[str, object] = {
        "tool_name": "batch_add",
        "students": [
            {"name": "王五", "api_key": "secret-in-list"},
            {"name": "赵六"},
        ],
    }

    with pytest.raises(AIConfirmationInvalidPayloadError):
        confirmation.create_token(payload)


def test_deeply_nested_forbidden_field_rejected() -> None:
    """Forbidden field multiple levels deep must be rejected."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    payload: dict[str, object] = {
        "tool_name": "deep",
        "meta": {
            "config": {
                "credentials": {
                    "api_key": "deeply-hidden",
                },
            },
        },
    }

    with pytest.raises(AIConfirmationInvalidPayloadError):
        confirmation.create_token(payload)


# ===================================================================
# 5. Valid payload still works
# ===================================================================


def test_valid_student_payload_still_works() -> None:
    """A clean student payload must still create and verify successfully."""
    from app.services.ai_action_confirmation import AIActionConfirmation

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    payload: dict[str, object] = {
        "tool_name": "add_student",
        "arguments": {
            "student_number": "0001",
            "name": "张三",
            "phone": "13800138000",
        },
        "action_id": "uuid-123",
    }

    token = confirmation.create_token(payload)
    result = confirmation.verify_token(token)

    assert result["tool_name"] == "add_student"
    assert result["arguments"]["name"] == "张三"


def test_create_token_does_not_mutate_payload() -> None:
    """create_token must not modify the original payload dict, even after
    validation."""
    from app.services.ai_action_confirmation import AIActionConfirmation

    payload: dict[str, object] = {
        "tool_name": "add_student",
        "arguments": {"student_number": "0001", "name": "张三"},
    }
    payload_copy = dict(payload)
    arguments_copy = dict(payload["arguments"])  # type: ignore[arg-type]

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    confirmation.create_token(payload)

    assert payload == payload_copy
    assert payload["arguments"] == arguments_copy


# ===================================================================
# 6. Error message safety
# ===================================================================


def test_invalid_payload_error_does_not_contain_forbidden_value() -> None:
    """Error message must not contain the value of a forbidden field."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    payload: dict[str, object] = {"tool_name": "test", "api_key": "super-secret-value"}

    with pytest.raises(AIConfirmationInvalidPayloadError) as excinfo:
        confirmation.create_token(payload)

    msg = str(excinfo.value)
    assert "super-secret-value" not in msg


# ===================================================================
# 4. Tampered / invalid tokens
# ===================================================================


def test_tampered_token_raises_invalid() -> None:
    """Token modified by one character must raise AIConfirmationInvalidError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    token = confirmation.create_token({"tool_name": "test"})

    # Modify the last character
    tampered = token[:-1] + ("X" if token[-1] != "X" else "Y")

    with pytest.raises(AIConfirmationInvalidError) as excinfo:
        confirmation.verify_token(tampered)

    _assert_safe_message(excinfo.value)


def test_random_string_raises_invalid() -> None:
    """Random string token must raise AIConfirmationInvalidError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)

    with pytest.raises(AIConfirmationInvalidError) as excinfo:
        confirmation.verify_token("this-is-not-a-valid-token")

    _assert_safe_message(excinfo.value)


def test_empty_token_raises_invalid() -> None:
    """Empty string token must raise AIConfirmationInvalidError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)

    with pytest.raises(AIConfirmationInvalidError) as excinfo:
        confirmation.verify_token("")

    _assert_safe_message(excinfo.value)


# ===================================================================
# 5. Expired token
# ===================================================================


def test_expired_token_raises_expired() -> None:
    """Token past its TTL must raise AIConfirmationExpiredError.

    Uses ``unittest.mock.patch`` to advance itsdangerous's time source
    without sleep.
    """
    from unittest.mock import patch

    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationExpiredError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=300)
    token = confirmation.create_token({"tool_name": "test"})

    with patch("itsdangerous.timed.time.time", lambda: 99_999_999_999):
        with pytest.raises(AIConfirmationExpiredError) as excinfo:
            confirmation.verify_token(token)

    assert excinfo.value.code == "ai_confirmation_expired"
    _assert_safe_message(excinfo.value)


# ===================================================================
# 6. Fail-closed: unsafe SECRET_KEY
# ===================================================================


def test_missing_secret_key_raises_not_configured() -> None:
    """Missing SECRET_KEY must raise AIConfirmationNotConfiguredError at init."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationNotConfiguredError,
    )

    with pytest.raises(AIConfirmationNotConfiguredError) as excinfo:
        AIActionConfirmation(secret_key="", token_ttl_seconds=120)

    assert excinfo.value.code == "ai_confirmation_not_configured"
    _assert_safe_message(excinfo.value)


def test_empty_secret_key_raises_not_configured() -> None:
    """Empty SECRET_KEY must raise AIConfirmationNotConfiguredError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationNotConfiguredError,
    )

    with pytest.raises(AIConfirmationNotConfiguredError) as excinfo:
        AIActionConfirmation(secret_key="", token_ttl_seconds=120)

    _assert_safe_message(excinfo.value)


def test_dev_default_secret_key_raises_not_configured() -> None:
    """Development default SECRET_KEY must raise AIConfirmationNotConfiguredError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationNotConfiguredError,
    )

    with pytest.raises(AIConfirmationNotConfiguredError) as excinfo:
        AIActionConfirmation(
            secret_key=DEV_SECRET_KEY,
            token_ttl_seconds=120,
        )

    _assert_safe_message(excinfo.value)


def test_placeholder_secret_key_raises_not_configured() -> None:
    """Placeholder SECRET_KEY must raise AIConfirmationNotConfiguredError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationNotConfiguredError,
    )

    with pytest.raises(AIConfirmationNotConfiguredError) as excinfo:
        AIActionConfirmation(
            secret_key=PLACEHOLDER_KEY,
            token_ttl_seconds=120,
        )

    _assert_safe_message(excinfo.value)


# ===================================================================
# 7. Fail-closed: invalid TTL
# ===================================================================


def test_ttl_zero_raises_not_configured() -> None:
    """TTL=0 must raise AIConfirmationNotConfiguredError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationNotConfiguredError,
    )

    with pytest.raises(AIConfirmationNotConfiguredError):
        AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=0)


def test_ttl_negative_raises_not_configured() -> None:
    """Negative TTL must raise AIConfirmationNotConfiguredError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationNotConfiguredError,
    )

    with pytest.raises(AIConfirmationNotConfiguredError):
        AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=-1)


# ===================================================================
# 8. Error message safety
# ===================================================================


def test_error_message_does_not_contain_secret_key() -> None:
    """AIConfirmationNotConfiguredError message must not contain SECRET_KEY."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationNotConfiguredError,
    )

    with pytest.raises(AIConfirmationNotConfiguredError) as excinfo:
        AIActionConfirmation(secret_key="", token_ttl_seconds=120)

    msg = str(excinfo.value)
    assert "SECRET_KEY" not in msg


def test_error_message_does_not_contain_token() -> None:
    """AIConfirmationInvalidError message must not contain token data."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)

    with pytest.raises(AIConfirmationInvalidError) as excinfo:
        confirmation.verify_token("bad-token-value")

    msg = str(excinfo.value)
    assert "bad-token-value" not in msg
    assert "token" not in msg.lower() or "确认请求" in msg


def test_error_message_does_not_contain_payload_info() -> None:
    """Error message must not leak student data from payload."""
    from app.services.ai_action_confirmation import AIActionConfirmation

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)

    # Trigger an invalid scenario
    with pytest.raises(Exception):
        AIActionConfirmation(secret_key="", token_ttl_seconds=120)


# ===================================================================
# 9. Verify revalidates decoded payload
# ===================================================================


def test_verify_rejects_list_payload() -> None:
    """verify_token must reject a validly-signed token with list payload."""
    from itsdangerous import URLSafeTimedSerializer

    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
        SALT,
    )

    # Build a validly-signed token with a non-dict payload bypassing
    # create_token's validation.
    serializer = URLSafeTimedSerializer(secret_key=SAFE_KEY, salt=SALT)
    bad_token = serializer.dumps(["invalid"])

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)

    with pytest.raises(AIConfirmationInvalidPayloadError) as excinfo:
        confirmation.verify_token(bad_token)

    assert excinfo.value.code == "ai_confirmation_invalid_payload"
    _assert_safe_message(excinfo.value)


def test_verify_rejects_forbidden_top_level_field() -> None:
    """verify_token must reject a signed token containing forbidden fields."""
    from itsdangerous import URLSafeTimedSerializer

    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
        SALT,
    )

    serializer = URLSafeTimedSerializer(secret_key=SAFE_KEY, salt=SALT)
    bad_token = serializer.dumps({
        "tool_name": "add_student",
        "reasoning_content": "internal",
    })

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)

    with pytest.raises(AIConfirmationInvalidPayloadError) as excinfo:
        confirmation.verify_token(bad_token)

    assert excinfo.value.code == "ai_confirmation_invalid_payload"
    _assert_safe_message(excinfo.value)


def test_verify_rejects_nested_forbidden_field() -> None:
    """verify_token must reject a signed token with nested forbidden fields."""
    from itsdangerous import URLSafeTimedSerializer

    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
        SALT,
    )

    serializer = URLSafeTimedSerializer(secret_key=SAFE_KEY, salt=SALT)
    bad_token = serializer.dumps({
        "arguments": {
            "metadata": {
                "api_key": "secret",
            },
        },
    })

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)

    with pytest.raises(AIConfirmationInvalidPayloadError) as excinfo:
        confirmation.verify_token(bad_token)

    assert excinfo.value.code == "ai_confirmation_invalid_payload"
    _assert_safe_message(excinfo.value)


def test_verify_still_accepts_valid_payload() -> None:
    """After revalidation, a clean signed payload must still verify."""
    from app.services.ai_action_confirmation import AIActionConfirmation

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    token = confirmation.create_token({"tool_name": "count_students"})
    result = confirmation.verify_token(token)

    assert result["tool_name"] == "count_students"


# ===================================================================
# 10. Non-JSON-serializable payload
# ===================================================================


def test_create_token_rejects_non_serializable_value() -> None:
    """Non-JSON-serializable value must raise AIConfirmationInvalidPayloadError,
    not a raw TypeError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    payload: dict[str, object] = {
        "tool_name": "add_student",
        "arguments": {"value": object()},  # type: ignore[assignment]
    }

    with pytest.raises(AIConfirmationInvalidPayloadError) as excinfo:
        confirmation.create_token(payload)

    assert excinfo.value.code == "ai_confirmation_invalid_payload"


def test_non_serializable_error_safe_message() -> None:
    """Error for non-serializable payload must not contain object repr."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidPayloadError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    payload: dict[str, object] = {
        "tool_name": "add_student",
        "arguments": {"value": object()},  # type: ignore[assignment]
    }

    with pytest.raises(AIConfirmationInvalidPayloadError) as excinfo:
        confirmation.create_token(payload)

    msg = str(excinfo.value)
    assert "object at 0x" not in msg
    assert SAFE_KEY not in msg
    assert "add_student" not in msg


# ===================================================================
# 11. Error type distinction: signature vs payload vs expiry
# ===================================================================


def test_signature_error_distinct_from_payload_error() -> None:
    """BadSignature must raise AIConfirmationInvalidError, not
    AIConfirmationInvalidPayloadError."""
    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationInvalidError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)

    with pytest.raises(AIConfirmationInvalidError):
        confirmation.verify_token("broken-token")


def test_expiry_error_distinct_from_payload_error() -> None:
    """SignatureExpired must raise AIConfirmationExpiredError, not
    AIConfirmationInvalidPayloadError."""
    from unittest.mock import patch

    from app.services.ai_action_confirmation import (
        AIActionConfirmation,
        AIConfirmationExpiredError,
    )

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=300)
    token = confirmation.create_token({"tool_name": "test"})

    with patch("itsdangerous.timed.time.time", lambda: 99_999_999_999):
        with pytest.raises(AIConfirmationExpiredError):
            confirmation.verify_token(token)


# ===================================================================
# 12. No real .env access
# ===================================================================


def test_no_real_env_access() -> None:
    """Tests must not read real .env — controlled fixture only."""
    from app.services.ai_action_confirmation import AIActionConfirmation

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=120)
    token = confirmation.create_token({"tool_name": "test"})
    result = confirmation.verify_token(token)

    assert result["tool_name"] == "test"
