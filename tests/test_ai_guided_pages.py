"""Frontend and template tests for the guided AI student action (phase 1).

The project has no JavaScript test runner and browser automation is out of
scope, so the safety-critical frontend invariants are asserted directly against
the rendered template (data-ai-target presence/uniqueness) and against the JS
source (fixed selector mapping, no student REST writes, no submit dispatch, no
token in sessionStorage).
"""

from __future__ import annotations

import re

import pytest

from app import create_app

EXPECTED_AI_TARGETS = {
    "student-add-button",
    "student-search-input",
    "student-search-button",
    "student-form-modal",
    "student-cancel-button",
    "student-submit-button",
    "student-number-input",
    "student-name-input",
    "student-gender-input",
    "student-age-input",
    "student-major-input",
    "student-year-level-select",
    "student-score-input",
    "student-phone-input",
    "student-email-input",
}


def _authenticated_client(app, role: str = "admin"):
    client = app.test_client()
    service = app.extensions["user_service_factory"]()
    user = service.get_user_by_username(role) or service.create_user(
        f"page-{role}", "secret1", role,
    )
    with client.session_transaction() as session:
        session["user_id"] = user["id"]
        session["auth_version"] = user["auth_version"]
        session["csrf_token"] = "test-csrf-token"
    return client


def _app():
    return create_app("testing", load_env=False)


def _static_path(app, *parts: str) -> str:
    root = app.root_path
    return f"{root}/static/{'/'.join(parts)}"


# ---------------------------------------------------------------------------
# Template: data-ai-target presence and uniqueness
# ---------------------------------------------------------------------------


def test_students_page_exposes_all_expected_ai_targets():
    app = _app()
    html = _authenticated_client(app, "admin").get("/students").get_data(as_text=True)
    found = set(re.findall(r'data-ai-target="([^"]+)"', html))
    assert EXPECTED_AI_TARGETS.issubset(found)


def test_students_page_ai_targets_are_unique():
    app = _app()
    html = _authenticated_client(app, "admin").get("/students").get_data(as_text=True)
    targets = re.findall(r'data-ai-target="([^"]+)"', html)
    seen: set[str] = set()
    for target in targets:
        assert target not in seen, f"duplicate data-ai-target: {target}"
        seen.add(target)


def test_students_page_does_not_use_fragile_selectors_for_ai():
    app = _app()
    html = _authenticated_client(app, "admin").get("/students").get_data(as_text=True)
    assert "nth-child" not in html


def test_runner_css_is_loaded_once_on_students_page():
    app = _app()
    html = _authenticated_client(app, "admin").get("/students").get_data(as_text=True)
    assert html.count("css/ai_action_runner.css") == 1
    assert html.count("js/ai_action_runner.js") == 1


# ---------------------------------------------------------------------------
# Runner source safety invariants
# ---------------------------------------------------------------------------


def test_runner_uses_only_fixed_data_ai_target_selectors():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    assert 'data-ai-target="student-add-button"' in js
    assert 'data-ai-target="student-form-modal"' in js
    assert 'data-ai-target="student-number-input"' in js
    assert 'data-ai-target="student-year-level-select"' in js
    assert "nth-child" not in js
    assert "AI_TARGETS" in js


def test_runner_never_calls_student_rest_write_api():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    assert "/api/students" not in js
    assert "/api/chat/actions/" in js


def test_runner_never_executes_code_or_submits_forms():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    assert "eval(" not in js
    assert "new Function" not in js
    assert "form.submit()" not in js
    assert ".submit(" not in js
    assert 'new Event("submit"' not in js
    assert "innerHTML" not in js
    assert "localStorage" not in js


def test_runner_never_dispatches_click_on_submit_button():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    # The submit button must only receive a visual press effect, never .click().
    assert "showVisualClick(submitButton)" in js
    assert "submitButton.click(" not in js


def test_runner_safe_abort_on_missing_target_without_write():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    assert "throw new Error(\"目标元素不存在\")" in js
    assert "waitForElement(AI_TARGETS.submitButton)" in js


def test_runner_fills_fields_with_standard_events():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    assert 'new Event("input", { bubbles: true })' in js
    assert 'new Event("change", { bubbles: true })' in js


def test_runner_confirmation_token_never_enters_session_storage():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    assert "confirmation_token" not in js
    assert "GUIDED_ACTION_KEY" in js
    assert 'action_id: action.action_id' in js
    assert 'action_type: action.action_type' in js


def test_runner_uses_guided_mode_guard():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    assert 'dataset.aiGuidedAction = "true"' in js


def test_runner_has_central_animation_timing():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    assert "AI_ACTION_TIMING" in js
    assert "Object.freeze({" in js
    for key in ("cursorMoveMs", "clickEffectMs", "modalOpenPauseMs", "characterDelayMs",
                "selectPauseMs", "fieldPauseMs", "beforeConfirmationMs", "successEffectMs"):
        assert key in js


def test_runner_timing_thresholds_are_slow_enough():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()

    def value(key: str) -> int:
        match = re.search(rf"{key}:\s*(\d+)", js)
        return int(match.group(1)) if match else 0

    assert value("characterDelayMs") >= 100
    assert value("fieldPauseMs") >= 400
    assert value("cursorMoveMs") >= 500
    assert value("selectPauseMs") >= 400


def test_runner_types_character_by_character():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    assert "for (const character of stringValue)" in js
    assert "element.value += character" in js
    assert "characterDelayMs" in js
    assert 'new Event("input", { bubbles: true })' in js
    assert 'new Event("change", { bubbles: true })' in js


def test_runner_success_closes_modal_via_page_ui():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    assert "window.StudentPageUI.closeModal()" in js
    assert "window.StudentPageUI.loadStudents()" in js
    assert "window.StudentPageUI.highlightStudentRow(student.id)" in js
    assert "finishSuccess" in js
    assert "form.submit()" not in js
    assert "requestSubmit" not in js


