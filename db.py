import os
import sqlite3
from contextlib import closing
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "students.db")

STUDENT_FIELDS = [
    "student_number",
    "name",
    "gender",
    "age",
    "major",
    "grade",
    "phone",
    "email",
]


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with closing(get_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_number TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                gender TEXT NOT NULL,
                age INTEGER NOT NULL,
                major TEXT NOT NULL,
                grade TEXT NOT NULL,
                phone TEXT,
                email TEXT
            )
            """
        )
        try:
            connection.execute("ALTER TABLE students ADD COLUMN updated_at TEXT")
        except sqlite3.OperationalError:
            pass

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'teacher',
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


def row_to_dict(row):
    return dict(row) if row else None


def validate_student_payload(payload):
    required_fields = ["student_number", "name", "gender", "age", "major", "grade"]
    for field in required_fields:
        value = str(payload.get(field, "")).strip()
        if not value:
            raise ValueError(f"{field} 不能为空")

    try:
        age = int(payload.get("age", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("age 必须为数字") from exc

    if age <= 0:
        raise ValueError("age 必须大于 0")


def normalize_student_payload(payload):
    validate_student_payload(payload)
    return {
        "student_number": str(payload.get("student_number", "")).strip(),
        "name": str(payload.get("name", "")).strip(),
        "gender": str(payload.get("gender", "")).strip(),
        "age": int(payload.get("age")),
        "major": str(payload.get("major", "")).strip(),
        "grade": str(payload.get("grade", "")).strip(),
        "phone": str(payload.get("phone", "")).strip(),
        "email": str(payload.get("email", "")).strip(),
    }


SORT_WHITELIST = {
    "id", "student_number", "name", "gender", "age", "major", "grade",
}

NUMERIC_SORT_FIELDS = {"id", "age", "grade"}


def _build_order_clause(sort_by: str, sort_order: str) -> str:
    sort_by = sort_by.strip().lower() if sort_by else "id"
    sort_order = sort_order.strip().lower() if sort_order else "asc"

    if sort_by not in SORT_WHITELIST:
        sort_by = "id"
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"

    if sort_by in NUMERIC_SORT_FIELDS:
        return f"ORDER BY CAST({sort_by} AS INTEGER) {sort_order}"
    return f"ORDER BY {sort_by} {sort_order}"


def list_students(
    sort_by: str = "id",
    sort_order: str = "asc",
    limit=None,
    offset=0,
):
    order_clause = _build_order_clause(
        sort_by,
        sort_order,
    )

    sql = f"""
        SELECT
            id,
            student_number,
            name,
            gender,
            age,
            major,
            grade,
            phone,
            email,
            updated_at
        FROM students
        {order_clause}
    """

    params = []

    if limit is not None:
        limit = max(int(limit), 1)
        offset = max(int(offset), 0)

        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    with closing(get_connection()) as connection:
        rows = connection.execute(
            sql,
            params,
        ).fetchall()

    return [row_to_dict(row) for row in rows]



def search_students(
    keyword,
    sort_by: str = "id",
    sort_order: str = "asc",
    limit=None,
    offset=0,
):
    order_clause = _build_order_clause(
        sort_by,
        sort_order,
    )

    query = f"%{str(keyword).strip()}%"

    sql = f"""
        SELECT
            id,
            student_number,
            name,
            gender,
            age,
            major,
            grade,
            phone,
            email,
            updated_at
        FROM students
        WHERE student_number LIKE ?
           OR name LIKE ?
           OR gender LIKE ?
           OR major LIKE ?
           OR grade LIKE ?
           OR phone LIKE ?
           OR email LIKE ?
        {order_clause}
    """

    params = [
        query,
        query,
        query,
        query,
        query,
        query,
        query,
    ]

    if limit is not None:
        limit = max(int(limit), 1)
        offset = max(int(offset), 0)

        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    with closing(get_connection()) as connection:
        rows = connection.execute(
            sql,
            params,
        ).fetchall()

    return [row_to_dict(row) for row in rows]

def count_students(keyword=""):
    keyword = str(keyword or "").strip()

    with closing(get_connection()) as connection:
        if not keyword:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM students"
            ).fetchone()

            return int(row["total"])

        query = f"%{keyword}%"

        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM students
            WHERE student_number LIKE ?
               OR name LIKE ?
               OR gender LIKE ?
               OR major LIKE ?
               OR grade LIKE ?
               OR phone LIKE ?
               OR email LIKE ?
            """,
            (
                query,
                query,
                query,
                query,
                query,
                query,
                query,
            ),
        ).fetchone()

    return int(row["total"])

