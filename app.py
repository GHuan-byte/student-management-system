import io
import logging
import os
from datetime import datetime
from functools import wraps

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file

from ai_service import (
    create_session,
    get_session_messages,
    list_sessions,
    rename_session,
    send_chat_message,
)
from db import (
    STUDENT_FIELDS,
    add_student,
    batch_delete_students,
    delete_student,
    get_student_by_id,
    get_student_stats,
    init_db,
    list_students,
    search_students,
    update_student,
    upsert_student,
)


app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

IMPORT_COLUMN_ALIASES = {
    "student_number": "student_number",
    "学号": "student_number",
    "name": "name",
    "姓名": "name",
    "gender": "gender",
    "性别": "gender",
    "age": "age",
    "年龄": "age",
    "major": "major",
    "专业": "major",
    "grade": "grade",
    "年级": "grade",
    "成绩": "grade",
    "phone": "phone",
    "电话": "phone",
    "手机号": "phone",
    "email": "email",
    "邮箱": "email",
}
EXPORT_COLUMNS = ["id", *STUDENT_FIELDS, "updated_at"]


def handle_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc)}), 400
        except Exception as exc:
            logger.exception("请求处理失败: %s", exc)
            return jsonify(
                {
                    "success": False,
                    "message": "服务器内部错误",
                    "error": str(exc),
                }
            ), 500

    return wrapper


@app.before_request
def initialize_database():
    init_db()


def normalize_import_dataframe(dataframe):
    rename_map = {}
    for column in dataframe.columns:
        key = IMPORT_COLUMN_ALIASES.get(str(column).strip())
        if key:
            rename_map[column] = key

    dataframe = dataframe.rename(columns=rename_map)
    missing = [field for field in ["student_number", "name", "gender", "age", "major", "grade"] if field not in dataframe.columns]
    if missing:
        raise ValueError(f"导入文件缺少必要列: {', '.join(missing)}")

    normalized = dataframe.copy()
    for field in STUDENT_FIELDS:
        if field not in normalized.columns:
            normalized[field] = ""

    normalized = normalized[STUDENT_FIELDS].fillna("")
    for field in STUDENT_FIELDS:
        normalized[field] = normalized[field].map(lambda value: str(value).strip())
    return normalized


def export_students_dataframe(keyword=""):
    students = search_students(keyword) if keyword else list_students()
    rows = []
    for student in students:
        rows.append({column: student.get(column, "") for column in EXPORT_COLUMNS})
    return pd.DataFrame(rows, columns=EXPORT_COLUMNS)


@app.route("/")
def index_page():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template(
        "index.html",
        stats=get_student_stats(),
        current_time=current_time,
    )


@app.route("/students")
def students_page():
    return render_template("students.html")


@app.route("/api/students", methods=["GET"])
@handle_errors
def api_get_students():
    keyword = request.args.get("keyword", "").strip()
    sort_by = request.args.get("sort_by", "id").strip()
    sort_order = request.args.get("sort_order", "asc").strip()
    if keyword:
        students = search_students(keyword, sort_by=sort_by, sort_order=sort_order)
    else:
        students = list_students(sort_by=sort_by, sort_order=sort_order)
    return jsonify(
        {
            "success": True,
            "data": students,
            "count": len(students),
        }
    )


@app.route("/api/students/<int:student_id>", methods=["GET"])
@handle_errors
def api_get_student(student_id):
    student = get_student_by_id(student_id)
    if not student:
        return jsonify({"success": False, "message": "学生不存在"}), 404
    return jsonify({"success": True, "data": student})


@app.route("/api/students", methods=["POST"])
@handle_errors
def api_create_student():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "请求数据不能为空"}), 400

    student = add_student(data)
    return jsonify({"success": True, "message": "学生添加成功", "data": student}), 201


@app.route("/api/students/<int:student_id>", methods=["PUT"])
@handle_errors
def api_update_student(student_id):
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "请求数据不能为空"}), 400

    student = update_student(student_id, data)
    if not student:
        return jsonify({"success": False, "message": "学生不存在"}), 404

    return jsonify({"success": True, "message": "学生信息更新成功", "data": student})


