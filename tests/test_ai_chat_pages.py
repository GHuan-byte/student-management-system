"""Server-rendered AI Chat page-integration checks."""
from collections import Counter
import re

import pytest

from app import create_app


def _authenticated_client(app):
    client = app.test_client()
    service = app.extensions["user_service_factory"]()
    user = service.get_user_by_username("page-admin") or service.create_user("page-admin", "secret1", "admin")
    with client.session_transaction() as session:
        session["user_id"] = user["id"]
        session["auth_version"] = user["auth_version"]
        session["csrf_token"] = "test-csrf-token"
    return client


def test_base_pages_include_one_ai_chat_shell_and_assets():
    app = create_app("testing", load_env=False)
    client = _authenticated_client(app)
    for path in ("/", "/students"):
        html = client.get(path).get_data(as_text=True)
        assert html.count('class="ai-chat-toggle"') == 1
        assert html.count('id="ai-chat-panel"') == 1
        assert 'css/ai_chat.css' in html
        assert 'js/ai_chat.js' in html
        assert 'hidden' in html


def test_ai_chat_shell_includes_confirmation_and_clear_controls():
    app = create_app("testing", load_env=False)
    html = _authenticated_client(app).get("/").get_data(as_text=True)

    assert 'class="ai-chat-clear"' in html
    assert 'class="ai-chat-confirmation"' in html
    assert 'class="ai-chat-confirm"' in html
    assert 'class="ai-chat-cancel"' in html


@pytest.mark.parametrize(("path", "page_marker", "existing_markers"), [
    ("/", "data-dashboard-page", ("sidebar-nav", "data-stats-card", 'href="/students"')),
    ("/students", "data-students-page", (
        "data-students-body", "data-student-modal", "data-open-create-modal", "data-search-form",
    )),
])
def test_shared_layout_renders_one_safe_ai_chat_instance_without_page_regressions(
    path: str,
    page_marker: str,
    existing_markers: tuple[str, ...],
):
    app = create_app("testing", config_overrides={
        "DEEPSEEK_API_KEY": "test-api-key-must-not-render",
        "DEEPSEEK_API_BASE": "https://api.invalid.example/v1",
        "DEEPSEEK_MODEL": "test-model-must-not-render",
    }, load_env=False)
    response = _authenticated_client(app).get(path)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert page_marker in html
    assert all(marker in html for marker in existing_markers)
    assert html.count('class="ai-chat-toggle"') == 1
    assert html.count('id="ai-chat-panel"') == 1
    assert html.count('class="ai-chat-messages"') == 1
    assert html.count('class="ai-chat-input"') == 1
    assert html.count('class="ai-chat-send"') == 1
    assert html.count('class="ai-chat-confirmation"') == 1
    assert html.count('class="ai-chat-clear"') == 1
    assert html.count('css/ai_chat.css') == 1
    assert html.count('js/ai_chat.js') == 1
    assert 'aria-expanded="false"' in html
    assert 'aria-hidden="true"' in html
    assert 'id="ai-chat-panel" class="ai-chat-panel"' in html
    assert "fetch(" not in html
    assert all(secret not in html for secret in (
        "test-api-key-must-not-render", "https://api.invalid.example/v1",
        "test-model-must-not-render", "reasoning_content", "confirmation_token",
    ))
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert not [item for item, count in Counter(ids).items() if count > 1]


def test_ai_chat_resources_are_owned_once_by_shared_base_template():
    root = create_app("testing", load_env=False).root_path
    base = open(f"{root}/templates/base.html", encoding="utf-8").read()
    dashboard = open(f"{root}/templates/dashboard.html", encoding="utf-8").read()
    students = open(f"{root}/templates/students.html", encoding="utf-8").read()

    assert base.count('{% include "_ai_chat.html" %}') == 1
    assert base.count("css/ai_chat.css") == 1
    assert base.count("js/ai_chat.js") == 1
    assert all("ai-chat-" not in template for template in (dashboard, students))


def test_ai_chat_static_assets_use_safe_client_patterns():
    root = create_app("testing", load_env=False).root_path
    js = open(f"{root}/static/js/ai_chat.js", encoding="utf-8").read()
    css = open(f"{root}/static/css/ai_chat.css", encoding="utf-8").read()
    style = open(f"{root}/static/css/style.css", encoding="utf-8").read()
    assert 'fetch("/api/chat"' in js
    assert 'fetch("/api/chat/actions/confirm"' in js
    assert 'textContent' in js
    assert 'innerHTML' not in js
    assert 'sessionStorage' in js
    assert 'localStorage' not in js
    assert 'confirmation_token: pendingAction.confirmationToken' in js
    assert 'student-modal-opened' in js
    assert 'event.key === "Escape"' in js
    assert 'aria-expanded' in js and 'aria-hidden' in js
    assert 'z-index: 80' in css
    assert '.modal-backdrop' in style and 'z-index: 90' in style
    assert 'confirmation_token' not in html_safe_storage_contract(js)
    for class_name in (
        "ai-chat-toggle", "ai-chat-panel", "ai-chat-header", "ai-chat-messages",
        "ai-chat-input", "ai-chat-send", "ai-chat-confirmation", "ai-chat-loading",
        "ai-chat-error",
    ):
        assert f".{class_name}" in css


def html_safe_storage_contract(js: str) -> str:
    """Return the storage serialization block for sensitive-field checks."""
    start = js.index('function saveHistory()')
    end = js.index('function restoreHistory()', start)
    return js[start:end]
