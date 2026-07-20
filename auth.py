"""登录验证与权限管理模块"""

from __future__ import annotations

import logging
from functools import wraps

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from db import create_user, get_user_by_username, list_users

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def init_default_admin() -> None:
    """首次启动时创建默认管理员账户（如果还没有任何用户）。"""
    users = list_users()
    if users:
        return
    password_hash = generate_password_hash(DEFAULT_ADMIN_PASSWORD)
    user = create_user(DEFAULT_ADMIN_USERNAME, password_hash, role="admin")
    logger.info("默认管理员已创建: username=%s, role=%s", user["username"], user["role"])


def login_required(func):
    """需要登录才能访问的装饰器。"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"success": False, "message": "请先登录"}), 401
        return func(*args, **kwargs)

    return wrapper


def role_required(*roles: str):
    """需要特定角色才能访问的装饰器。

    用法::

        @role_required("admin")
        @role_required("admin", "teacher")
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return jsonify({"success": False, "message": "请先登录"}), 401
            if session.get("role") not in roles:
                return jsonify({"success": False, "message": "权限不足"}), 403
            return func(*args, **kwargs)

        return wrapper

    return decorator


# ──────────────────────────────────────────
# API 路由
# ──────────────────────────────────────────


@auth_bp.route("/login", methods=["POST"])
def api_login():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "请求数据不能为空"}), 400

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()

    if not username or not password:
        return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400

    user = get_user_by_username(username)
    if not user:
        return jsonify({"success": False, "message": "用户名或密码错误"}), 401

    if not check_password_hash(user["password_hash"], password):
        return jsonify({"success": False, "message": "用户名或密码错误"}), 401

    session.permanent = True
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]

    logger.info("用户登录成功: username=%s, role=%s", user["username"], user["role"])

    return jsonify({
        "success": True,
        "message": "登录成功",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
        },
    })


@auth_bp.route("/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True, "message": "已退出登录"})


@auth_bp.route("/me", methods=["GET"])
def api_me():
    """获取当前登录用户信息。"""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "未登录"}), 401
    return jsonify({
        "success": True,
        "user": {
            "id": session["user_id"],
            "username": session["username"],
            "role": session["role"],
        },
    })
