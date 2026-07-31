"""Tests for login/access-control browser surface."""

from __future__ import annotations

import re

import pytest

from app import create_app


BOOTSTRAP = {
    "BOOTSTRAP_DEFAULT_USERS_ENABLED": True,
    "BOOTSTRAP_VIEWER_USERNAME": "viewer",
    "BOOTSTRAP_VIEWER_PASSWORD": "viewer1",
    "BOOTSTRAP_STAFF_USERNAME": "staff",
    "BOOTSTRAP_STAFF_PASSWORD": "staff1",
    "BOOTSTRAP_ADMIN_USERNAME": "admin",
    "BOOTSTRAP_ADMIN_PASSWORD": "admin1",
}


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        "testing",
        load_env=False,
        config_overrides={
            "DATABASE_PATH": str(tmp_path / "frontend.db"),
            "SECRET_KEY": "test-secret-not-for-production",
            **BOOTSTRAP,
        },
    )
    return app.test_client()


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, html
    return match.group(1)


def _login(client, username: str, password: str) -> None:
    login_page = client.get("/login")
    token = _csrf(login_page.get_data(as_text=True))
    response = client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": token},
    )
    assert response.status_code == 302


def test_authenticated_layout_exposes_identity_logout_and_csrf(client):
    _login(client, "viewer", "viewer1")

    html = client.get("/").get_data(as_text=True)

    assert '<meta name="csrf-token"' in html
    assert 'data-current-username' in html
    assert 'data-current-role="viewer"' in html
    assert 'action="/logout"' in html
    assert 'method="post"' in html


def test_login_page_loads_css_and_uses_card_form_structure(client):
    html = client.get("/login").get_data(as_text=True)

    assert 'rel="stylesheet"' in html
    assert 'href="/static/css/style.css"' in html
    assert '<body class="login-page">' in html
    assert 'class="login-card"' in html
    assert 'class="login-brand"' in html
    assert 'class="login-subtitle"' in html
    assert 'class="login-form"' in html
    assert html.count('class="form-group"') >= 2
    assert 'class="login-submit"' in html
    assert 'name="username"' in html
    assert 'name="password"' in html
    assert 'name="csrf_token"' in html
    assert html.count("</label>") >= 2
    assert "?/label" not in html
    assert 'type="hidden"' in html
    assert 'method="post"' in html
    assert 'action="/login' in html
    assert "登录" in html
    assert "Student Management System V2" in html
    assert "style=" not in html


def test_login_styles_define_centered_card_and_scoped_form_controls():
    css = open("app/static/css/style.css", encoding="utf-8").read()

    for selector in (
        ".login-page",
        ".login-card",
        ".login-brand",
        ".login-subtitle",
        ".login-form",
        ".form-group",
        ".login-error",
        ".login-submit",
    ):
        assert selector in css

    assert "min-height: 100vh" in css
    assert "place-items: center" in css
    assert "max-width: 420px" in css
    assert ".login-form input" in css
    assert ".login-submit" in css and "width: 100%" in css


def test_student_page_server_controls_follow_role(client):
    _login(client, "viewer", "viewer1")
    viewer_html = client.get("/students").get_data(as_text=True)
    assert "data-open-create-modal" not in viewer_html
    assert "data-batch-delete-button" not in viewer_html

    client.post("/logout", headers={"X-CSRF-Token": re.search(r'<meta name="csrf-token" content="([^"]+)"', viewer_html).group(1)})
    _login(client, "staff", "staff1")
    staff_html = client.get("/students").get_data(as_text=True)
    assert "data-open-create-modal" in staff_html
    assert "data-batch-delete-button" not in staff_html


def test_students_and_ai_javascript_send_csrf_header():
    students_js = open("app/static/js/students.js", encoding="utf-8").read()
    ai_js = open("app/static/js/ai_chat.js", encoding="utf-8").read()

    assert "X-CSRF-Token" in students_js
    assert "csrf-token" in students_js
    assert "X-CSRF-Token" in ai_js
    assert "csrf-token" in ai_js
