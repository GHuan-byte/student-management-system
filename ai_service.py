from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from uuid import uuid4

import requests
from requests import RequestException

from mcp_client import call_mcp_tool, get_openai_tools

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False


load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
CHAT_HISTORY_FILE = os.path.join(DATA_DIR, "chat_history.json")

SYSTEM_PROMPT = """
你是学生信息管理系统中的 AI 助手。

规则：
1. 只要问题涉及数据库中的真实学生数据，必须优先调用 MCP 工具，不得猜测。
2. 当用户询问当前学生总人数时，优先调用 count_students。
3. 如果工具调用失败，必须明确说明查询失败，不能假装成功。
4. 你的回答应简洁、准确、使用中文。
""".strip()


def ensure_data_files() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    for file_path in (SESSIONS_FILE, CHAT_HISTORY_FILE):
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump([], file, ensure_ascii=False, indent=2)


def load_json(file_path: str) -> list[dict]:
    ensure_data_files()
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(file_path: str, data: list[dict]) -> None:
    ensure_data_files()
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def list_sessions() -> list[dict]:
    sessions = load_json(SESSIONS_FILE)
    return sorted(sessions, key=lambda item: item["updated_at"], reverse=True)


def create_session(title: str = "新建会话") -> dict:
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


def rename_session(session_id: str, title: str) -> bool:
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


def get_session_messages(session_id: str, limit: int = 100) -> list[dict]:
    messages = [item for item in load_json(CHAT_HISTORY_FILE) if item["session_id"] == session_id]
    return messages[-limit:] if limit else messages


def append_message(message: str, sender: str, session_id: str) -> dict:
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


def touch_session(session_id: str) -> None:
    sessions = load_json(SESSIONS_FILE)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for session in sessions:
        if session["id"] == session_id:
            session["updated_at"] = now
            break
    save_json(SESSIONS_FILE, sessions)


def build_chat_url(api_url: str) -> str:
    api_url = api_url.rstrip("/")
    if api_url.endswith("/chat/completions"):
        return api_url
    if api_url.endswith("/v1"):
        return f"{api_url}/chat/completions"
    return f"{api_url}/v1/chat/completions"


def should_bypass_proxy() -> bool:
    value = os.environ.get("OPENAI_BYPASS_PROXY", "true").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _build_request_kwargs(payload: dict) -> dict:
    api_url = os.environ.get("OPENAI_API_BASE", "").strip()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request_kwargs = {
        "url": build_chat_url(api_url),
        "json": payload,
        "headers": headers,
        "timeout": 90,
    }
    if should_bypass_proxy():
        request_kwargs["proxies"] = {"http": "", "https": ""}
    return request_kwargs


def _request_chat_completion(payload: dict) -> dict:
    request_kwargs = _build_request_kwargs(payload)
    response = requests.post(**request_kwargs)
    response.raise_for_status()
    return response.json()


def _extract_message(response_data: dict) -> dict:
    try:
        return response_data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("AI 服务返回了无法识别的数据格式") from exc


def _normalize_tool_arguments(raw_arguments: str | dict | None) -> dict[str, object]:
    if raw_arguments is None:
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not str(raw_arguments).strip():
        return {}
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise ValueError(f"工具参数不是有效 JSON: {raw_arguments}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("工具参数必须是 JSON 对象")
    return parsed


def generate_ai_reply(message: str, session_id: str) -> str:
    api_url = os.environ.get("OPENAI_API_BASE", "").strip()
    model = os.environ.get("OPENAI_MODEL", "").strip()

    if not api_url or not model:
        return "AI 助手基础对话能力已接入，但当前未配置大模型接口。请在 .env 中设置 OPENAI_API_BASE、OPENAI_API_KEY 和 OPENAI_MODEL。"

    history = get_session_messages(session_id, limit=12)
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    for item in history:
        role = "user" if item["sender"] == "user" else "assistant"
        messages.append({"role": role, "content": item["message"]})

    messages.append({"role": "user", "content": message})

    try:
        tools = get_openai_tools()
        first_response = _request_chat_completion(
            {
                "model": model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "stream": False,
            }
        )
        assistant_message = _extract_message(first_response)
        tool_calls = assistant_message.get("tool_calls") or []

        if not tool_calls:
            return assistant_message.get("content", "") or "AI 暂时没有返回内容。"

        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.get("content") or "",
                "tool_calls": tool_calls,
            }
        )

        for tool_call in tool_calls:
            function_info = tool_call.get("function", {})
            tool_name = function_info.get("name", "").strip()
            arguments = _normalize_tool_arguments(function_info.get("arguments"))

            logger.info("AI selected tool: %s", tool_name)
            logger.info("Tool arguments: %s", json.dumps(arguments, ensure_ascii=False))

            tool_result = call_mcp_tool(tool_name, arguments)
            logger.info(
                "Tool result status: tool=%s success=%s error=%s",
                tool_name,
                tool_result.get("success"),
                tool_result.get("error"),
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

        second_response = _request_chat_completion(
            {
                "model": model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "stream": False,
            }
        )
        final_message = _extract_message(second_response)
        return final_message.get("content", "") or "工具调用已完成，但模型没有返回最终文本。"
    except RequestException as exc:
        raise ValueError(f"AI 服务连接失败：{exc}") from exc
    except ValueError:
        raise
    except Exception as exc:
        logger.exception("AI tool-calling flow failed")
        raise ValueError(f"AI 服务执行失败：{exc}") from exc


def send_chat_message(message: str, session_id: str | None = None) -> dict:
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