@app.route("/api/students/<int:student_id>", methods=["DELETE"])
@handle_errors
def api_delete_student(student_id):
    deleted = delete_student(student_id)
    if not deleted:
        return jsonify({"success": False, "message": "学生不存在"}), 404
    return jsonify({"success": True, "message": "学生删除成功"})


@app.route("/api/students/batch-delete", methods=["DELETE"])
@handle_errors
def api_batch_delete_students():
    data = request.get_json() or {}
    student_ids = data.get("ids", [])
    if not student_ids:
        return jsonify({"success": False, "message": "请选择要删除的学生"}), 400

    deleted_count = batch_delete_students(student_ids)
    return jsonify(
        {
            "success": True,
            "message": f"已删除 {deleted_count} 条学生记录",
            "deleted_count": deleted_count,
        }
    )


@app.route("/api/students/import", methods=["POST"])
@handle_errors
def api_import_students():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"success": False, "message": "请选择要导入的文件"}), 400

    filename = upload.filename.lower()
    if filename.endswith(".csv"):
        dataframe = pd.read_csv(upload, dtype=str)
    elif filename.endswith(".xlsx") or filename.endswith(".xls"):
        dataframe = pd.read_excel(upload, dtype=str)
    else:
        return jsonify({"success": False, "message": "仅支持导入 CSV 或 Excel 文件"}), 400

    normalized = normalize_import_dataframe(dataframe)
    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors = []

    for index, row in normalized.iterrows():
        payload = row.to_dict()
        try:
            action, _student = upsert_student(payload)
            if action == "created":
                created_count += 1
            else:
                updated_count += 1
        except Exception as exc:
            skipped_count += 1
            errors.append(f"第 {index + 2} 行: {exc}")

    message = f"导入完成，新增 {created_count} 条，更新 {updated_count} 条"
    if skipped_count:
        message += f"，跳过 {skipped_count} 条"

    return jsonify(
        {
            "success": True,
            "message": message,
            "created_count": created_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "errors": errors[:10],
        }
    )


@app.route("/api/students/export", methods=["GET"])
@handle_errors
def api_export_students():
    file_format = request.args.get("format", "csv").strip().lower()
    keyword = request.args.get("keyword", "").strip()
    dataframe = export_students_dataframe(keyword)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if file_format == "csv":
        buffer = io.BytesIO()
        buffer.write(dataframe.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"))
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"students_{timestamp}.csv",
            mimetype="text/csv",
        )

    if file_format == "xlsx":
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Students")
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"students_{timestamp}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    return jsonify({"success": False, "message": "导出格式仅支持 csv 或 xlsx"}), 400


@app.route("/api/chat", methods=["POST"])
@handle_errors
def api_chat():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "无效的请求数据"}), 400

    user_message = data.get("message", "").strip()
    session_id = data.get("session_id")

    if not user_message:
        return jsonify({"success": False, "message": "消息不能为空"}), 400
    if len(user_message) > 500:
        return jsonify({"success": False, "message": "消息不能超过 500 个字符"}), 400

    result = send_chat_message(user_message, session_id=session_id)
    return jsonify({"success": True, **result})


@app.route("/api/sessions", methods=["GET"])
@handle_errors
def api_get_sessions():
    return jsonify(list_sessions())


@app.route("/api/sessions", methods=["POST"])
@handle_errors
def api_create_session():
    data = request.get_json() or {}
    title = data.get("title", "新建会话")
    session = create_session(title=title)
    return jsonify(session), 201


@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
@handle_errors
def api_get_session_messages(session_id):
    limit = request.args.get("limit", 100, type=int)
    messages = get_session_messages(session_id, limit=limit)
    return jsonify(messages)


@app.route("/api/sessions/<session_id>/rename", methods=["PUT"])
@handle_errors
def api_rename_session(session_id):
    data = request.get_json() or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"success": False, "message": "标题不能为空"}), 400

    if not rename_session(session_id, title):
        return jsonify({"success": False, "message": "会话不存在"}), 404
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "true").lower() == "true",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
    )
