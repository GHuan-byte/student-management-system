"""Test-driven coverage for the shared application logging policy."""

from __future__ import annotations

import logging
import os
import secrets
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest

from app import create_app
from app.logging_config import (
    MANAGED_HANDLER_ATTRIBUTE,
    REQUEST_ID,
    _close_managed_handlers,
    configure_mcp_logging,
    correlation_context,
    current_request_id,
    log_security_event,
    sanitize_log_value,
)
from app.config import DEFAULT_LOG_BACKUP_COUNT, DEFAULT_LOG_MAX_BYTES, DEV_SECRET_KEY, PLACEHOLDER_SECRET_KEY
from mcp_server.result import mcp_result_from_exception


@pytest.fixture
def logger_registry_assertion():
    """Assert the autouse fixture restores the registry after each test."""
    registry = logging.root.manager.loggerDict
    before = dict(registry)
    yield
    assert dict(registry) == before


@pytest.fixture(autouse=True)
def restore_logging_state(logger_registry_assertion):
    """Restore logging globals so logging tests cannot affect other tests."""
    root = logging.getLogger()
    root_handlers = list(root.handlers)
    root_level = root.level
    root_filters = list(root.filters)
    root_disabled = root.disabled
    root_propagate = root.propagate
    logger_states = {
        name: (
            list(logger.handlers),
            logger.level,
            logger.propagate,
            logger.disabled,
            list(logger.filters),
        )
        for name, logger in logging.root.manager.loggerDict.items()
        if isinstance(logger, logging.Logger)
    }
    logger_parents = {
        name: logger.parent
        for name, logger in logging.root.manager.loggerDict.items()
        if isinstance(logger, logging.Logger)
    }
    logger_registry = dict(logging.root.manager.loggerDict)
    original_handlers = {
        handler
        for handlers, *_state in logger_states.values()
        for handler in handlers
    } | set(root_handlers)
    marker_states = {
        handler: (hasattr(handler, MANAGED_HANDLER_ATTRIBUTE), getattr(handler, MANAGED_HANDLER_ATTRIBUTE, None))
        for handler in original_handlers
    }
    handler_filter_states = {handler: list(handler.filters) for handler in original_handlers}
    request_id = REQUEST_ID.get()
    environment = dict(os.environ)
    try:
        yield
    finally:
        for logger in [root, *(
            item for item in logging.root.manager.loggerDict.values()
            if isinstance(item, logging.Logger)
        )]:
            for handler in list(logger.handlers):
                if handler not in original_handlers:
                    logger.removeHandler(handler)
                    handler.close()
            logger.handlers.clear()

        root.handlers[:] = root_handlers
        root.setLevel(root_level)
        root.filters[:] = root_filters
        root.disabled = root_disabled
        root.propagate = root_propagate
        for name, state in logger_states.items():
            logger = logging.getLogger(name)
            handlers, level, propagate, disabled, filters = state
            logger.handlers[:] = handlers
            logger.setLevel(level)
            logger.propagate = propagate
            logger.disabled = disabled
            logger.filters[:] = filters
        for name, logger in logging.root.manager.loggerDict.items():
            if isinstance(logger, logging.Logger) and name not in logger_states:
                logger.setLevel(logging.NOTSET)
                logger.propagate = True
                logger.disabled = False
                logger.filters.clear()
        for name in list(logging.root.manager.loggerDict):
            if name not in logger_registry:
                del logging.root.manager.loggerDict[name]
        logging.root.manager.loggerDict.update(logger_registry)
        for name, parent in logger_parents.items():
            logger = logging.root.manager.loggerDict.get(name)
            if isinstance(logger, logging.Logger):
                logger.parent = parent
        for handler, (had_marker, marker) in marker_states.items():
            if had_marker:
                setattr(handler, MANAGED_HANDLER_ATTRIBUTE, marker)
            elif hasattr(handler, MANAGED_HANDLER_ATTRIBUTE):
                delattr(handler, MANAGED_HANDLER_ATTRIBUTE)
        for handler, filters in handler_filter_states.items():
            handler.filters[:] = filters
        REQUEST_ID.set(request_id)
        os.environ.clear()
        os.environ.update(environment)


def test_logging_fixture_removes_logger_entries_created_during_a_test():
    logging.getLogger("test.logging.created_during_test")


def test_default_logging_policy_installs_a_managed_console_handler():
    app = create_app("testing", load_env=False)

    handlers = [
        handler
        for handler in app.logger.handlers
        if getattr(handler, "_student_management_managed", False)
    ]

    assert len(handlers) == 1
    assert handlers[0].level == logging.INFO


