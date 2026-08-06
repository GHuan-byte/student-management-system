"""Structured AI guided action model — action types, statuses, and mappings.

Phase 1 implements only the ``create_student`` guided action end-to-end. The
full action-type set is defined here so later phases (search / update / delete)
reuse the same model and animation framework instead of writing parallel
architectures.

The ``target_page`` for every student action is a fixed server-side mapping and
is NEVER taken from model output. The browser only ever receives semantic field
names; DOM selectors are maintained exclusively in the frontend.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Action types (whitelist)
# ---------------------------------------------------------------------------

CREATE_STUDENT = "create_student"
UPDATE_STUDENT = "update_student"
DELETE_STUDENT = "delete_student"
SEARCH_STUDENTS = "search_students"
GET_STUDENT = "get_student"
COUNT_STUDENTS = "count_students"

ACTION_TYPES: frozenset[str] = frozenset({
    CREATE_STUDENT,
    UPDATE_STUDENT,
    DELETE_STUDENT,
    SEARCH_STUDENTS,
    GET_STUDENT,
    COUNT_STUDENTS,
})

# Write actions always require explicit user confirmation before execution.
WRITE_ACTION_TYPES: frozenset[str] = frozenset({
    CREATE_STUDENT,
    UPDATE_STUDENT,
    DELETE_STUDENT,
})

READ_ACTION_TYPES: frozenset[str] = ACTION_TYPES - WRITE_ACTION_TYPES

# Mapping from MCP tool name to the structured action type.
ACTION_TYPE_BY_TOOL: dict[str, str] = {
    "add_student": CREATE_STUDENT,
    "update_student": UPDATE_STUDENT,
    "upsert_student": CREATE_STUDENT,  # resolves to create or update at execution
    "delete_student": DELETE_STUDENT,
    "batch_delete_students": DELETE_STUDENT,
    "search_students": SEARCH_STUDENTS,
    "get_student_by_id": GET_STUDENT,
    "get_student_by_number": GET_STUDENT,
    "count_students": COUNT_STUDENTS,
    "list_students": SEARCH_STUDENTS,
}

DEFAULT_TARGET_PAGE = "/students"

# Fixed server-side mapping: every approved student action plays on /students.
TARGET_PAGE_BY_ACTION_TYPE: dict[str, str] = {
    action_type: DEFAULT_TARGET_PAGE for action_type in ACTION_TYPES
}

# Student payload fields allowed to reach the browser for the animation preview.
STUDENT_PAYLOAD_FIELDS: frozenset[str] = frozenset({
    "student_number",
    "name",
    "gender",
    "age",
    "major",
    "year_level",
    "score",
    "phone",
    "email",
})

# ---------------------------------------------------------------------------
# Action status lifecycle
# ---------------------------------------------------------------------------

PENDING = "pending"
ANIMATING = "animating"
WAITING_CONFIRMATION = "waiting_confirmation"
EXECUTING = "executing"
SUCCEEDED = "succeeded"
FAILED = "failed"
CANCELLED = "cancelled"
EXPIRED = "expired"

ACTION_STATUSES: frozenset[str] = frozenset({
    PENDING,
    ANIMATING,
    WAITING_CONFIRMATION,
    EXECUTING,
    SUCCEEDED,
    FAILED,
    CANCELLED,
    EXPIRED,
})

# Confirmable states: the action has not been executed and can still be
# confirmed. ``animating`` is a frontend presentation state; it never gates
# execution on its own.
CONFIRMABLE_STATUSES: frozenset[str] = frozenset({
    PENDING,
    ANIMATING,
    WAITING_CONFIRMATION,
})

TERMINAL_STATUSES: frozenset[str] = frozenset({
    SUCCEEDED,
    FAILED,
    CANCELLED,
    EXPIRED,
})


def is_action_type(value: Any) -> bool:
    """Return True when *value* is an approved action type."""
    return isinstance(value, str) and value in ACTION_TYPES


def is_write_action(action_type: Any) -> bool:
    """Return True when *action_type* requires user confirmation."""
    return isinstance(action_type, str) and action_type in WRITE_ACTION_TYPES


def target_page_for(action_type: Any) -> str:
    """Return the fixed target page for *action_type* (never model-supplied)."""
    if not isinstance(action_type, str):
        return DEFAULT_TARGET_PAGE
    return TARGET_PAGE_BY_ACTION_TYPE.get(action_type, DEFAULT_TARGET_PAGE)


def filter_student_payload(payload: Any) -> dict[str, Any]:
    """Keep only approved semantic student fields from raw tool arguments.

    Any selector, script, SQL, or URL-like key is dropped because the allowed
    field set is fixed. Unknown fields never reach the browser action JSON.
    """
    if not isinstance(payload, dict):
        return {}
    return {
        key: value
        for key, value in payload.items()
        if isinstance(key, str) and key in STUDENT_PAYLOAD_FIELDS
    }