def get_student_by_id(student_id):
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT id, student_number, name, gender, age, major, grade, phone, email, updated_at
            FROM students
            WHERE id = ?
            """,
            (student_id,),
        ).fetchone()
    return row_to_dict(row)


def get_student_by_number(student_number):
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT id, student_number, name, gender, age, major, grade, phone, email, updated_at
            FROM students
            WHERE student_number = ?
            """,
            (str(student_number).strip(),),
        ).fetchone()
    return row_to_dict(row)


def add_student(payload):
    data = normalize_student_payload(payload)
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO students (student_number, name, gender, age, major, grade, phone, email, updated_at)
            VALUES (:student_number, :name, :gender, :age, :major, :grade, :phone, :email, :updated_at)
            """,
            data,
        )
        connection.commit()
        student_id = cursor.lastrowid
    return get_student_by_id(student_id)


def update_student(student_id, payload):
    if not get_student_by_id(student_id):
        return None

    data = normalize_student_payload(payload)
    data["id"] = student_id
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with closing(get_connection()) as connection:
        connection.execute(
            """
            UPDATE students
            SET student_number = :student_number,
                name = :name,
                gender = :gender,
                age = :age,
                major = :major,
                grade = :grade,
                phone = :phone,
                email = :email,
                updated_at = :updated_at
            WHERE id = :id
            """,
            data,
        )
        connection.commit()
    return get_student_by_id(student_id)


def upsert_student(payload):
    student_number = str(payload.get("student_number", "")).strip()
    existing = get_student_by_number(student_number) if student_number else None
    if existing:
        return "updated", update_student(existing["id"], payload)
    return "created", add_student(payload)


def delete_student(student_id):
    with closing(get_connection()) as connection:
        cursor = connection.execute("DELETE FROM students WHERE id = ?", (student_id,))
        connection.commit()
    return cursor.rowcount > 0


def batch_delete_students(student_ids):
    ids = [int(student_id) for student_id in student_ids]
    if not ids:
        return 0

    placeholders = ",".join("?" for _ in ids)
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            f"DELETE FROM students WHERE id IN ({placeholders})",
            ids,
        )
        connection.commit()
    return cursor.rowcount


def get_student_stats():
    with closing(get_connection()) as connection:
        total = connection.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        majors = connection.execute("SELECT COUNT(DISTINCT major) FROM students").fetchone()[0]
        grades = connection.execute("SELECT COUNT(DISTINCT grade) FROM students").fetchone()[0]
        latest = connection.execute(
            "SELECT name, updated_at FROM students ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return {
        "total_students": total,
        "major_count": majors,
        "grade_count": grades,
        "latest_student_name": latest["name"] if latest else "暂无数据",
        "latest_student_time": latest["updated_at"] if latest and latest["updated_at"] else "暂无记录",
    }


# ──────────────────────────────────────────
# 用户 (users) 表操作
# ──────────────────────────────────────────


def get_user_by_id(user_id: int) -> dict | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            "SELECT id, username, password_hash, role, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return row_to_dict(row)


def get_user_by_username(username: str) -> dict | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            "SELECT id, username, password_hash, role, created_at FROM users WHERE username = ?",
            (str(username).strip(),),
        ).fetchone()
    return row_to_dict(row)


def create_user(username: str, password_hash: str, role: str = "teacher") -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (str(username).strip(), password_hash, role, now),
        )
        connection.commit()
        return get_user_by_id(cursor.lastrowid)


def list_users() -> list[dict]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id ASC"
        ).fetchall()
    return [row_to_dict(row) for row in rows]