def test_file_logging_writes_a_safe_startup_record_with_standard_fields(tmp_path):
    log_path = tmp_path / "startup" / "app.log"

    app = create_app(
        "testing",
        config_overrides={"LOG_FILE_ENABLED": True, "LOG_TEST_FILE_PATH": str(log_path)},
        load_env=False,
    )
    for handler in app.logger.handlers:
        handler.flush()

    output = log_path.read_text(encoding="utf-8")

    assert "event=application_logging_configured" in output
    assert "message=Application logging configured" in output
    assert "timestamp=" in output
    assert "level=INFO" in output
    assert "logger=app" in output
    assert "request_id=-" in output


def test_managed_formatter_has_standard_fallback_fields():
    app = create_app("testing", load_env=False)
    handler = next(
        handler
        for handler in app.logger.handlers
        if getattr(handler, "_student_management_managed", False)
    )
    record = logging.LogRecord("app", logging.INFO, __file__, 1, "ready", (), None)

    rendered = handler.format(record)

    assert "request_id=-" in rendered
    assert "event=-" in rendered
    assert "ready" in rendered


def test_records_in_one_flask_request_share_server_generated_request_id():
    app = create_app("testing", load_env=False)
    observed: list[str] = []

    @app.get("/logging-request-id")
    def logging_request_id():
        observed.append(current_request_id())
        app.logger.info("first")
        observed.append(current_request_id())
        app.logger.info("second")
        return "ok"

    response = app.test_client().get("/logging-request-id", headers={"X-Request-ID": "client-id"})

    assert response.status_code == 200
    assert len(observed) == 2
    assert observed[0] == observed[1]
    assert observed[0] != "client-id"
    assert len(observed[0]) == 32


def test_separate_flask_requests_receive_distinct_server_generated_request_ids():
    app = create_app("testing", load_env=False)
    observed: list[str] = []

    @app.get("/logging-distinct-request-id")
    def logging_distinct_request_id():
        observed.append(current_request_id())
        return "ok"

    client = app.test_client()
    assert client.get("/logging-distinct-request-id").status_code == 200
    assert client.get("/logging-distinct-request-id").status_code == 200

    assert len(observed) == 2
    assert observed[0] != observed[1]


def test_request_context_resets_and_explicit_non_request_context_is_supported():
    app = create_app("testing", load_env=False)

    @app.get("/reset-request-id")
    def reset_request_id():
        return "ok"

    app.test_client().get("/reset-request-id")

    assert current_request_id() == "-"
    with correlation_context("mcp-correlation"):
        assert current_request_id() == "mcp-correlation"
    assert current_request_id() == "-"


def test_security_event_redacts_sensitive_values_without_mutating_metadata():
    app = create_app("testing", load_env=False)
    handler = next(
        handler
        for handler in app.logger.handlers
        if getattr(handler, "_student_management_managed", False)
    )
    stream = StringIO()
    handler.setStream(stream)
    metadata = {
        "password": "open-sesame",
        "nested": [{"authorization": "Bearer private-token"}],
        "student": {
            "student_number": "001",
            "name": "Student Name",
            "gender": "X",
            "age": 20,
            "major": "CS",
            "year_level": "大一",
            "score": 99,
            "phone": "123",
            "email": "student@example.test",
        },
    }

    log_security_event("login_failed", metadata=metadata)

    output = stream.getvalue()
    assert "open-sesame" not in output
    assert "private-token" not in output
    assert "Student Name" not in output
    assert metadata["password"] == "open-sesame"
    assert metadata["nested"][0]["authorization"] == "Bearer private-token"


@pytest.mark.parametrize(
    ("message", "secret"),
    [
        ("password open-sesame", "open-sesame"),
        ("API key api-secret", "api-secret"),
        ("csrf token csrf-secret", "csrf-secret"),
        ("session token session-secret", "session-secret"),
        ("AI confirmation token confirmation-secret", "confirmation-secret"),
    ],
)
def test_string_redaction_covers_common_free_form_sensitive_values(message, secret):
    sanitized = sanitize_log_value(message)

    assert secret not in sanitized
    assert "[REDACTED]" in sanitized


