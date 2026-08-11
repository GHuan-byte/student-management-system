# 学生信息管理系统（Student Management System）

基于 **Flask** 的学生信息管理 Web 应用，内置 **AI 助手**，通过 **MCP（Model Context Protocol）** 让大模型直接查询 / 维护学生数据库，实现"问一句，查数据，给答案"。

## ✨ 功能特性

### 学生信息管理
- **增删改查**：学号、姓名、性别、年龄、专业、成绩、电话、邮箱
- **关键字搜索**：学号 / 姓名 / 专业 / 成绩 / 电话 / 邮箱 模糊匹配
- **排序与分页**：点击表头排序（字段白名单防注入），每页 15 条，自动纠偏页码
- **批量删除**：勾选多条记录一键删除（仅管理员）
- **导入 / 导出**：支持 CSV、Excel（xlsx/xls），导入自动识别中英文列名并按学号 **upsert**（存在即更新、不存在即新增，跳过错误行并返回明细）

### 登录与权限
- 用户名密码登录（密码哈希存储）、登出、当前用户查询
- 角色体系：`admin`（管理员）/ `teacher`（教师）
- 首次启动自动创建默认管理员：`admin / admin123`

### AI 助手（🤖）
- 右下角浮动按钮 + 侧边栏界面
- 多会话管理：新建、自动命名、重命名、历史消息加载
- **MCP 工具调用**：模型自动选择工具查询真实数据后再回答（Function Calling）
- 语音输入（Web Speech API）、Markdown 表格渲染、复制按钮、打字指示器

### MCP 服务
- 提供 **stdio** 与 **HTTP（streamable-http）** 两种传输方式
- 内置 13 个学生数据库工具（详见下文）

## 🛠 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python ≥ 3.12 |
| Web 框架 | Flask ≥ 3.0 |
| 数据库 | SQLite（标准库 `sqlite3`） |
| 数据处理 | pandas、openpyxl |
| AI 协议 | MCP（`mcp>=1.27` + FastMCP） |
| HTTP 服务 | uvicorn（MCP streamable-http） |
| 前端 | 原生 HTML / CSS / JavaScript |

## 📁 项目结构

```
student-management-system/
├── app.py                 # Flask 主应用 + 全部 REST API 路由
├── auth.py                # 登录验证 + 角色权限（admin / teacher）
├── db.py                  # SQLite 数据访问层（students / users 表）
├── ai_service.py          # AI 对话服务、会话管理（JSON 存储）
├── mcp_client.py          # MCP 客户端（stdio 拉起子进程并调用工具）
├── run.py                 # 统一启动入口（Flask + MCP）
├── requirements.txt       # 依赖清单
├── pyproject.toml         # 项目元数据 + 控制台脚本
├── .env.example           # 环境变量示例
├── data/                  # 数据库、会话、聊天记录（自动生成）
├── exports/               # 导出的文件
├── logs/                  # 运行日志（含 MCP server 日志）
├── uploads/               # 导入的原始文件
├── mcp_server/
│   ├── server.py          # FastMCP 服务器，注册全部工具
│   ├── student_tools.py   # 学生数据库工具（13 个）
│   └── http_app.py        # MCP HTTP（streamable-http）入口
├── static/
│   ├── css/style.css      # 样式
│   └── js/                # students.js / login.js / ai_assistant.js
└── templates/             # base / index / login / students
```

## 🚀 快速开始

### 1. 环境要求
- Python 3.12 及以上

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

> `requirements.txt` 已包含 `mcp` 与 `uvicorn`，可直接用于安装。

### 3. 配置环境变量（可选）

复制 `.env.example` 为 `.env`，AI 助手功能需要配置以下项：

```ini
# AI 大模型接口（OpenAI 兼容格式）
OPENAI_API_BASE=https://your-api-endpoint/v1
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o-mini

# 是否绕过系统代理直连（默认 true）
OPENAI_BYPASS_PROXY=true

# 会话密钥（生产环境请修改）
FLASK_SECRET_KEY=please-change-me
```

