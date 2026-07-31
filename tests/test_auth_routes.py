"""Tests for login, session, CSRF, and HTTP authorization."""

from __future__ import annotations

import re
from datetime import timedelta

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
def app(tmp_path):
    return create_app(
        "testing",
        load_env=False,
        config_overrides={
            "DATABASE_PATH": str(tmp_path / "auth-routes.db"),
            "SECRET_KEY": "test-secret-not-for-production",
            **BOOTSTRAP,
        },
    )


@pytest.fixture()
def client(app):
    return app.test_client()


def _csrf_from_html(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, html
    return match.group(1)


def _login(client, username: str, password: str):
    response = client.get("/login")
    token = _csrf_from_html(response.get_data(as_text=True))
    return client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": token},
        follow_redirects=False,
    )


def _csrf_header(client) -> dict[str, str]:
    response = client.get("/")
    html = response.get_data(as_text=True)
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    assert match, html
    return {"X-CSRF-Token": match.group(1)}


def test_app_factory_bootstraps_default_users(app):
    user_service = app.extensions["user_service_factory"]()

    assert user_service.authenticate("viewer", "viewer1")["role"] == "viewer"
    assert user_service.authenticate("staff", "staff1")["role"] == "staff"
    assert user_service.authenticate("admin", "admin1")["role"] == "admin"


def test_login_page_and_successful_login_create_minimal_session(client):
    response = client.get("/login")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="username"' in html
    assert 'name="password"' in html
    assert 'name="csrf_token"' in html

    login = _login(client, "viewer", "viewer1")
    assert login.status_code == 302
    assert login.headers["Location"] == "/"
    with client.session_transaction() as session:
        assert set(session.keys()) <= {"user_id", "auth_version", "csrf_token", "_permanent"}
        assert session.permanent is True
        assert "role" not in session
        assert "password" not in session
        assert "password_hash" not in session


def test_login_failure_is_generic_and_inactive_rejected(client, app):
    response = client.get("/login")
    token = _csrf_from_html(response.get_data(as_text=True))
    bad = client.post(
        "/login",
        data={"username": "viewer", "password": "wrong", "csrf_token": token},
    )
    assert bad.status_code == 401
    assert "wrong" not in bad.get_data(as_text=True).lower()

    service = app.extensions["user_service_factory"]()
    viewer = service.get_user_by_username("viewer")
    service.repository.set_active(viewer["id"], False)
    response = client.get("/login")
    token = _csrf_from_html(response.get_data(as_text=True))
    inactive = client.post(
        "/login",
        data={"username": "viewer", "password": "viewer1", "csrf_token": token},
    )
    assert inactive.status_code == 401


def test_login_failures_record_safe_reasoned_security_events(client, app, monkeypatch):
    events = []
    monkeypatch.setattr(
        "app.routes.auth.log_security_event",
        lambda event, metadata=None: events.append((event, metadata or {})),
    )
    service = app.extensions["user_service_factory"]()
    viewer = service.get_user_by_username("viewer")
    password_hash = viewer["password_hash"]

    response = client.get("/login")
    token = _csrf_from_html(response.get_data(as_text=True))
    missing = client.post(
        "/login",
        data={"username": "missing", "password": "secret-password", "csrf_token": token},
    )
    response = client.get("/login")
    token = _csrf_from_html(response.get_data(as_text=True))
    wrong = client.post(
        "/login",
        data={"username": "viewer", "password": "secret-password", "csrf_token": token},
    )
    service.repository.set_active(viewer["id"], False)
    response = client.get("/login")
    token = _csrf_from_html(response.get_data(as_text=True))
    inactive = client.post(
        "/login",
        data={"username": "viewer", "password": "viewer1", "csrf_token": token},
    )

    assert missing.status_code == wrong.status_code == inactive.status_code == 401
    assert "用户名或密码无效" in inactive.get_data(as_text=True)
    assert events == [
        ("login_failed", {"username": "missing", "outcome": "denied", "reason": "invalid_credentials"}),
        ("login_failed", {"username": "viewer", "outcome": "denied", "reason": "invalid_credentials"}),
        (
            "inactive_account_rejected",
            {
                "user_id": viewer["id"],
                "username": "viewer",
                "role": "viewer",
                "outcome": "denied",
                "reason": "inactive_account",
            },
        ),
    ]
    event_text = str(events)
    assert "secret-password" not in event_text
    assert "viewer1" not in event_text
    assert password_hash not in event_text