@pytest.mark.parametrize(
    "message",
    [
        "Authorization: Bearer secret",
        "Authorization=Bearer secret",
        "authorization bearer secret",
        "Bearer secret",
    ],
)
def test_authorization_and_bearer_credentials_are_fully_redacted_in_messages_and_exceptions(message):
    app = create_app("testing", load_env=False)
    handler = next(handler for handler in app.logger.handlers if getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False))
    stream = StringIO()
    handler.setStream(stream)

    assert "secret" not in sanitize_log_value(message)
    try:
        raise RuntimeError(message)
    except RuntimeError:
        app.logger.exception("safe context remains")

    output = stream.getvalue()
    assert "safe context remains" in output
    assert "Traceback" in output
    assert "secret" not in output


@pytest.mark.parametrize(
    ("header", "credentials"),
    [
        ("Authorization: Basic base64credential", ("base64credential",)),
        ("Authorization=Basic base64credential", ("base64credential",)),
        ("Authorization: Token secret", ("secret",)),
        ('Authorization: Digest username="x", response="secret"', ('username="x"', 'response="secret"')),
        ("authorization: basic credential", ("credential",)),
        ("Authorization  :   Basic   whitespace-secret", ("whitespace-secret",)),
    ],
)
def test_authorization_headers_redact_any_scheme_in_messages_metadata_arguments_and_exceptions(header, credentials):
    app = create_app("testing", load_env=False)
    handler = next(handler for handler in app.logger.handlers if getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False))
    stream = StringIO()
    handler.setStream(stream)
    metadata = {"detail": header}
    arguments = {"detail": header}

    sanitized = sanitize_log_value(header)
    assert "authorization" in sanitized.lower()
    for credential in credentials:
        assert credential not in sanitized

    log_security_event("authorization_header_seen", metadata=metadata)
    app.logger.info("safe surrounding argument %s", arguments)
    try:
        raise RuntimeError(header)
    except RuntimeError:
        app.logger.exception("safe surrounding exception context")

    output = stream.getvalue()
    assert "safe surrounding argument" in output
    assert "safe surrounding exception context" in output
    assert "Traceback" in output
    assert "authorization" in output.lower()
    for credential in credentials:
        assert credential not in output
    assert metadata["detail"] == header
    assert arguments["detail"] == header


@pytest.mark.parametrize(
    ("header", "credential", "trailing_context"),
    [
        ("Authorization: 1scheme numeric-secret", "numeric-secret", None),
        ("Authorization: 9 digit-secret", "digit-secret", None),
        ("Authorization: !scheme punctuation-secret", "punctuation-secret", None),
        ("authorization: 9 lowercase-secret", "lowercase-secret", None),
        (
            "safe leading Authorization: 1scheme semicolon-secret; safe semicolon suffix",
            "semicolon-secret",
            "safe semicolon suffix",
        ),
        (
            "safe leading Authorization: 1scheme pipe-secret | safe pipe suffix",
            "pipe-secret",
            "safe pipe suffix",
        ),
    ],
)
def test_token_style_authorization_schemes_redact_credentials_without_mutating_values(
    header,
    credential,
    trailing_context,
):
    app = create_app("testing", load_env=False)
    handler = next(handler for handler in app.logger.handlers if getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False))
    stream = StringIO()
    handler.setStream(stream)
    metadata = {"detail": header}
    arguments = {"detail": header}

    sanitized = sanitize_log_value(header)
    assert credential not in sanitized
    assert "authorization" in sanitized.lower()
    assert "[REDACTED]" in sanitized
    assert "safe leading" in sanitized or "safe leading" not in header
    if trailing_context:
        assert trailing_context in sanitized

    log_security_event("token_style_authorization", metadata=metadata)
    app.logger.info("safe leading logging arguments %s", arguments)
    try:
        raise RuntimeError(header)
    except RuntimeError:
        app.logger.exception("safe leading exception context")

    output = stream.getvalue()
    assert credential not in output
    assert "authorization" in output.lower()
    assert "[REDACTED]" in output
    assert "safe leading logging arguments" in output
    assert "safe leading exception context" in output
    assert "Traceback" in output
    if trailing_context:
        assert trailing_context in output
    assert metadata["detail"] == header
    assert arguments["detail"] == header


def test_structured_api_key_names_are_redacted_without_mutating_the_caller():
    metadata = {"DEEPSEEK_API_KEY": "api-secret"}

    sanitized = sanitize_log_value(metadata)

    assert sanitized["DEEPSEEK_API_KEY"] == "[REDACTED]"
    assert metadata["DEEPSEEK_API_KEY"] == "api-secret"