> 未配置时，学生管理功能完全可用；AI 助手会提示"未配置大模型接口"。

### 4. 启动项目

```bash
# 推荐：同时启动 MCP Server（HTTP :8000）+ 主应用（:5000）
python run.py

# 仅启动主应用（等价于 python app.py）
python run.py web
```

启动后访问：<http://127.0.0.1:5000>

默认账号：**admin / admin123**

## 🧩 run.py 启动模式

| 命令 | 说明 |
|------|------|
| `python run.py` | **默认**：MCP 自检 → 后台启动 MCP HTTP（`:8000`）→ 启动主应用（`:5000`），退出自动清理 |
| `python run.py web` | 仅启动主 Flask 应用 |
| `python run.py mcp` | 仅以 **stdio** 模式启动 MCP（供 Claude Desktop 等客户端连接） |
| `python run.py mcp-http` | 仅以前台方式启动 MCP HTTP |
| `python run.py mcp-check` | 对 MCP Server 做一次自检后退出 |

环境变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MCP_HOST` | `127.0.0.1` | MCP HTTP 监听地址 |
| `MCP_PORT` | `8000` | MCP HTTP 监听端口 |
| `HOST` | `0.0.0.0` | 主应用监听地址 |
| `PORT` | `5000` | 主应用监听端口 |
| `FLASK_DEBUG` | `true` | 是否开启调试模式 |

## 🔌 API 接口

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 当前用户信息 |

### 学生管理（登录后可用，删除/导入/导出需 admin）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/students` | 分页列表（支持 `keyword` / `sort_by` / `sort_order` / `page` / `page_size`） |
| POST | `/api/students` | 新增学生 |
| GET | `/api/students/<id>` | 获取单个学生 |
| PUT | `/api/students/<id>` | 更新学生 |
| DELETE | `/api/students/<id>` | 删除学生 |
| DELETE | `/api/students/batch-delete` | 批量删除 |
| POST | `/api/students/import` | 导入 CSV/Excel（multipart `file`） |
| GET | `/api/students/export` | 导出（`format=csv\|xlsx`，支持 `keyword`） |

### AI 助手
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 发送对话消息（`message` / `session_id`） |
| GET | `/api/sessions` | 会话列表 |
| POST | `/api/sessions` | 新建会话 |
| GET | `/api/sessions/<id>/messages` | 会话历史 |
| PUT | `/api/sessions/<id>/rename` | 重命名会话 |

## 🛠 MCP 工具（13 个）

**基础测试**
- `mcp_health_check` — 检查 MCP Server 是否正常
- `echo_message` — 原样返回消息（测试参数传递）

**数据库信息**
- `database_status` — 数据库是否存在及表清单
- `get_student_table_schema` — students 表结构

**查询类**
- `count_students` — 学生总人数
- `list_students` — 学生列表
- `search_students` — 关键字搜索
- `get_student_by_id` — 按数据库 ID 查询
- `get_student_by_number` — 按学号查询
- `get_student_stats` — 统计信息（总人数 / 专业数 / 成绩数 / 最近录入）

**写入类**
- `add_student` — 新增学生
- `update_student` — 更新学生（支持部分字段）
- `upsert_student` — 不存在则新增，存在则更新

> 页面内 AI 助手通过 `mcp_client.py` 以 stdio 方式按需调用这些工具；同时 `python run.py` 会以 HTTP 形式在 `:8000/mcp` 暴露同一批工具，供外部 MCP 客户端接入。

## 📝 备注与约定

- 学生字段（`STUDENT_FIELDS`）：`student_number`、`name`、`gender`、`age`、`major`、`grade`、`phone`、`email`
- 导入列名别名：支持中文（学号/姓名/性别/年龄/专业/年级/成绩/电话/手机号/邮箱）与英文（`student_number` 等）
- 数据文件（`data/students.db`、`sessions.json`、`chat_history.json`）会在首次运行时自动创建
- 生产部署请替换 `FLASK_SECRET_KEY` 并修改默认管理员密码，避免使用 Flask 开发服务器

## 📄 许可证

本项目为教学 / 学习用途示例项目。
