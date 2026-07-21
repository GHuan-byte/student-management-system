# Legacy Audit — Student Management System V1

> 审计日期：2026-07-21
> 目标项目：`D:\Python\student-management-system`

---

## 1. 总体架构

**模式：扁平单体 Flask 应用** — 没有分层架构。

```
student-management-system/
├── app.py              # Flask 应用 — 路由、错误处理、导入/导出
├── db.py               # 数据库操作 + 数据验证 + 用户操作（混合）
├── auth.py             # Flask Blueprint — 登录/登出/会话管理
├── ai_service.py       # AI 聊天逻辑 + MCP 工具编排
├── mcp_client.py       # MCP stdio 客户端
├── run.py              # 空文件（无内容）
├── mcp_server/
│   ├── __init__.py     # 空文件
│   ├── server.py       # FastMCP 服务器（stdio 传输）
│   └── student_tools.py # MCP 工具注册（5 个只读 + 3 个写入）
├── templates/          # Jinja2 模板
│   ├── base.html       # 基础布局（导航栏 + AI 侧边栏）
│   ├── index.html      # 仪表盘
│   ├── login.html      # 登录页
│   └── students.html   # 学生列表页
├── static/
│   ├── css/
│   │   └── style.css   # 全局样式
│   └── js/
│       ├── login.js    # 登录逻辑
│       ├── students.js # 学生列表全部逻辑（~500 行）
│       └── ai_assistant.js # AI 侧边栏（~250 行）
├── data/
│   ├── students.db     # SQLite 数据库文件
│   ├── sessions.json   # AI 会话元数据
│   └── chat_history.json # AI 聊天消息历史
├── exports/            # 导出的 CSV 文件
├── uploads/            # 导入的上传文件
├── logs/               # 应用日志
├── requirements.txt    # pip 依赖
├── pyproject.toml      # uv 依赖 + MCP 脚本入口
└── .env                # 环境变量（已 gitignore）
```

**依赖：** 同时使用 `requirements.txt`（pip）和 `pyproject.toml`（uv）。Python >= 3.12。

---

## 2. 数据库 Schema

### `students` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PK, AUTOINCREMENT | 内部标识 |
| `student_number` | TEXT | NOT NULL, UNIQUE | 学号 |
| `name` | TEXT | NOT NULL | 姓名 |
| `gender` | TEXT | NOT NULL | 性别 |
| `age` | INTEGER | NOT NULL | 年龄 |
| `major` | TEXT | NOT NULL | 专业 |
| `grade` | TEXT | NOT NULL | 年级（如 "2023级"） |
| `phone` | TEXT | NULLABLE | 电话 |
| `email` | TEXT | NULLABLE | 邮箱 |
| `updated_at` | TEXT | NULLABLE | 后期 ALTER TABLE 添加 |

> **注意：** 无 `created_at` 字段。`updated_at` 是通过 `ALTER TABLE ADD COLUMN` 后期添加的，通过 try/except 实现。

### `users` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PK, AUTOINCREMENT | 内部标识 |
| `username` | TEXT | NOT NULL, UNIQUE | 用户名 |
| `password_hash` | TEXT | NOT NULL | 密码哈希（Werkzeug） |
| `role` | TEXT | NOT NULL, DEFAULT 'teacher' | 角色 |
| `created_at` | TEXT | NOT NULL | 创建时间 |

### 学生字段白名单（用于验证和列表）

```python
STUDENT_FIELDS = [
    'student_number', 'name', 'gender', 'age', 'major', 'grade', 'phone', 'email'
]
```

### 排序白名单

```python
SORT_WHITELIST = {'id', 'student_number', 'name', 'gender', 'age', 'major', 'grade'}
```

> 数字字段（`id`, `age`, `grade`）使用 `CAST(... AS INTEGER)` 排序。

---

## 3. 所有路由

### 页面路由

| 方法 | 路径 | 函数 | 认证 |
|------|------|------|------|
| GET | `/` | `index_page` | 无 |
| GET | `/login` | `login_page` | 无 |
| GET | `/students` | `students_page` | `@login_required` |

### API 路由

| 方法 | 路径 | 函数 | 认证 |
|------|------|------|------|
| POST | `/api/auth/login` | `api_login` | 无 |
| POST | `/api/auth/logout` | `api_logout` | 无 |
| GET | `/api/auth/me` | `api_me` | 无（未登录返回 401） |
| GET | `/api/students` | `api_get_students` | `@login_required` |
| GET | `/api/students/<id>` | `api_get_student` | `@login_required` |
| POST | `/api/students` | `api_create_student` | `@login_required` |
| PUT | `/api/students/<id>` | `api_update_student` | `@login_required` |
| DELETE | `/api/students/<id>` | `api_delete_student` | `@role_required("admin")` |
| DELETE | `/api/students/batch-delete` | `api_batch_delete_students` | `@role_required("admin")` |
| POST | `/api/students/import` | `api_import_students` | `@role_required("admin")` |
| GET | `/api/students/export` | `api_export_students` | `@role_required("admin")` |
| POST | `/api/chat` | `api_chat` | `@login_required` |
| GET | `/api/sessions` | `api_get_sessions` | `@login_required` |
| POST | `/api/sessions` | `api_create_session` | `@login_required` |
| GET | `/api/sessions/<id>/messages` | `api_get_session_messages` | `@login_required` |
| PUT | `/api/sessions/<id>/rename` | `api_rename_session` | `@login_required` |