def test_logging_arguments_are_redacted_without_mutating_nested_caller_values():
    app = create_app("testing", load_env=False)
    handler = next(handler for handler in app.logger.handlers if getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False))
    stream = StringIO()
    handler.setStream(stream)
    arguments = {
        "authorization": "Bearer argument-secret",
        "nested": [{"password": "nested-secret"}],
    }

    app.logger.info("safe message %s", arguments)

    assert "argument-secret" not in stream.getvalue()
    assert "nested-secret" not in stream.getvalue()
    assert arguments["authorization"] == "Bearer argument-secret"
    assert arguments["nested"][0]["password"] == "nested-secret"


@pytest.mark.parametrize(
    ("message", "arguments"),
    [
        ("password=%s", lambda secret, _student: (secret,)),
        ("Authorization: %s", lambda secret, _student: (f"Bearer {secret}",)),
        ("student=%s", lambda _secret, student: (student,)),
        ("password=%(password)s", lambda secret, _student: {"password": secret}),
    ],
)
def test_logging_formatting_errors_do_not_leak_original_arguments_to_stderr(
    message,
    arguments,
    capsys,
):
    app = create_app("testing", load_env=False)
    secret = f"manual-secret-{secrets.token_urlsafe(12)}"
    student = {
        "student_number": f"SYN-{secrets.token_hex(4)}",
        "name": f"Synthetic {secrets.token_hex(4)}",
        "gender": "Synthetic",
        "age": 19,
        "major": f"Major {secrets.token_hex(4)}",
        "year_level": "大一",
        "score": 91,
        "phone": f"199{secrets.randbelow(10**8):08d}",
        "email": f"manual-{secrets.token_hex(4)}@example.invalid",
    }
    caller_arguments = arguments(secret, student)

    if isinstance(caller_arguments, dict):
        app.logger.info(message, caller_arguments)
    else:
        app.logger.info(message, *caller_arguments)

    captured = capsys.readouterr()
    rendered = captured.err
    assert "--- Logging error ---" not in rendered
    assert secret not in rendered
    assert "[REDACTED]" in rendered or "[STUDENT_RECORD_REDACTED]" in rendered
    if not isinstance(caller_arguments, dict) and caller_arguments[0] == student:
        for value in student.values():
            assert str(value) not in rendered
    if isinstance(caller_arguments, dict):
        assert caller_arguments["password"] == secret
    else:
        assert caller_arguments[0] == secret or caller_arguments[0] == f"Bearer {secret}" or caller_arguments[0] == student


def test_exception_logging_formatting_errors_do_not_leak_original_arguments_to_stderr(capsys):
    app = create_app("testing", load_env=False)
    secret = f"manual-secret-{secrets.token_urlsafe(12)}"

    try:
        raise RuntimeError(f"password={secret}")
    except RuntimeError:
        app.logger.exception("failed with api_key=%s", secret)

    captured = capsys.readouterr()
    assert "--- Logging error ---" not in captured.err
    assert "Traceback" in captured.err
    assert secret not in captured.err
    assert "[REDACTED]" in captured.err


def test_configured_log_level_and_repeated_setup_preserve_unrelated_logger_state():
    third_party = logging.getLogger("third.party")
    third_party_handler = logging.NullHandler()
    third_party.addHandler(third_party_handler)
    third_party.setLevel(logging.WARNING)
    third_party.propagate = True
    third_party.disabled = False
    try:
        app_one = create_app("testing", config_overrides={"LOG_LEVEL": "DEBUG"}, load_env=False)
        app_two = create_app("testing", config_overrides={"LOG_LEVEL": "DEBUG"}, load_env=False)

        handlers = [
            handler for handler in app_two.logger.handlers
            if getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False)
        ]
        assert len(handlers) == 1
        assert handlers[0].level == logging.DEBUG
        assert third_party_handler in third_party.handlers
        assert third_party.level == logging.WARNING
        assert third_party.propagate is True
        assert third_party.disabled is False
        assert all(item.get("disable_existing_loggers") is False for item in app_two.extensions["logging_dictconfigs"])
        assert len([handler for handler in app_one.logger.handlers if getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False)]) == 1
    finally:
        third_party.removeHandler(third_party_handler)