def test_unauthenticated_pages_redirect_and_api_returns_json_401(client):
    page = client.get("/")
    assert page.status_code == 302
    assert page.headers["Location"].startswith("/login?next=")

    students = client.get("/students")
    assert students.status_code == 302
    assert students.headers["Location"].startswith("/login?next=")

    api = client.get("/api/students")
    assert api.status_code == 401
    assert api.get_json()["error"]["code"] == "unauthorized"
    assert client.get("/api/health").status_code == 200


def test_unauthenticated_page_redirect_records_safe_security_event(client, monkeypatch):
    events = []
    monkeypatch.setattr(
        "app.auth.log_security_event",
        lambda event, metadata=None: events.append((event, metadata or {})),
    )

    response = client.get("/", headers={
        "Cookie": "student_v2_session=secret-cookie",
        "Authorization": "Bearer secret-token",
        "X-CSRF-Token": "secret-csrf",
    })

    assert response.status_code == 302
    assert events == [(
        "anonymous_access_rejected",
        {
            "endpoint": "pages.dashboard_page",
            "method": "GET",
            "outcome": "rejected",
            "reason": "missing_login",
        },
    )]
    assert "secret-cookie" not in str(events)
    assert "secret-token" not in str(events)
    assert "secret-csrf" not in str(events)


def test_unauthenticated_api_401_records_safe_security_event(client, monkeypatch):
    events = []
    monkeypatch.setattr(
        "app.auth.log_security_event",
        lambda event, metadata=None: events.append((event, metadata or {})),
    )

    response = client.get("/api/students", headers={
        "Cookie": "student_v2_session=secret-cookie",
        "Authorization": "Bearer secret-token",
        "X-CSRF-Token": "secret-csrf",
    })

    assert response.status_code == 401
    assert events == [(
        "anonymous_access_rejected",
        {
            "endpoint": "students.list_students",
            "method": "GET",
            "outcome": "rejected",
            "reason": "missing_login",
        },
    )]
    assert "secret-cookie" not in str(events)
    assert "secret-token" not in str(events)
    assert "secret-csrf" not in str(events)


@pytest.mark.parametrize(("path", "payload", "endpoint"), [
    ("/api/chat", {"messages": [{"role": "user", "content": "hello"}]}, "chat.chat"),
    ("/api/chat/actions/confirm", {"confirmation_token": "secret-confirmation-token"}, "chat.confirm_chat_action"),
])
def test_unauthenticated_chat_endpoints_record_safe_json_401(client, monkeypatch, path, payload, endpoint):
    events = []
    monkeypatch.setattr(
        "app.auth.log_security_event",
        lambda event, metadata=None: events.append((event, metadata or {})),
    )

    response = client.post(path, json=payload, headers={
        "Cookie": "student_v2_session=secret-cookie",
        "Authorization": "Bearer secret-token",
        "X-CSRF-Token": "secret-csrf",
    })

    assert response.status_code == 401
    assert response.is_json
    assert "Location" not in response.headers
    assert events == [(
        "anonymous_access_rejected",
        {
            "endpoint": endpoint,
            "method": "POST",
            "outcome": "rejected",
            "reason": "missing_login",
        },
    )]
    event_text = str(events)
    assert "secret-cookie" not in event_text
    assert "secret-token" not in event_text
    assert "secret-csrf" not in event_text
    assert "secret-confirmation-token" not in event_text
    assert "hello" not in event_text


def test_public_routes_do_not_record_anonymous_rejection(client, monkeypatch):
    events = []
    monkeypatch.setattr(
        "app.auth.log_security_event",
        lambda event, metadata=None: events.append((event, metadata or {})),
    )

    assert client.get("/login").status_code == 200
    assert client.get("/api/health").status_code == 200

    assert events == []


