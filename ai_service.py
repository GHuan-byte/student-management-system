import json
import os
from datetime import datetime
from uuid import uuid4

import requests
from requests import RequestException

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False


load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
CHAT_HISTORY_FILE = os.path.join(DATA_DIR, "chat_history.json")


def ensure_data_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    for file_path in (SESSIONS_FILE, CHAT_HISTORY_FILE):
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump([], file, ensure_ascii=False, indent=2)


def load_json(file_path):
    ensure_data_files()
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(file_path, data):
    ensure_data_files()
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def list_sessions():
    sessions = load_json(SESSIONS_FILE)
    return sorted(sessions, key=lambda item: item["updated_at"], reverse=True)


def create_session(title="新建会话"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session = {
        "id": uuid4().hex,
        "title": title,
        "created_at": now,
        "updated_at": now,
    }
    sessions = load_json(SESSIONS_FILE)
    sessions.append(session)
    save_json(SESSIONS_FILE, sessions)
    return session


def rename_session(session_id, title):
    sessions = load_json(SESSIONS_FILE)
    updated = False
    for session in sessions:
        if session["id"] == session_id:
            session["title"] = title
            session["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updated = True
            break
    if updated:
        save_json(SESSIONS_FILE, sessions)
    return updated


def get_session_messages(session_id, limit=100):
    messages = [item for item in load_json(CHAT_HISTORY_FILE) if item["session_id"] == session_id]
    return messages[-limit:] if limit else messages


def append_message(message, sender, session_id):
    history = load_json(CHAT_HISTORY_FILE)
    entry = {
        "id": uuid4().hex,
        "message": message,
        "sender": sender,
        "session_id": session_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    history.append(entry)
    save_json(CHAT_HISTORY_FILE, history[-1000:])
    return entry


def touch_session(session_id):
    sessions = load_json(SESSIONS_FILE)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for session in sessions:
        if session["id"] == session_id:
            session["updated_at"] = now
            break
    save_json(SESSIONS_FILE, sessions)


def build_chat_url(api_url):
    api_url = api_url.rstrip("/")
    if api_url.endswith("/chat/completions"):
        return api_url
    if api_url.endswith("/v1"):
        return f"{api_url}/chat/completions"
    return f"{api_url}/v1/chat/completions"


def should_bypass_proxy():
    value = os.environ.get("OPENAI_BYPASS_PROXY", "true").strip().lower()
    return value in {"1", "true", "yes", "on"}


def generate_ai_reply(message, session_id):
    api_url = os.environ.get("OPENAI_API_BASE", "").strip()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "").strip()

    if not api_url or not model:
        return "AI 助手基础版本已接通会话逻辑，但当前未配置 API。请在 .env 中设置 OPENAI_API_BASE、OPENAI_API_KEY 和 OPENAI_MODEL。"

    history = get_session_messages(session_id, limit=12)
    messages = [
        {
            "role": "system",
            "content": "你是学生信息管理系统中的 AI 助手，请用简洁、清晰的中文回答用户问题。",
        }
    ]
    for item in history:
        role = "user" if item["sender"] == "user" else "assistant"
        messages.append({"role": role, "content": item["message"]})
    messages.append({"role": "user", "content": message})

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        request_kwargs = {
            "json": {"model": model, "messages": messages, "stream": False},
            "headers": headers,
            "timeout": 90,
        }
        if should_bypass_proxy():
            request_kwargs["proxies"] = {"http": "", "https": ""}

        response = requests.post(build_chat_url(api_url), **request_kwargs)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except RequestException as exc:
        raise ValueError(f"AI 服务连接失败：{exc}") from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError("AI 服务返回了无法识别的数据格式") from exc


def send_chat_message(message, session_id=None):
    if not session_id:
        session_id = create_session()["id"]

    user_entry = append_message(message, "user", session_id)
    sessions = load_json(SESSIONS_FILE)
    for session in sessions:
        if session["id"] == session_id and session["title"] == "新建会话":
            session["title"] = message[:20] + ("..." if len(message) > 20 else "")
            break
    save_json(SESSIONS_FILE, sessions)

    reply = generate_ai_reply(message, session_id)
    append_message(reply, "assistant", session_id)
    touch_session(session_id)

    return {
        "session_id": session_id,
        "user_message": user_entry["message"],
        "bot_reply": reply,
    }