def test_configuring_logging_preserves_all_unrelated_logger_state_and_handler_usability():
    logger = logging.getLogger("third.party.disabled")
    handler_stream = StringIO()
    handler = logging.StreamHandler(handler_stream)
    logger_filter = logging.Filter("third.party.disabled")
    logger.addHandler(handler)
    logger.addFilter(logger_filter)
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    logger.disabled = True
    try:
        create_app("testing", load_env=False)

        handler.emit(logging.LogRecord(logger.name, logging.ERROR, __file__, 1, "still usable", (), None))
        handler.flush()

        assert logger.disabled is True
        assert logger.level == logging.ERROR
        assert logger.propagate is False
        assert logger_filter in logger.filters
        assert handler in logger.handlers
        assert handler._closed is False
        assert "still usable" in handler_stream.getvalue()
    finally:
        logger.removeFilter(logger_filter)
        logger.removeHandler(handler)
        handler.close()


def test_setup_preserves_unmanaged_handlers_on_shared_application_loggers():
    app_logger = logging.getLogger("app")
    mcp_logger = logging.getLogger("mcp_server")
    app_handler = logging.StreamHandler(StringIO())
    mcp_handler = logging.StreamHandler(StringIO())
    app_logger.addHandler(app_handler)
    mcp_logger.addHandler(mcp_handler)
    try:
        create_app("testing", load_env=False)

        assert app_handler in app_logger.handlers
        assert mcp_handler in mcp_logger.handlers
        assert not getattr(app_handler, MANAGED_HANDLER_ATTRIBUTE, False)
        assert not getattr(mcp_handler, MANAGED_HANDLER_ATTRIBUTE, False)
    finally:
        app_logger.removeHandler(app_handler)
        mcp_logger.removeHandler(mcp_handler)


def test_configuring_logging_keeps_an_unmanaged_external_file_handler_open_and_usable(tmp_path):
    app_logger = logging.getLogger("app")
    log_path = tmp_path / "external.log"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    app_logger.addHandler(handler)
    try:
        app_logger.warning("before configuration")
        handler.flush()

        create_app("testing", load_env=False)

        app_logger.warning("after configuration")
        handler.flush()
        output = log_path.read_text(encoding="utf-8")

        assert handler in app_logger.handlers
        assert handler.stream is not None
        assert handler._closed is False
        assert "before configuration" in output
        assert "after configuration" in output
    finally:
        app_logger.removeHandler(handler)
        handler.close()


def test_file_logging_is_opt_in_and_rotates_in_an_isolated_test_path(tmp_path):
    disabled_directory = tmp_path / "disabled" / "logs"
    create_app("testing", config_overrides={"INSTANCE_PATH": str(disabled_directory.parent)}, load_env=False)
    assert not disabled_directory.exists()

    log_path = tmp_path / "enabled" / "app.log"
    app = create_app(
        "testing",
        config_overrides={
            "LOG_FILE_ENABLED": True,
            "LOG_TEST_FILE_PATH": str(log_path),
            "LOG_FILE_MAX_BYTES": 80,
            "LOG_FILE_BACKUP_COUNT": 2,
        },
        load_env=False,
    )
    for _ in range(12):
        app.logger.info("rollover payload %s", "x" * 40)
    for handler in app.logger.handlers:
        handler.flush()

    assert log_path.exists()
    assert list(log_path.parent.glob("app.log.*"))
    assert len(list(log_path.parent.glob("app.log.*"))) <= 2


def test_file_logging_uses_default_rotation_values_and_closes_managed_handlers(tmp_path):
    log_path = tmp_path / "defaults" / "app.log"
    app = create_app(
        "testing",
        config_overrides={"LOG_FILE_ENABLED": True, "LOG_TEST_FILE_PATH": str(log_path)},
        load_env=False,
    )
    handler = next(
        handler for handler in app.logger.handlers
        if getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False)
        and isinstance(handler, logging.handlers.RotatingFileHandler)
    )

    assert DEFAULT_LOG_MAX_BYTES == 5 * 1024 * 1024
    assert DEFAULT_LOG_BACKUP_COUNT == 5
    assert handler.maxBytes == DEFAULT_LOG_MAX_BYTES
    assert handler.backupCount == DEFAULT_LOG_BACKUP_COUNT
    _close_managed_handlers(app.logger)
    assert handler._closed is True
    log_path.unlink(missing_ok=True)
    assert not log_path.exists()


def test_testing_logging_rejects_a_runtime_file_path_without_a_test_only_path():
    app = create_app(
        "testing",
        config_overrides={
            "LOG_FILE_ENABLED": True,
            "LOG_FILE_PATH": "instance/logs/app.log",
        },
        load_env=False,
    )

    assert app.config["LOG_FILE_ENABLED"] is False
    assert app.config["LOG_FILE_PATH"] is None


