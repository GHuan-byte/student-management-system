"""Tests for bootstrap user configuration and startup behavior."""

from __future__ import annotations

import pytest

from app.config import DEV_SECRET_KEY, PLACEHOLDER_SECRET_KEY, create_config
from app.database.schema import initialize_database


BOOTSTRAP_ENV = {
    "BOOTSTRAP_DEFAULT_USERS_ENABLED": "true",
    "BOOTSTRAP_VIEWER_USERNAME": "viewer",
    "BOOTSTRAP_VIEWER_PASSWORD": "viewer1",
    "BOOTSTRAP_STAFF_USERNAME": "staff",
    "BOOTSTRAP_STAFF_PASSWORD": "staff1",
    "BOOTSTRAP_ADMIN_USERNAME": "admin",
    "BOOTSTRAP_ADMIN_PASSWORD": "admin1",
}


@pytest.fixture(autouse=True)
def _clean_bootstrap_env(monkeypatch):
    for key in BOOTSTRAP_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SECRET_KEY", "test-secret-not-for-production")
    monkeypatch.setenv("APP_ENV", "testing")


def _mapping(monkeypatch, env=None, config_name="testing"):
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)
    return create_config(config_name).to_mapping()


def test_bootstrap_config_defaults_disabled_without_passwords(monkeypatch):
    mapping = _mapping(monkeypatch)

    assert mapping["BOOTSTRAP_DEFAULT_USERS_ENABLED"] is False
    assert mapping["BOOTSTRAP_VIEWER_USERNAME"] == "viewer"
    assert mapping["BOOTSTRAP_VIEWER_PASSWORD"] is None
    assert mapping["BOOTSTRAP_STAFF_USERNAME"] == "staff"
    assert mapping["BOOTSTRAP_STAFF_PASSWORD"] is None
    assert mapping["BOOTSTRAP_ADMIN_USERNAME"] == "admin"
    assert mapping["BOOTSTRAP_ADMIN_PASSWORD"] is None


def test_production_defaults_bootstrap_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "production-secret")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "prod.db"))

    mapping = _mapping(monkeypatch, config_name="production")

    assert mapping["APP_ENV"] == "production"
    assert mapping["BOOTSTRAP_DEFAULT_USERS_ENABLED"] is False


@pytest.mark.parametrize("secret", ["", DEV_SECRET_KEY, PLACEHOLDER_SECRET_KEY])
def test_production_rejects_unsafe_secret_key(monkeypatch, tmp_path, secret):
    monkeypatch.setenv("SECRET_KEY", secret)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "prod.db"))
    config = create_config("production")
    mapping = config.to_mapping()

    with pytest.raises(RuntimeError):
        config.finalize(mapping, project_root=tmp_path, instance_path=tmp_path / "instance")


def test_ensure_bootstrap_users_creates_three_role_accounts(monkeypatch, tmp_path):
    from app.repositories.user_repository import UserRepository
    from app.services.user_service import UserService

    database_path = tmp_path / "auth.db"
    initialize_database(database_path)
    mapping = _mapping(monkeypatch, BOOTSTRAP_ENV)
    service = UserService(UserRepository(database_path=database_path))

    result = service.ensure_bootstrap_users(mapping)

    assert {item["role"] for item in result["created"]} == {"viewer", "staff", "admin"}
    for username, password, role in (
        ("viewer", "viewer1", "viewer"),
        ("staff", "staff1", "staff"),
        ("admin", "admin1", "admin"),
    ):
        user = service.authenticate(username, password)
        assert user is not None
        assert user["role"] == role
        assert user["password_hash"] != password


def test_bootstrap_is_idempotent_and_does_not_overwrite_existing_users(monkeypatch, tmp_path):
    from app.repositories.user_repository import UserRepository
    from app.services.user_service import UserService

    database_path = tmp_path / "auth.db"
    initialize_database(database_path)
    mapping = _mapping(monkeypatch, BOOTSTRAP_ENV)
    repository = UserRepository(database_path=database_path)
    service = UserService(repository)

    service.ensure_bootstrap_users(mapping)
    staff_before = service.get_user_by_username("staff")
    repository.update_role(staff_before["id"], "admin")
    repository.set_active(staff_before["id"], False)
    hash_before = service.get_user_by_username("staff")["password_hash"]

    second = service.ensure_bootstrap_users(mapping)
    users = repository.list_users()
    staff_after = service.get_user_by_username("staff")

    assert second["created"] == []
    assert len(users) == 3
    assert staff_after["password_hash"] == hash_before
    assert staff_after["role"] == "admin"
    assert staff_after["is_active"] is False


def test_bootstrap_existing_accounts_record_safe_skip_events(monkeypatch, tmp_path):
    from app.repositories.user_repository import UserRepository
    from app.services.user_service import UserService

    database_path = tmp_path / "auth.db"
    initialize_database(database_path)
    mapping = _mapping(monkeypatch, BOOTSTRAP_ENV)
    repository = UserRepository(database_path=database_path)
    service = UserService(repository)
    service.ensure_bootstrap_users(mapping)
    staff_before = service.get_user_by_username("staff")
    repository.update_role(staff_before["id"], "admin")
    repository.set_active(staff_before["id"], False)
    staff_hash_before = service.get_user_by_username("staff")["password_hash"]
    events = []
    monkeypatch.setattr(
        "app.services.user_service.log_security_event",
        lambda event, metadata=None: events.append((event, metadata or {})),
    )

    second = service.ensure_bootstrap_users(mapping)
    staff_after = service.get_user_by_username("staff")

    assert second["created"] == []
    assert {item["username"] for item in second["skipped"]} == {"viewer", "staff", "admin"}
    assert staff_after["password_hash"] == staff_hash_before
    assert staff_after["role"] == "admin"
    assert staff_after["is_active"] is False
    assert events == [
        ("bootstrap_user_skipped", {"username": "viewer", "role": "viewer", "outcome": "skipped", "reason": "already_exists"}),
        ("bootstrap_user_skipped", {"username": "staff", "role": "admin", "outcome": "skipped", "reason": "already_exists"}),
        ("bootstrap_user_skipped", {"username": "admin", "role": "admin", "outcome": "skipped", "reason": "already_exists"}),
    ]
    event_text = str(events)
    assert "viewer1" not in event_text
    assert "staff1" not in event_text
    assert "admin1" not in event_text
    assert staff_hash_before not in event_text


@pytest.mark.parametrize("overrides", [
    {"BOOTSTRAP_ADMIN_PASSWORD": ""},
    {"BOOTSTRAP_ADMIN_USERNAME": "viewer"},
    {"BOOTSTRAP_VIEWER_USERNAME": "   "},
    {"BOOTSTRAP_STAFF_PASSWORD": "12345"},
])
def test_bootstrap_invalid_config_fails_without_secret_values(monkeypatch, tmp_path, overrides):
    from app.repositories.user_repository import UserRepository
    from app.services.user_service import UserService

    database_path = tmp_path / "auth.db"
    initialize_database(database_path)
    env = {**BOOTSTRAP_ENV, **overrides}
    mapping = _mapping(monkeypatch, env)
    service = UserService(UserRepository(database_path=database_path))

    with pytest.raises(ValueError) as error:
        service.ensure_bootstrap_users(mapping)

    message = str(error.value)
    assert "viewer1" not in message
    assert "staff1" not in message
    assert "admin1" not in message