def test_open_redirect_is_rejected(client):
    response = client.get("/login")
    token = _csrf_from_html(response.get_data(as_text=True))
    login = client.post(
        "/login?next=https://evil.example/",
        data={"username": "viewer", "password": "viewer1", "csrf_token": token},
        follow_redirects=False,
    )
    assert login.status_code == 302
    assert login.headers["Location"] == "/"


def test_logout_requires_post_csrf_and_clears_session(client):
    assert _login(client, "viewer", "viewer1").status_code == 302
    assert client.get("/logout").status_code == 405

    missing = client.post("/logout")
    assert missing.status_code == 403

    response = client.post("/logout", headers=_csrf_header(client))
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
    with client.session_transaction() as session:
        assert not session


def test_login_session_cookie_has_bounded_expiration(client, app):
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=123)

    login = _login(client, "viewer", "viewer1")

    assert "Expires=" in login.headers.get("Set-Cookie", "")
    with client.session_transaction() as session:
        assert session.permanent is True


def test_custom_session_lifetime_config_is_applied(tmp_path):
    app = create_app(
        "testing",
        load_env=False,
        config_overrides={
            "DATABASE_PATH": str(tmp_path / "custom-lifetime.db"),
            "SECRET_KEY": "test-secret-not-for-production",
            "PERMANENT_SESSION_LIFETIME_SECONDS": 777,
            **BOOTSTRAP,
        },
    )

    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(seconds=777)


def test_production_login_cookie_is_secure(tmp_path):
    app = create_app(
        "production",
        load_env=False,
        config_overrides={
            "DATABASE_PATH": str(tmp_path / "prod-auth.db"),
            "SECRET_KEY": "production-secret-not-default",
            **BOOTSTRAP,
        },
    )
    client = app.test_client()

    response = client.get("/login")
    token = _csrf_from_html(response.get_data(as_text=True))
    login = client.post(
        "/login",
        data={"username": "viewer", "password": "viewer1", "csrf_token": token},
        follow_redirects=False,
    )

    assert "Secure" in login.headers.get("Set-Cookie", "")


def test_auth_version_change_invalidates_existing_session(client, app):
    assert _login(client, "viewer", "viewer1").status_code == 302
    service = app.extensions["user_service_factory"]()
    viewer = service.get_user_by_username("viewer")
    service.repository.increment_auth_version(viewer["id"])

    response = client.get("/students")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login?next=")
    with client.session_transaction() as session:
        assert not session


def test_inactive_existing_session_uses_session_invalidated_event(client, app, monkeypatch):
    events = []
    monkeypatch.setattr(
        "app.auth.log_security_event",
        lambda event, metadata=None: events.append((event, metadata or {})),
    )
    assert _login(client, "viewer", "viewer1").status_code == 302
    service = app.extensions["user_service_factory"]()
    viewer = service.get_user_by_username("viewer")
    service.repository.set_active(viewer["id"], False)

    response = client.get("/students")

    assert response.status_code == 302
    assert events[0] == ("session_invalidated", {"endpoint": "pages.students_page"})
    assert events[1] == (
        "anonymous_access_rejected",
        {
            "endpoint": "pages.students_page",
            "method": "GET",
            "outcome": "rejected",
            "reason": "missing_login",
        },
    )


def test_all_application_routes_are_explicitly_public_or_protected(app):
    from app.auth import ENDPOINT_ROLES, PUBLIC_ENDPOINTS

    ignored = {None}
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules() if rule.endpoint not in ignored}

    assert endpoints <= (PUBLIC_ENDPOINTS | set(ENDPOINT_ROLES))


def test_csrf_rejects_unsafe_api_before_service(client):
    assert _login(client, "staff", "staff1").status_code == 302

    response = client.post("/api/students", json={"student_number": "001", "name": "Alice"})

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"


