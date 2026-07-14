import logging
import os
from datetime import datetime
from functools import wraps

from flask import Flask, jsonify, render_template, request

from ai_service import (
    create_session,
    get_session_messages,
    list_sessions,
    rename_session,
    send_chat_message,
)
from db import (
    add_student,
    delete_student,
    get_student_by_id,
    get_student_stats,
    init_db,
    list_students,
    search_students,
    update_student,
)


# 创建 Flask 应用
app = Flask(__name__)


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# 统一异常处理装饰器
def handle_errors(func):
    """捕获接口异常，并统一返回 JSON 格式的错误信息"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc)}), 400
        except Exception as exc:
            logger.exception("请求处理失败: %s", exc)
            return jsonify({
                "success": False,
                "message": "服务器内部错误",
                "error": str(exc),
            }), 500

    return wrapper


# 每次请求前初始化数据库
@app.before_request
def initialize_database():
    """确保学生数据库和基础表结构已经创建"""
    init_db()


# =========================
# 页面路由
# =========================

# 首页路由
@app.route("/")
def index_page():
    """渲染系统首页，并传入基础统计数据和服务器当前时间"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template(
        "index.html",
        stats=get_student_stats(),
        current_time=current_time,
    )


# 学生管理页面路由
@app.route("/students")
def students_page():
    """渲染学生信息管理页面"""
    return render_template("students.html")


# =========================
# 学生信息 API 路由
# =========================

# API - 获取学生列表
@app.route("/api/students", methods=["GET"])
@handle_errors
def api_get_students():
    """获取学生列表，支持通过 keyword 参数进行搜索"""
    keyword = request.args.get("keyword", "").strip()

    if keyword:
        students = search_students(keyword)
    else:
        students = list_students()

    return jsonify({
        "success": True,
        "data": students,
        "count": len(students),
    })


# API - 获取单个学生详情
@app.route("/api/students/<int:student_id>", methods=["GET"])
@handle_errors
def api_get_student(student_id):
    """根据学生 ID 获取单个学生信息"""
    student = get_student_by_id(student_id)

    if not student:
        return jsonify({
            "success": False,
            "message": "学生不存在",
        }), 404

    return jsonify({
        "success": True,
        "data": student,
    })


# API - 新增学生
@app.route("/api/students", methods=["POST"])
@handle_errors
def api_create_student():
    """新增一条学生信息"""
    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "请求数据不能为空",
        }), 400

    student = add_student(data)

    return jsonify({
        "success": True,
        "message": "学生添加成功",
        "data": student,
    }), 201


# API - 修改学生
@app.route("/api/students/<int:student_id>", methods=["PUT"])
@handle_errors
def api_update_student(student_id):
    """根据学生 ID 修改学生信息"""
    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "请求数据不能为空",
        }), 400

    student = update_student(student_id, data)

    if not student:
        return jsonify({
            "success": False,
            "message": "学生不存在",
        }), 404

    return jsonify({
        "success": True,
        "message": "学生信息更新成功",
        "data": student,
    })


# API - 删除学生
@app.route("/api/students/<int:student_id>", methods=["DELETE"])
@handle_errors
def api_delete_student(student_id):
    """根据学生 ID 删除学生信息"""
    deleted = delete_student(student_id)

    if not deleted:
        return jsonify({
            "success": False,
            "message": "学生不存在",
        }), 404

    return jsonify({
        "success": True,
        "message": "学生删除成功",
    })


# =========================
# AI 助手 API 路由
# =========================

# API - 发送聊天消息
@app.route("/api/chat", methods=["POST"])
@handle_errors
def api_chat():
    """处理 AI 助手聊天消息，支持基于 session_id 的多轮对话"""
    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "无效的请求数据",
        }), 400

    user_message = data.get("message", "").strip()
    session_id = data.get("session_id")

    if not user_message:
        return jsonify({
            "success": False,
            "message": "消息不能为空",
        }), 400

    if len(user_message) > 500:
        return jsonify({
            "success": False,
            "message": "消息不能超过500个字符",
        }), 400

    # 发送消息并保存会话记录
    result = send_chat_message(user_message, session_id=session_id)

    return jsonify({
        "success": True,
        **result,
    })


# =========================
# 会话管理 API 路由
# =========================

# API - 获取会话列表
@app.route("/api/sessions", methods=["GET"])
@handle_errors
def api_get_sessions():
    """获取所有 AI 助手会话列表"""
    return jsonify(list_sessions())


# API - 创建会话
@app.route("/api/sessions", methods=["POST"])
@handle_errors
def api_create_session():
    """创建新的 AI 助手会话"""
    data = request.get_json() or {}
    title = data.get("title", "新建会话")
    session = create_session(title=title)

    return jsonify(session), 201


# API - 获取指定会话消息
@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
@handle_errors
def api_get_session_messages(session_id):
    """获取指定会话下的历史消息"""
    limit = request.args.get("limit", 100, type=int)
    messages = get_session_messages(session_id, limit=limit)

    return jsonify(messages)


# API - 重命名会话
@app.route("/api/sessions/<session_id>/rename", methods=["PUT"])
@handle_errors
def api_rename_session(session_id):
    """根据 session_id 修改会话标题"""
    data = request.get_json() or {}
    title = data.get("title", "").strip()

    if not title:
        return jsonify({
            "success": False,
            "message": "标题不能为空",
        }), 400

    if not rename_session(session_id, title):
        return jsonify({
            "success": False,
            "message": "会话不存在",
        }), 404

    return jsonify({
        "success": True,
    })


# =========================
# 应用启动入口
# =========================

if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "true").lower() == "true",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
    )