def test_runner_failure_keeps_modal_open():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    assert "showFailure" in js
    assert "waitForDismiss" in js
    assert "closeStudentModal" in js
    # The failure branch reports the real server error and only closes the
    # modal after the user dismisses the failure state — never on failure.
    assert "this.notifyFinished(false, message);" in js
    assert "this.showFailure(message);" in js
    assert "await this.waitForDismiss();" in js
    assert "添加失败" in js


# ---------------------------------------------------------------------------
# 4.12 Refresh recovery / manual interference / network failure / DOM loss
# (static + template assertions this round; runtime DOM tests deferred)
# ---------------------------------------------------------------------------


def test_refresh_recovery_saves_minimal_ref_and_navigates():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    # If the runner starts outside /students it persists only the minimal
    # reference (action_id + action_type) and navigates; on /students it
    # re-fetches the safe action data by action_id.
    assert 'window.location.pathname !== "/students"' in js
    assert 'window.location.assign("/students")' in js
    assert "saveMinimalRef(action)" in js
    assert "fetchSafeAction" in js


def test_refresh_recovery_revalidates_action_type_whitelist():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    # After a refresh the persisted reference is re-validated against the local
    # whitelist; unknown or absent action types are discarded.
    assert "GUIDED_ACTION_TYPES.indexOf(parsed.action_type) === -1" in js
    assert "return null" in js
    # Only the minimal reference (never a token) is ever persisted.
    assert "confirmation_token" not in js
    assert "action_id: parsed.action_id" in js


def test_refresh_recovery_refetches_safe_action_by_id():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    # The client re-reads the action state via the safe GET endpoint, never by
    # replaying an embedded token or re-running the animation from scratch.
    assert "fetchSafeAction" in js
    assert "/api/chat/actions/" in js
    assert 'headers: { "Accept": "application/json" }' in js


def test_manual_interference_preview_locks_fields_during_guide():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    # Guided filling locks text inputs (readOnly) and selects (disabled) so the
    # user cannot drift the form state mid-animation.
    assert "element.readOnly = true" in js
    assert "element.disabled = true" in js
    # exitGuidedMode restores both locks.
    assert "element.readOnly = false" in js
    assert "element.disabled = false" in js


def test_network_failure_single_confirm_write_no_auto_retry():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    # The confirm write is issued by exactly one code path (no retry loop, no
    # duplicated executor) and only after the user confirms.
    assert js.count("/confirm") == 1
    assert "callExecutor" in js
    assert 'method: "POST"' in js
    # On failure the real server error is surfaced; the server-side cancel is
    # best-effort and never blocks the client.
    assert "this.notifyFinished(false, message);" in js
    assert "this.showFailure(message);" in js
    assert "await this.waitForDismiss();" in js
    assert "best-effort server-side cancel" in js


def test_call_executor_success_returns_explicit_success_flag():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    # The confirm endpoint uses the unified envelope {success, data, ...}; the
    # inner data object (action_id/status/reply/action_result) has no `success`
    # key. The executor must merge an explicit success flag so runCreateStudent
    # does not treat a real server success as a failure (regression: data was
    # written but the UI reported "添加失败").
    assert "Object.assign({ success: true }, payload.data || {})" in js
    assert "if (!response.ok || !payload.success)" in js
    assert 'return { success: false, message: (payload && payload.message) || "添加失败" };' in js


def test_dom_loss_aborts_every_key_target_without_write():
    app = _app()
    js = open(_static_path(app, "js", "ai_action_runner.js"), encoding="utf-8").read()
    # Every key step (add button, each field, submit) aborts with the same
    # "目标元素不存在" message when its target is missing, and never reaches
    # the confirm executor.
    assert "WAIT_TIMEOUT_MS" in js
    assert js.count('throw new Error("目标元素不存在")') >= 3
    # The modal has its own distinct failure message and still aborts.
    assert "新增学生弹窗未成功打开" in js
    # waitForElement returns null on timeout; the caller aborts.
    assert "return null;" in js
    # The abort happens before the confirm write path.
    assert js.find("目标元素不存在") < js.find("callExecutor")


# ---------------------------------------------------------------------------
# students.js guided-mode guard and result integration
# ---------------------------------------------------------------------------


def test_students_js_blocks_form_submit_during_guided_mode():
    app = _app()
    js = open(_static_path(app, "js", "students.js"), encoding="utf-8").read()
    assert 'dataset.aiGuidedAction === "true"' in js
    assert "StudentPageUI" in js
    assert "closeModal" in js
    assert "ai-guide-row-highlight" in js


def test_students_js_keeps_manual_crud_path():
    app = _app()
    js = open(_static_path(app, "js", "students.js"), encoding="utf-8").read()
    assert 'fetch(`/api/students' in js or '"/api/students' in js
    assert 'data-open-create-modal' in js


# ---------------------------------------------------------------------------
# ai_chat.js guided trigger
# ---------------------------------------------------------------------------


def test_ai_chat_js_triggers_guided_flow_without_touching_legacy_confirm():
    app = _app()
    js = open(_static_path(app, "js", "ai_chat.js"), encoding="utf-8").read()
    # Existing legacy confirm contract is preserved.
    assert 'fetch("/api/chat/actions/confirm"' in js
    assert "confirmation_token: pendingAction.confirmationToken" in js
    # New guided trigger keeps only action_id/action_type in sessionStorage.
    assert "startGuidedAction" in js
    assert "GUIDED_ACTION_KEY" in js
    assert 'action_type: action.action_type' in js
    assert "ai-guided-action-finished" in js
    assert "innerHTML" not in js
    assert "localStorage" not in js