def test_student_api_role_matrix(client):
    assert _login(client, "viewer", "viewer1").status_code == 302
    headers = _csrf_header(client)
    viewer_create = client.post(
        "/api/students",
        json={"student_number": "001", "name": "Alice"},
        headers=headers,
    )
    assert viewer_create.status_code == 403
    client.post("/logout", headers=headers)

    assert _login(client, "staff", "staff1").status_code == 302
    headers = _csrf_header(client)
    staff_create = client.post(
        "/api/students",
        json={"student_number": "001", "name": "Alice"},
        headers=headers,
    )
    assert staff_create.status_code == 201
    student_id = staff_create.get_json()["data"]["id"]
    staff_delete = client.delete(f"/api/students/{student_id}", headers=headers)
    assert staff_delete.status_code == 403
    client.post("/logout", headers=headers)

    assert _login(client, "admin", "admin1").status_code == 302
    headers = _csrf_header(client)
    admin_delete = client.delete(f"/api/students/{student_id}", headers=headers)
    assert admin_delete.status_code == 200


class FakeConfirmService:
    def __init__(self):
        self.confirm_calls: list[str] = []

    async def confirm_action(self, token: str):
        self.confirm_calls.append(token)
        return {
            "success": True,
            "reply": "ok",
            "requires_confirmation": False,
            "pending_action": None,
            "action_result": {"success": True, "data": {"ok": True}},
        }


def _token(app, tool_name: str, action_id: str):
    return app.extensions["ai_action_confirmation"].create_token({
        "tool_name": tool_name,
        "arguments": {"student_id": 1},
        "action_id": action_id,
    })


def test_ai_confirmation_role_matrix_uses_current_database_role(client, app):
    service = FakeConfirmService()
    app.extensions["ai_chat_service_factory"] = lambda: service

    assert _login(client, "viewer", "viewer1").status_code == 302
    viewer_delete = client.post(
        "/api/chat/actions/confirm",
        json={"confirmation_token": _token(app, "delete_student", "viewer-delete")},
        headers=_csrf_header(client),
    )
    assert viewer_delete.status_code == 403
    assert service.confirm_calls == []
    client.post("/logout", headers=_csrf_header(client))

    assert _login(client, "staff", "staff1").status_code == 302
    staff_add_token = _token(app, "add_student", "staff-add")
    staff_add = client.post(
        "/api/chat/actions/confirm",
        json={"confirmation_token": staff_add_token},
        headers=_csrf_header(client),
    )
    assert staff_add.status_code == 200
    assert service.confirm_calls == [staff_add_token]

    staff_delete = client.post(
        "/api/chat/actions/confirm",
        json={"confirmation_token": _token(app, "delete_student", "staff-delete")},
        headers=_csrf_header(client),
    )
    assert staff_delete.status_code == 403
    assert service.confirm_calls == [staff_add_token]
    client.post("/logout", headers=_csrf_header(client))

    assert _login(client, "admin", "admin1").status_code == 302
    admin_delete_token = _token(app, "delete_student", "admin-delete")
    admin_delete = client.post(
        "/api/chat/actions/confirm",
        json={"confirmation_token": admin_delete_token},
        headers=_csrf_header(client),
    )
    assert admin_delete.status_code == 200
    assert service.confirm_calls == [staff_add_token, admin_delete_token]


def test_ai_confirmation_forbidden_records_safe_security_event(client, app, monkeypatch):
    service = FakeConfirmService()
    app.extensions["ai_chat_service_factory"] = lambda: service
    events = []
    monkeypatch.setattr(
        "app.routes.chat.log_security_event",
        lambda event, metadata=None: events.append((event, metadata or {})),
        raising=False,
    )

    assert _login(client, "viewer", "viewer1").status_code == 302
    token = _token(app, "delete_student", "viewer-delete")
    response = client.post(
        "/api/chat/actions/confirm",
        json={"confirmation_token": token, "tool_name": "client-forged"},
        headers=_csrf_header(client),
    )

    assert response.status_code == 403
    assert service.confirm_calls == []
    assert events == [(
        "authorization_denied",
        {
            "user_id": 1,
            "username": "viewer",
            "role": "viewer",
            "endpoint": "chat.confirm_chat_action",
            "method": "POST",
            "tool_name": "delete_student",
            "outcome": "denied",
            "reason": "ai_confirmation_forbidden",
        },
    )]
    event_text = str(events)
    assert token not in event_text
    assert "client-forged" not in event_text
    assert "student_id" not in event_text
