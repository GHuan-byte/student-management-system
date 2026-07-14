import os
import sqlite3
from contextlib import closing


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
    except (TypeError, ValueError):
        raise ValueError("age 必须为数字")

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


def list_students():
    with closing(get_connection()) as connection:
        rows = connection.execute(
            "SELECT id, student_number, name, gender, age, major, grade, phone, email FROM students ORDER BY id DESC"
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def search_students(keyword):
    query = f"%{keyword.strip()}%"
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT id, student_number, name, gender, age, major, grade, phone, email
            FROM students
            WHERE student_number LIKE ?
               OR name LIKE ?
               OR gender LIKE ?
               OR major LIKE ?
               OR grade LIKE ?
               OR phone LIKE ?
               OR email LIKE ?
            ORDER BY id DESC
            """,
            (query, query, query, query, query, query, query),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def get_student_by_id(student_id):
    with closing(get_connection()) as connection:
        row = connection.execute(
            "SELECT id, student_number, name, gender, age, major, grade, phone, email FROM students WHERE id = ?",
            (student_id,),
        ).fetchone()
    return row_to_dict(row)


def add_student(payload):
    data = normalize_student_payload(payload)
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO students (student_number, name, gender, age, major, grade, phone, email)
            VALUES (:student_number, :name, :gender, :age, :major, :grade, :phone, :email)
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
                email = :email
            WHERE id = :id
            """,
            data,
        )
        connection.commit()
    return get_student_by_id(student_id)


def delete_student(student_id):
    with closing(get_connection()) as connection:
        cursor = connection.execute("DELETE FROM students WHERE id = ?", (student_id,))
        connection.commit()
    return cursor.rowcount > 0


def get_student_stats():
    with closing(get_connection()) as connection:
        total = connection.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        majors = connection.execute("SELECT COUNT(DISTINCT major) FROM students").fetchone()[0]
        grades = connection.execute("SELECT COUNT(DISTINCT grade) FROM students").fetchone()[0]
        latest = connection.execute(
            "SELECT name FROM students ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return {
        "total_students": total,
        "major_count": majors,
        "grade_count": grades,
        "latest_student_name": latest["name"] if latest else "暂无数据",
    }