@pytest.mark.parametrize(
    "test_path",
    [
        "instance/logs/app.log",
        "instance/logs/../logs/app.log",
        str((Path(__file__).resolve().parents[1] / "instance" / "logs" / "app.log").resolve()),
    ],
)
def test_testing_logging_rejects_test_paths_that_resolve_to_the_runtime_log_path(test_path):
    app = create_app(
        "testing",
        config_overrides={"LOG_FILE_ENABLED": True, "LOG_TEST_FILE_PATH": test_path},
        load_env=False,
    )

    assert app.config["LOG_FILE_ENABLED"] is False
    assert app.config["LOG_FILE_PATH"] is None


def test_unexpected_flask_exception_logs_a_traceback_without_changing_safe_response():
    app = create_app("testing", load_env=False)
    handler = next(handler for handler in app.logger.handlers if getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False))
    stream = StringIO()
    handler.setStream(stream)

    @app.get("/logging-error")
    def logging_error():
        raise RuntimeError("password=do-not-log")

    response = app.test_client().get("/logging-error")

    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == "internal_error"
    assert "Traceback" in stream.getvalue()
    assert "do-not-log" not in stream.getvalue()


@pytest.mark.parametrize("secret", [DEV_SECRET_KEY, PLACEHOLDER_SECRET_KEY])
def test_known_unsafe_secret_keys_are_redacted(secret):
    assert secret not in sanitize_log_value(f"safe context secret={secret}")


def test_unexpected_mcp_failure_logs_safe_traceback_and_keeps_stdout_clean(capsys):
    configure_mcp_logging({"LOG_LEVEL": "INFO"})
    try:
        raise RuntimeError("Authorization: Bearer mcp-secret")
    except RuntimeError as error:
        result = mcp_result_from_exception(error)

    captured = capsys.readouterr()
    assert result == {
        "success": False,
        "data": None,
        "message": "Internal server error",
        "error": {"code": "internal_error", "details": None},
        "meta": {},
    }
    assert "Traceback" in captured.err
    assert "mcp-secret" not in captured.err
    assert captured.out == ""


def test_mcp_logging_uses_a_managed_stderr_handler_without_stdout_output(capsys):
    configure_mcp_logging({"LOG_LEVEL": "INFO"})
    logger = logging.getLogger("mcp_server")
    handler = next(handler for handler in logger.handlers if getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False))

    logger.info("mcp startup")
    captured = capsys.readouterr()

    assert handler.stream is not sys.stdout
    assert "mcp startup" in captured.err
    assert captured.out == ""


def test_mcp_server_startup_uses_the_shared_logging_policy():
    from mcp_server.server import configure_server_logging

    configure_server_logging()

    assert any(
        getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False)
        for handler in logging.getLogger("mcp_server").handlers
    )


def test_mcp_main_configures_stderr_logging_before_its_startup_record(monkeypatch, capsys):
    import mcp_server.server as server_module

    class FakeServer:
        def run(self, *, transport):
            assert transport == "stdio"

    monkeypatch.setattr(server_module, "create_mcp_server", lambda: FakeServer())

    server_module.main()
    captured = capsys.readouterr()

    assert "Starting MCP server in stdio mode" in captured.err
    assert captured.out == ""


def test_mcp_module_entrypoint_emits_startup_log_to_stderr_without_touching_stdout():
    project_root = Path(__file__).resolve().parents[1]
    runtime_logs_path = project_root / "instance" / "logs"
    runtime_logs_existed = runtime_logs_path.exists()
    environment = os.environ.copy()
    environment.update({"LOG_FILE_ENABLED": "false", "LOG_LEVEL": "INFO"})
    environment.pop("PYTHONWARNINGS", None)

    stdin_holder = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert stdin_holder.stdout is not None
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mcp_server.server"],
            cwd=project_root,
            env=environment,
            stdin=stdin_holder.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    finally:
        stdin_holder.stdout.close()
        stdin_holder.wait(timeout=5)

    assert result.returncode == 0
    assert result.stdout == ""
    assert "Starting MCP server in stdio mode" in result.stderr
    assert "level=INFO" in result.stderr
    assert "logger=mcp_server.server" in result.stderr
    assert runtime_logs_path.exists() is runtime_logs_existed


def test_factory_configures_logging_before_startup_extensions(monkeypatch):
    import app as app_module

    observed: list[dict[str, object]] = []

    def capture_logging(flask_app):
        observed.append(dict(flask_app.extensions))

    monkeypatch.setattr(app_module, "configure_logging", capture_logging)

    app_module.create_app("testing", load_env=False)

    assert observed == [{}]
