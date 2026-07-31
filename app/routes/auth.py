"""Login and logout routes."""

from __future__ import annotations

from flask import Blueprint, g, redirect, render_template, request, url_for

from app.auth import login_user, logout_user, safe_redirect_target
from app.logging_config import log_security_event


auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/login")
def login():
    if getattr(g, "current_user", None) is not None:
        return redirect(url_for("pages.dashboard_page"))
    return render_template("login.html", error="", next_url=request.args.get("next", ""))


@auth_bp.post("/login")
def login_post():
    from flask import current_app

    user_service = current_app.extensions["user_service_factory"]()
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    auth_result = user_service.authenticate_with_result(username, password)
    user = auth_result.user
    if auth_result.reason == "inactive_account" and user is not None:
        log_security_event(
            "inactive_account_rejected",
            metadata={
                "user_id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "outcome": "denied",
                "reason": "inactive_account",
            },
        )
        return render_template("login.html", error="用户名或密码无效", next_url=request.args.get("next", "")), 401
    if user is None:
        log_security_event(
            "login_failed",
            metadata={
                "username": str(username).strip().lower(),
                "outcome": "denied",
                "reason": "invalid_credentials",
            },
        )
        return render_template("login.html", error="用户名或密码无效", next_url=request.args.get("next", "")), 401

    login_user(user)
    user_service.record_login(user["id"])
    log_security_event(
        "login_succeeded",
        metadata={"user_id": user["id"], "username": user["username"], "role": user["role"], "outcome": "succeeded"},
    )
    return redirect(safe_redirect_target(request.args.get("next")))


@auth_bp.post("/logout")
def logout():
    user = getattr(g, "current_user", None)
    if user is not None:
        log_security_event(
            "logout_succeeded",
            metadata={"user_id": user["id"], "username": user["username"], "role": user["role"], "outcome": "succeeded"},
        )
    logout_user()
    return redirect(url_for("auth.login"))
