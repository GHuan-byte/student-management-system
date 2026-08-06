# Student Management System V2

Student Management System V2 是对旧版学生管理系统的重写项目。项目使用 Python、Flask、SQLite、Jinja2、HTML/CSS、Vanilla JavaScript、MCP、OpenAI-compatible Chat Completions API 和 pytest 构建。

当前已具备的主要能力包括：

- Dashboard 与学生 CRUD
- 搜索、分页、排序、当前页全选和批量删除
- AI Chat 与危险操作的 Action Confirmation
- AI Chat 引导添加学生动画（受控动作、确认前暂停、确认后单次写入与高亮）
- MCP 学生工具
- Viewer / Staff / Admin 登录与权限控制
- CSRF 防护、安全事件日志与 `request_id`

项目仍按 OpenSpec 分阶段演进；例如旧数据库迁移、用户管理页面等规划能力不应视为已完成。

## 当前项目状态

### 已完成并归档

- V2 application factory 和配置基础
- 学生 CRUD 与 Dashboard
- AI Chat 基础和 Action Confirmation
- `configure-application-logging`
- `add-login-access-control`（Viewer / Staff / Admin 登录、权限控制与 CSRF）
- `add-ai-guided-student-actions`（AI 引导添加学生动画：受控动作、确认后单次写入与高亮）

## 项目结构

```text
student-management-system-v2/
├── app/
│   ├── routes/          # HTTP 路由
│   ├── services/        # 业务规则、验证与编排
│   ├── repositories/    # 数据库访问
│   ├── database/        # SQLite 连接与 schema
│   ├── templates/       # Jinja2 模板
│   └── static/          # CSS 和 Vanilla JavaScript
├── mcp_server/          # stdio MCP server 与学生工具
├── mcp_client/          # 本地 MCP client 与 self-check
├── tests/               # pytest 测试
├── openspec/            # 规格、Change 与归档记录
├── instance/            # 本地运行时数据与可选日志（不提交）
├── run.py               # Flask 启动入口
├── pyproject.toml       # 项目依赖与测试额外依赖
└── .env.example         # 本地环境变量模板
```

依赖方向固定为：

```text
HTTP Route / MCP Tool
        ↓
     Service
        ↓
   Repository
        ↓
     SQLite
```

HTTP Route 和 MCP Tool 都不得直接执行 SQL；它们必须复用 Service，Repository 只负责数据库访问。

## 环境要求

- 当前主要开发环境：Windows 11 / PowerShell
- Python 3.12 或兼容版本（项目声明为 Python `>=3.12`）
- 示例虚拟环境目录：`student-v2-env`

## 创建本地环境

在项目根目录执行：

```powershell
python -m venv student-v2-env
.\student-v2-env\Scripts\Activate.ps1
```

首次建立环境后，按 `pyproject.toml` 安装项目及测试额外依赖：

```powershell
python -m pip install -e ".[test]"
```

若 PowerShell 阻止激活脚本，请遵循本机的执行策略要求处理；不要为此提交虚拟环境目录。

## 配置本地变量

复制模板创建仅供本机使用的 `.env`：

```powershell
Copy-Item .env.example .env
```

至少为本地登录验收设置下列值；密码必须由开发者自行指定，不要使用示例、弱密码或提交后的值：

```dotenv
SECRET_KEY=<随机且仅本机使用的密钥>
BOOTSTRAP_DEFAULT_USERS_ENABLED=true
BOOTSTRAP_VIEWER_PASSWORD=<viewer 本地密码>
BOOTSTRAP_STAFF_PASSWORD=<staff 本地密码>
BOOTSTRAP_ADMIN_PASSWORD=<admin 本地密码>
```

`.env.example` 还包含 Flask 地址、SQLite 路径、日志、session、MCP 和 AI Chat 的配置项。AI Chat 需要在本地 `.env` 中填写 `DEEPSEEK_API_KEY`、`DEEPSEEK_API_BASE` 和 `DEEPSEEK_MODEL`；未配置时不应假定 AI 服务可用。

## 初始化并启动 Flask

先初始化当前 `DATABASE_PATH` 指向的 SQLite 数据库：

```powershell
flask --app run.py init-db
```

然后启动开发服务器：

```powershell
python run.py
```

默认地址为 `http://127.0.0.1:5001/`。也可显式指定监听地址和端口：

```powershell
python run.py --host 127.0.0.1 --port 5001
```

健康检查：

```powershell
curl http://127.0.0.1:5001/api/health
```

## 使用三个角色账号

当 `BOOTSTRAP_DEFAULT_USERS_ENABLED=true` 且三个密码变量均已设置时，应用会根据 `.env` 的用户名配置创建本地 bootstrap 账号。默认用户名为 `viewer`、`staff` 和 `admin`；密码就是你在本地 `.env` 中设置的值，README 不提供或记录密码。

打开 `http://127.0.0.1:5001/login` 登录。角色权限如下：

| 角色 | 学生读取与 AI 只读对话 | 新增 / 编辑 / Upsert | 删除 / 批量删除 |
| --- | --- | --- | --- |
| Viewer | 允许 | 不允许 | 不允许 |
| Staff | 允许 | 允许 | 不允许 |
| Admin | 允许 | 允许 | 允许 |

所有受保护的写请求都需要有效登录和 CSRF token。退出登录使用页面提供的 POST logout 操作。

## 运行测试

在已激活的虚拟环境中运行完整测试：

```powershell
pytest -q
```

提交前还应检查文档或代码差异：

```powershell
git diff --check
git status
```

## 启动 MCP

当前 MCP 使用 stdio 传输。启动 server：

```powershell
python -m mcp_server.server
```

MCP 协议消息只使用 stdout；诊断日志应保持在 stderr，避免向 stdout 添加 `print()` 调试输出。MCP 工具同样通过 Service 和 Repository 访问 SQLite，不直接执行 SQL。

可运行本地临时数据库自检：

```powershell
python -m mcp_client.self_check
```

该自检会使用临时 SQLite 数据库验证 MCP 工具，不应用来替代对本地业务数据库的备份或人工验收。

## OpenSpec + Superpowers 工作流

中大型变更使用 OpenSpec 管理。推荐顺序是：

```text
OpenSpec Explore / Propose
        ↓
用户审查并批准规格
        ↓
Superpowers 按规格实施、调试与代码审查
        ↓
OpenSpec 只读对照检查
        ↓
Superpowers 生成新的验证证据
        ↓
用户完成浏览器验收
        ↓
OpenSpec Sync / Archive
```

不要自动进入下一个阶段。每个 Change 都应限定允许修改范围，先运行相关测试，再运行完整测试、`git diff --check` 和 Git diff 审查；带有 `[USER]` 的人工验收项必须由用户完成。

## 敏感文件与隐私

严禁提交 `.env`、API Key、密码、session secret、Cookie、CSRF token、运行时 SQLite 数据库、本地日志、含学生隐私的导入/导出文件、虚拟环境或测试缓存。`.env.example` 只能保留空值或占位符。

提交前请检查：

```powershell
git status
git diff --check
```

如需修改应用行为，请先阅读相关 OpenSpec 与 `AGENTS.md`，并保持变更在当前批准的阶段范围内。