**共计：** 3 个页面路由 + 16 个 API 路由 = 19 个端点。

---

## 4. MCP Server

**框架：** `mcp[cli]` 的 `FastMCP`。
**传输：** 仅 `stdio`。
**入口：** `mcp_server.server:main`（`pyproject.toml` 中注册为 `mcp-server` 脚本）。

### 已注册工具（共 11 个）

**基础工具：**
- `mcp_health_check` — 返回 server 状态
- `echo_message` — 参数往返测试
- `database_status` — 检查数据库文件和表

**只读工具：**
- `get_student_table_schema` — 返回 `PRAGMA table_info(students)`
- `count_students` — 统计总数
- `list_students` — 列出所有学生
- `search_students` — 跨字段搜索
- `get_student_by_id` — 按 ID 查询
- `get_student_by_number` — 按学号查询
- `get_student_stats` — 统计数据

**写入工具：**
- `add_student` — 添加学生
- `update_student` — 更新学生（部分更新）
- `upsert_student` — 按学号创建或更新

**架构问题：** MCP Server 通过 `sys.path.insert(0, ...)` 直接导入 `db.py`，绕过应用和 Service 层。

---

## 5. AI Chat 流程

1. 前端 `POST /api/chat` 发送消息 + `session_id`
2. `ai_service.py` 的 `send_chat_message()` 处理：
   - 无 session_id 时创建新会话
   - 消息保存到 `data/chat_history.json`
3. `generate_ai_reply()` 核心逻辑：
   - 从 JSON 加载最近 12 条消息作为上下文
   - 构建系统提示 + 历史 + 当前消息
   - 附带 MCP OpenAI 工具格式，`tool_choice: "auto"`
   - 第一次请求 → 获取 tool_calls
   - 执行 MCP 工具调用 → 结果追加到消息列表
   - 第二次请求 → 用工具结果生成最终回复
   - 回复写入 JSON，更新会话时间戳

**存储：** `data/sessions.json` + `data/chat_history.json`（无索引、无并发控制）。

---

## 6. 认证机制

- **Flask session cookie**（基于 `FLASK_SECRET_KEY`）
- 密码：Werkzeug `generate_password_hash` / `check_password_hash`
- 默认管理员：源码中硬编码 `admin` / `admin123`
- 装饰器：`@login_required`（检查 session user_id）、`@role_required("admin")`（检查 role）
- 角色：`"admin"` 和 `"teacher"`
- `session.permanent = True`

---

## 7. 前端结构

- **模板：** Jinja2 继承体系（`base.html` → 子模板）
- **CSS：** 自定义属性主题、Flexbox 布局、阴影/圆角
- **JS：** 无框架，`fetch()` + 手动 DOM 操作
  - `students.js`（~500 行）：全部学生列表状态管理
  - `ai_assistant.js`（~250 行）：AI 侧边栏 + 语音输入（Web Speech API）
  - `login.js`：登录表单

### 前端状态

```javascript
let currentPage = 1;
let pageSize = 15;
let totalPages = 0;
let totalStudents = 0;
let currentKeyword = '';
let currentSortBy = 'id';
let currentSortOrder = 'desc';
let selectedStudentIds = new Set();
let currentStudents = [];
```

---

## 8. 导入导出

- **导入：** pandas 解析 CSV 和 Excel（xlsx/xls）
- **列名映射：** 支持中英文别名（如 `"学号"` → `"student_number"`）
- **去重：** upsert 方式按 `student_number`
- **导出：** pandas 输出 CSV（UTF-8 BOM）或 Excel
- **权限：** 导入导出均为 admin only

---

## 9. 测试覆盖

**无测试。** 无 `tests/` 目录，无 pytest 配置，无任何测试文件。

---

## 10. 依赖清单

| 包名 | 用途 |
|------|------|
| Flask>=3.0.0 | Web 框架 |
| python-dotenv>=1.0.0 | 环境变量加载 |
| requests>=2.31.0 | HTTP 请求 |
| pandas>=2.2.0 | 数据导入导出 |
| openpyxl>=3.1.0 | Excel 支持 |
| mcp[cli]>=1.27,<2 | MCP Server |
| httpx>=0.28.1 | MCP Client 底层 HTTP |
