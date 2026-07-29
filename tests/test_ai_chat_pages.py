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


def test_ai_chat_static_assets_use_safe_client_patterns():
    root = create_app("testing", load_env=False).root_path
    js = open(f"{root}/static/js/ai_chat.js", encoding="utf-8").read()
    css = open(f"{root}/static/css/ai_chat.css", encoding="utf-8").read()
    assert 'fetch("/api/chat"' in js
    assert 'textContent' in js
    assert 'innerHTML' not in js
    assert 'localStorage' not in js and 'sessionStorage' not in js
    assert '/actions/confirm' not in js
    assert '.ai-chat-' in css
