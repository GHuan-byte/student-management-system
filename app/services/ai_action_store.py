"""In-process AI guided action store.

Phase 1 uses an in-memory store keyed by ``action_id``. It is NOT a production
persistence layer: entries are lost on application restart and are not shared
across worker processes. See design.md D11/D12 for the documented limitations
and the future database-backed upgrade path. Redis/Celery and new database
tables are deliberately out of scope for this phase.

Security invariants enforced by the store:

- ``action_id`` is created server-side (unpredictable random value).
- Every entry is bound to the ``user_id`` that created it.
- ``get_for_user`` / ``safe_view`` / ``cancel`` refuse other users.
- ``safe_view`` never exposes the confirmation token or internal fields.
- ``begin_execution`` is atomic (CAS) so an ``action_id`` can only be executed
  once, and never after cancel, expiry, or completion.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from app.services.ai_action import (
    CONFIRMABLE_STATUSES,
    CANCELLED,
    EXECUTING,
    EXPIRED,
    FAILED,
    PENDING,
    SUCCEEDED,
    target_page_for,
)


class AIActionError(RuntimeError):
    """Base error for the in-process action store."""


class AIActionNotFoundError(AIActionError):
    """Raised when the action does not exist or is not owned by the caller."""


class AIActionNotExecutableError(AIActionError):
    """Raised when the action is not in a confirmable state."""


class AIActionExpiredError(AIActionError):
    """Raised when the action has exceeded its TTL."""


class AIActionStore:
    """Thread-safe in-memory store of guided actions."""

    __slots__ = ("_lock", "_actions")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._actions: dict[str, dict[str, Any]] = {}

    def create(
        self,
        *,
        action_id: str,
        action_type: str,
        tool_name: str,
        arguments: dict[str, Any],
        token: str,
        user_id: Any,
        created_at: float | None = None,
        expires_at: float | None = None,
        payload: dict[str, Any] | None = None,
        target: Any = None,
        requires_confirmation: bool = True,
    ) -> dict[str, Any]:
        """Create a new pending action bound to *user_id*."""
        now = time.time() if created_at is None else created_at
        entry: dict[str, Any] = {
            "action_id": action_id,
            "action_type": action_type,
            "tool_name": tool_name,
            "arguments": dict(arguments),
            "payload": dict(payload) if payload is not None else dict(arguments),
            "target": target,
            "target_page": target_page_for(action_type),
            "requires_confirmation": bool(requires_confirmation),
            "status": PENDING,
            "user_id": user_id,
            "confirmation_token": token,
            "created_at": now,
            "expires_at": expires_at,
            "result": None,
            "error": None,
        }
        with self._lock:
            self._actions[action_id] = entry
            return dict(entry)

    def get(self, action_id: str) -> dict[str, Any] | None:
        """Return a copy of the entry or None (no ownership check)."""
        with self._lock:
            entry = self._actions.get(action_id)
            return dict(entry) if entry else None

    def get_for_user(self, action_id: str, user_id: Any) -> dict[str, Any] | None:
        """Return a copy of the entry only when it belongs to *user_id*."""
        with self._lock:
            entry = self._actions.get(action_id)
            if entry is None or entry["user_id"] != user_id:
                return None
            return dict(entry)

    def safe_view(self, action_id: str, user_id: Any) -> dict[str, Any] | None:
        """Return browser-safe display data (never the token or internals)."""
        entry = self.get_for_user(action_id, user_id)
        if entry is None:
            return None
        return {
            "action_id": entry["action_id"],
            "action_type": entry["action_type"],
            "status": entry["status"],
            "requires_confirmation": entry["requires_confirmation"],
            "target_page": entry["target_page"],
            "target": entry["target"],
            "payload": dict(entry["payload"]),
            "created_at": entry["created_at"],
            "expires_at": entry["expires_at"],
        }

    def get_token(self, action_id: str) -> str | None:
        """Return the server-held token (server-side execution only)."""
        with self._lock:
            entry = self._actions.get(action_id)
            return entry["confirmation_token"] if entry else None

    def begin_execution(self, action_id: str, *, now: float | None = None) -> str:
        """Atomically move a confirmable action to ``executing``.

        Returns the server-held confirmation token. Raises an error when the
        action is missing, expired, or already executing/terminal, so an
        ``action_id`` can only be executed once.
        """
        current_time = time.time() if now is None else now
        with self._lock:
            entry = self._actions.get(action_id)
            if entry is None:
                raise AIActionNotFoundError()
            if entry["expires_at"] is not None and entry["expires_at"] <= current_time:
                entry["status"] = EXPIRED
                raise AIActionExpiredError()
            if entry["status"] not in CONFIRMABLE_STATUSES:
                raise AIActionNotExecutableError()
            entry["status"] = EXECUTING
            return entry["confirmation_token"]

    def mark_succeeded(self, action_id: str, result: Any) -> None:
        """Record a successful execution (only from ``executing``)."""
        with self._lock:
            entry = self._actions.get(action_id)
            if entry is not None and entry["status"] == EXECUTING:
                entry["status"] = SUCCEEDED
                entry["result"] = result

    def mark_failed(self, action_id: str, error_code: Any) -> None:
        """Record a failed execution (only from ``executing``)."""
        with self._lock:
            entry = self._actions.get(action_id)
            if entry is not None and entry["status"] == EXECUTING:
                entry["status"] = FAILED
                entry["error"] = error_code

    def cancel(self, action_id: str, user_id: Any) -> bool:
        """Cancel a confirmable action owned by *user_id*.

        Returns True when cancelled, False when already expired (not
        cancellable), and raises for missing/not-owned or executing/terminal
        actions.
        """
        with self._lock:
            entry = self._actions.get(action_id)
            if entry is None or entry["user_id"] != user_id:
                raise AIActionNotFoundError()
            if entry["status"] == EXPIRED:
                return False
            if entry["status"] not in CONFIRMABLE_STATUSES:
                raise AIActionNotExecutableError()
            entry["status"] = CANCELLED
            return True

    def expire_stale(self, *, now: float | None = None) -> int:
        """Mark confirmable entries past their TTL as expired. Returns count."""
        current_time = time.time() if now is None else now
        expired = 0
        with self._lock:
            for entry in self._actions.values():
                if (
                    entry["status"] in CONFIRMABLE_STATUSES
                    and entry["expires_at"] is not None
                    and entry["expires_at"] <= current_time
                ):
                    entry["status"] = EXPIRED
                    expired += 1
        return expired
