"""Server-rendered AI Chat shell checks."""
from app import create_app


def test_base_pages_include_one_ai_chat_shell_and_assets():
    app = create_app("testing", load_env=False)
    client = app.test_client()
    for path in ("/", "/students"):
        html = client.get(path).get_data(as_text=True)
        assert html.count('class="ai-chat-toggle"') == 1
        assert html.count('id="ai-chat-panel"') == 1
        assert 'css/ai_chat.css' in html
        assert 'js/ai_chat.js' in html
        assert 'hidden' in html


def test_ai_chat_shell_includes_confirmation_and_clear_controls():
    app = create_app("testing", load_env=False)
    html = app.test_client().get("/").get_data(as_text=True)

    assert 'class="ai-chat-clear"' in html
    assert 'class="ai-chat-confirmation"' in html
    assert 'class="ai-chat-confirm"' in html
    assert 'class="ai-chat-cancel"' in html


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
    assert '.ai-chat-' in css


def html_safe_storage_contract(js: str) -> str:
    """Return the storage serialization block for sensitive-field checks."""
    start = js.index('function saveHistory()')
    end = js.index('function restoreHistory()', start)
    return js[start:end]
