# Implementation Roadmap — Student Management System V2

> 阶段门（Gate）定义。每个 Gate 完成后经验证方可进入下一 Gate。
> 不得自动进入下一阶段。

---

## 阶段总览

```
Gate 0: 规划阶段（当前）── 文档已就绪
    │
    ▼
Gate 1: Project Foundation ──── Gate 2: Legacy Audit (已完成)
    │                                 已完成，文档在 docs/planning/
    ▼
Gate 3: Database and Repository
    │
    ▼
Gate 4: Service Layer
    │
    ▼
Gate 5: Authentication
    │
    ▼
Gate 6: REST API — Student CRUD
    │
    ▼
Gate 7: Student List Frontend
    │
    ▼
Gate 8: Search, Pagination, Sorting, Selection
    │
    ▼
Gate 9: Create, Edit, Delete Frontend
    │
    ▼
Gate 10: Import and Export
    │
    ▼
Gate 11: MCP Read Tools
    │
    ▼
Gate 12: AI Chat
    │
    ▼
Gate 13: Legacy Data Migration
    │
    ▼
Gate 14: Final Verification
```

---

## Gate 0：Planning（已完成）

**状态：** ✅ 已完成

**目标：** 完成需求分析、旧项目审计、架构决策和实现规划。

**输入：** 旧项目代码、用户需求。

**输出：**
- `docs/planning/legacy-audit.md`
- `docs/planning/feature-inventory.md`
- `docs/planning/known-problems.md`
- `docs/planning/architecture-decisions.md`
- `docs/planning/implementation-roadmap.md`

**允许修改：** 仅 `docs/planning/` 目录。

**禁止范围：** 任何业务代码、依赖安装、数据库创建。

**验证命令：** 无需（纯文档阶段）。

**验收条件：** 所有规划文档完成并经过审查。

**完成证据：** 5 份文档存在于 `docs/planning/` 中。

---

## Gate 1：Project Foundation

**目标：** 搭建 Flask 应用骨架：应用工厂、配置管理、统一响应格式、错误处理、CLI 入口。

**输入：**
- `docs/planning/architecture-decisions.md`（ADR-001, ADR-002, ADR-005, ADR-013）

**输出：**
- `pyproject.toml` — 项目元数据和依赖声明
- `run.py` — 应用启动入口
- `app/__init__.py` — `create_app()` 应用工厂
- `app/config.py` — 配置类（开发/测试/生产）
- `app/utils/__init__.py`
- `app/utils/response.py` — 统一 JSON 响应工具
- `app/utils/errors.py` — 错误处理装饰器和异常类
- `app/cli.py` — CLI 命令注册（`flask init-admin` 占位）
- `.gitignore` — Python 项目标准 gitignore
- `.env.example` — 环境变量模板
- `tests/conftest.py` — pytest 共享 fixture
- `tests/test_app.py` — 应用启动和健康检查测试

**允许修改：**
- `pyproject.toml`（新增）
- `run.py`（新增）
- `app/` 目录（新增）
- `tests/` 目录（新增）
- `.gitignore`（新增/修改）
- `.env.example`（已存在，可修改）

**禁止范围：**
- 数据库连接和 schema
- Repository 层
- Service 层
- 路由（除 `/api/health`）
- 模板和静态文件
- MCP 相关代码

**验证命令：**
```powershell
pip install -e .
pytest tests/test_app.py -q
python run.py --check  # 或健康检查
```

**验收条件：**
1. `create_app()` 工厂函数正常创建应用实例。
2. 配置类正确加载环境变量。
3. `/api/health` 返回统一 JSON 响应格式。
4. 错误处理装饰器正确捕获异常并返回统一格式。
5. `flask init-admin --help` 显示命令说明（可暂不实现）。
6. 所有测试通过。

**完成证据：** 应用可启动，健康检查端点返回 `{"success": true, "data": {"status": "ok"}}`。

---

## Gate 2：Legacy Audit（已完成）

**状态：** ✅ 已完成（参见 `docs/planning/legacy-audit.md`）

---

## Gate 3：Database and Repository

**目标：** 实现数据库连接管理、Schema 初始化、Student Repository 和 User Repository。

**输入：**
- Gate 1 输出的 `app/` 骨架
- `docs/planning/architecture-decisions.md`（ADR-004, ADR-012, ADR-013）
- `docs/planning/feature-inventory.md`（字段定义）

**输出：**
- `app/database.py` — 数据库连接管理、Schema 初始化
- `app/repositories/__init__.py`
- `app/repositories/student_repository.py` — 学生 CRUD + 搜索 + 分页 + 排序
- `app/repositories/user_repository.py` — 用户 CRUD
- `tests/test_student_repository.py`
- `tests/test_user_repository.py`

**允许修改：**
- `app/database.py`（新增）
- `app/repositories/`（新增）
- `tests/test_student_repository.py`（新增）
- `tests/test_user_repository.py`（新增）
- `app/__init__.py`（注册 database 初始化）

**禁止范围：**
- Service 层
- 路由
- 模板和静态文件
- MCP

**Repository 方法清单 — `student_repository.py`：**

| 方法 | 说明 |
|------|------|
| `init_schema()` | 创建 students 表 |
| `count(keyword=None)` | 统计学生数（支持搜索过滤） |
| `list(page, page_size, sort_by, sort_order, keyword=None)` | 分页列表 |
| `get_by_id(student_id)` | 按 ID 查询 |
| `get_by_student_number(number)` | 按学号查询 |
| `create(student_data)` | 新增学生 |
| `update(student_id, student_data)` | 更新学生 |
| `delete(student_id)` | 删除学生 |
| `batch_delete(ids)` | 批量删除 |
| `get_stats()` | 统计数据 |
| `exists_by_student_number(number, exclude_id=None)` | 检查学号唯一性 |

**排序白名单：**
```python
SORT_WHITELIST = {'id', 'student_number', 'name', 'gender', 'age', 'major', 'cohort', 'grade'}
```

> 数字字段（`id`, `age`, `grade`）使用 `CAST(... AS INTEGER)` 排序。

**Repository 方法清单 — `user_repository.py`：**

| 方法 | 说明 |
|------|------|
| `init_schema()` | 创建 users 表 |
| `get_by_username(username)` | 按用户名查询 |
| `create(username, password_hash, role)` | 创建用户 |
| `exists_by_username(username)` | 检查用户名是否存在 |
| `count()` | 统计用户数 |

**测试要求：**
1. 使用 `tmp_path` fixture 创建临时数据库。
2. 每个测试函数独立数据库。
3. 覆盖正常路径和边界条件。
4. 排序字段注入非法值应被拒绝（白名单验证）。
5. 搜索 SQL 参数化正确性。

**验证命令：**
```powershell
pytest tests/test_student_repository.py tests/test_user_repository.py -q
```

**验收条件：**
1. Schema 初始化正确创建 students 和 users 表。
2. Repository CRUD 操作全部通过测试。
3. 排序白名单阻止非法字段。
4. 搜索 SQL 是参数化的。
5. 分页返回正确数据和总数。
6. 测试数据库隔离（互相不影响）。

**完成证据：** Repository 测试全部通过，代码审查确认 SQL 参数化和白名单。

---

## Gate 4：Service Layer

**目标：** 实现 Student Service 和 Auth Service，包含业务规则和数据验证。

**输入：**
- Gate 3 的 Repository 代码
- `docs/planning/architecture-decisions.md`（ADR-001）

**输出：**
- `app/services/__init__.py`
- `app/services/student_service.py` — 学生业务逻辑
- `app/services/auth_service.py` — 认证业务逻辑
- `tests/test_student_service.py`
- `tests/test_auth_service.py`

**允许修改：**
- `app/services/`（新增）
- `tests/test_student_service.py`（新增）
- `tests/test_auth_service.py`（新增）

**禁止范围：**
- 路由
- 模板和静态文件
- MCP

**Student Service 验证规则：**

| 字段 | 规则 |
|------|------|
| `student_number` | 必填，不超过 32 字符，唯一 |
| `name` | 必填，不超过 64 字符 |
| `gender` | 必填，取值 `"男"` 或 `"女"` |
| `age` | 必填，整数，1–150 |
| `major` | 必填，不超过 128 字符 |
| `cohort` | 必填，不超过 32 字符 |
| `grade` | 必填，整数，0–100 |
| `phone` | 可选，匹配手机号格式 |
| `email` | 可选，匹配邮箱格式 |

**Service 异常：**
- `ValidationError` — 数据验证失败
- `DuplicateError` — 学号重复
- `NotFoundError` — 资源不存在
- `ForbiddenError` — 权限不足

**测试要求：**
1. Mock Repository 层，不依赖真实数据库。
2. 覆盖所有验证规则。
3. 覆盖重复学号检测。
4. 覆盖边界值（age 0/150/151，grade -1/0/100/101）。

**验证命令：**
```powershell
pytest tests/test_student_service.py tests/test_auth_service.py -q
```

**验收条件：**
1. 所有验证规则正确触发对应异常。
2. 学号重复检测通过 Repository 调用实现。
3. 合法数据通过验证并正确传递到 Repository。
4. 异常信息清晰、具体。

**完成证据：** Service 测试全部通过。

---

## Gate 5：Authentication

**目标：** 实现完整的认证体系：Flask-Login、登录/登出/状态 API、角色装饰器、`flask init-admin` CLI。

**输入：**
- Gate 4 的 Auth Service
- `docs/planning/architecture-decisions.md`（ADR-003）

**输出：**
- `app/routes/__init__.py`
- `app/routes/auth.py` — 认证 Blueprint
- `app/extensions.py` — Flask-Login 初始化
- `app/models/user.py` — Flask-Login UserMixin 模型
- `app/decorators.py` — `@login_required`, `@role_required` 装饰器
- `app/cli.py` — 更新：实现 `flask init-admin` 命令
- `tests/test_auth_api.py`

**允许修改：**
- `app/routes/auth.py`（新增）
- `app/extensions.py`（新增）
- `app/models/user.py`（新增）
- `app/decorators.py`（新增）
- `app/cli.py`（修改）
- `app/__init__.py`（注册 Flask-Login 和 Blueprint）
- `tests/test_auth_api.py`（新增）

**禁止范围：**
- 学生相关路由
- 模板和静态文件
- MCP

**CLI 命令设计：**
```
flask init-admin
  # 交互式输入用户名、密码
  # 验证密码强度（至少 6 位）
  # 如果 admin 用户已存在则提示跳过
```

**验证命令：**
```powershell
pytest tests/test_auth_api.py -q
flask init-admin --help
```

**验收条件：**
1. 登录成功返回用户信息和 session cookie。
2. 登录失败（错误凭据）返回 401。
3. 未登录请求受保护端点返回 401。
4. teacher 角色无法调用 admin 专属端点。
5. `flask init-admin` 成功创建初始管理员。
6. 重复运行 `flask init-admin` 提示已存在。

**完成证据：** 认证 API 测试全部通过，CLI 命令验证通过。

---

## Gate 6：REST API — Student CRUD

**目标：** 实现学生相关的全部 REST API 端点。

**输入：**
- Gate 4 的 Student Service
- `docs/planning/architecture-decisions.md`（ADR-005, ADR-006）

**输出：**
- `app/routes/students.py` — 学生 Blueprint
- `tests/test_students_api.py`

**允许修改：**
- `app/routes/students.py`（新增）
- `app/__init__.py`（注册 student Blueprint）
- `tests/test_students_api.py`（新增）

**禁止范围：**
- 模板和静态文件
- MCP

**API 端点清单：**

| 方法 | 路径 | 角色 | 说明 |
|------|------|------|------|
| GET | `/api/students` | teacher+ | 列表（page, page_size, keyword, sort_by, sort_order） |
| GET | `/api/students/<id>` | teacher+ | 详情 |
| GET | `/api/students/stats` | teacher+ | 统计 |
| POST | `/api/students` | teacher+ | 新增 |
| PUT | `/api/students/<id>` | teacher+ | 编辑 |
| DELETE | `/api/students/<id>` | admin | 单条删除 |
| DELETE | `/api/students/batch` | admin | 批量删除 |

**响应格式示例（列表）：**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "student_number": "2024001",
      "name": "张三",
      "gender": "男",
      "age": 20,
      "major": "计算机科学",
      "cohort": "2023级",
      "grade": 85,
      "phone": "13800138000",
      "email": "zhangsan@example.com",
      "created_at": "2026-07-21T10:00:00",
      "updated_at": "2026-07-21T10:00:00"
    }
  ],
  "message": "",
  "error": null,
  "meta": {
    "page": 1,
    "page_size": 15,
    "total": 42,
    "total_pages": 3
  }
}
```

**验证命令：**
```powershell
pytest tests/test_students_api.py -q
```

**验收条件：**
1. 所有端点返回统一 JSON 响应格式。
2. 分页参数在 `meta` 中正确返回。
3. 权限装饰器正确拦截未授权访问。
4. 非法排序字段返回 400 错误。
5. 重复学号返回 409 错误。
6. 所有集成测试使用临时数据库。

**完成证据：** API 测试全部通过，可手动 curl 验证。

---

## Gate 7：Student List Frontend

**目标：** 实现基础前端：Jinja2 模板体系、登录页面、学生列表页面（只读）。

**输入：**
- Gate 6 的 REST API
- `docs/planning/architecture-decisions.md`（ADR-007）

**输出：**
- `templates/base.html` — 基础布局
- `templates/login.html` — 登录页
- `templates/students.html` — 学生列表页
- `static/css/style.css` — 全局样式
- `static/js/core/api.js` — fetch 封装 + 统一错误处理
- `static/js/core/utils.js` — DOM 工具、格式化
- `static/js/pages/login.js` — 登录逻辑
- `static/js/pages/students.js` — 学生列表（仅加载和渲染）

**允许修改：**
- `templates/`（新增）
- `static/`（新增）
- `app/routes/`（新增页面路由：`/`、`/login`、`/students`）

**禁止范围：**
- 搜索、分页、排序控件
- 编辑/删除按钮
- 导入导出
- MCP、AI Chat

**验证命令：**
```powershell
# 启动 Flask 应用
python run.py
# 打开浏览器访问 http://127.0.0.1:5001
# 登录后查看学生列表
```

**验收条件：**
1. 登录页面正确渲染，登录成功跳转到学生列表。
2. 学生列表页面加载后自动 AJAX 加载数据。
3. 数据正确渲染为表格。
4. 未登录自动跳转到登录页。
5. 模板继承体系正常工作。

**完成证据：** 手动测试验证页面渲染和数据加载。

---

## Gate 8：Search, Pagination, Sorting, Selection

**目标：** 实现前端搜索、分页控件、排序控件、当前页全选功能。

**输入：**
- Gate 7 的前端代码

**输出：**
- 修改 `static/js/pages/students.js`（扩展状态管理和事件处理）
- 修改 `templates/students.html`（添加搜索栏、分页栏、表头排序）

**允许修改：**
- `static/js/pages/students.js`（修改）
- `templates/students.html`（修改）
- `static/css/style.css`（修改）

**禁止范围：**
- 编辑/删除功能
- 导入导出
- MCP、AI Chat

**前端状态：**
```javascript
const state = {
  currentPage: 1,
  pageSize: 15,
  keyword: '',
  sortBy: 'id',
  sortOrder: 'desc',
  selectedIds: new Set(),
  total: 0,
  totalPages: 0,
  loading: false,
  students: []
};
```

**功能清单：**

| 功能 | 规则 |
|------|------|
| 搜索输入 | 输入后按回车或点击搜索按钮触发 |
| 搜索重置 | 清空关键词并重新加载 |
| 关键词变化 | `currentPage = 1` |
| 排序点击 | 点击表头切换 `asc`/`desc` |
| 排序变化 | `currentPage = 1` |
| 分页控件 | 上一页、下一页、页码跳转 |
| 当前页全选 | 选中/取消当前页所有 visible id |
| 全选不定状态 | 部分选中时 checkbox 显示 indeterminate |
| 翻页后 | 重新计算全选 checkbox 状态 |

**验证命令：**
```powershell
# 手动测试
pytest tests/test_students_api.py -q  # 确保后端 API 正常
```

**验收条件：**
1. 搜索关键词输入后正确过滤结果，页码重置为 1。
2. 点击表头正确切换排序方向，页码重置为 1。
3. 分页控件正确显示页码信息，翻页正常。
4. 当前页全选/取消全选正常工作。
5. 翻页后全选状态正确重置或恢复。

**完成证据：** 手动测试验证搜索、分页、排序、全选全部正常。

---

## Gate 9：Create, Edit, Delete Frontend

**目标：** 实现新增/编辑弹窗、单条删除、批量删除的前端交互。

**输入：**
- Gate 8 的前端代码

**输出：**
- 修改 `static/js/pages/students.js`（新增编辑、删除逻辑）
- 修改 `templates/students.html`（新增弹窗、操作按钮）
- 新增 `static/css/modal.css` 或集成到 `style.css`

**允许修改：**
- `static/js/pages/students.js`（修改）
- `templates/students.html`（修改）
- `static/css/style.css`（修改）

**禁止范围：**
- 导入导出
- MCP、AI Chat

**功能清单：**

| 功能 | 规则 |
|------|------|
| 新增弹窗 | 填写表单后 POST 到 `/api/students` |
| 编辑弹窗 | 填入现有数据后 PUT 到 `/api/students/<id>` |
| 单条删除 | 确认后 DELETE `/api/students/<id>` |
| 批量删除 | 确认后 DELETE `/api/students/batch` |
| 删除后 | 如果当前页无数据且 `page > 1`，`page -= 1` |
| 权限控制 | 非 admin 隐藏删除按钮 |
| 表单验证 | 前端基础验证 + 后端 Service 验证 |

**验证命令：**
```powershell
pytest tests/test_students_api.py -q
```

**验收条件：**
1. 新增学生成功，列表自动刷新到第一页。
2. 编辑学生成功，列表保持当前页不变。
3. 单条删除成功，列表自动刷新。
4. 批量删除成功，列表自动刷新。
5. 删除当前页最后一条记录后自动退回上一页。
6. teacher 角色看不到删除按钮。

**完成证据：** CRUD 操作全部手动测试通过。

---

## Gate 10：Import and Export

**目标：** 实现 CSV/Excel 导入和导出功能。

**输入：**
- Gate 9 的前端和后端代码
- `docs/planning/feature-inventory.md`（导入导出需求）
- 旧项目的列名映射机制

**输出：**
- `app/utils/importer.py` — 导入处理逻辑
- `app/utils/exporter.py` — 导出处理逻辑
- 修改 `app/routes/students.py`（导入/导出端点）
- 修改 `static/js/pages/students.js`（导入/导出 UI）
- 修改 `templates/students.html`（导入/导出按钮）
- `tests/test_import_export.py`

**允许修改：**
- `app/utils/importer.py`（新增）
- `app/utils/exporter.py`（新增）
- `app/routes/students.py`（修改）
- `static/js/pages/students.js`（修改）
- `templates/students.html`（修改）
- `tests/test_import_export.py`（新增）
- `pyproject.toml`（添加 pandas/openpyxl 依赖）

**禁止范围：**
- MCP
- AI Chat

**功能要求：**

| 功能 | 说明 |
|------|------|
| CSV 导入 | pandas 解析，支持 UTF-8/GBK |
| Excel 导入 | openpyxl 解析 |
| 列名映射 | 中英文双向映射（如 "学号" ↔ "student_number"） |
| 去重 | 按 `student_number` 去重 |
| CSV 导出 | UTF-8 BOM，包含所有字段 |
| Excel 导出 | 包含所有字段 |

**验证命令：**
```powershell
pytest tests/test_import_export.py -q
# 手动测试：导入一个 CSV 文件后检查列表
```

**验收条件：**
1. CSV 导入正确解析并存入数据库。
2. Excel 导入正确解析并存入数据库。
3. 重复学号的行被更新（upsert）而非报错。
4. 导出文件可正常打开，内容正确。
5. 中英文字段名均被识别。

**完成证据：** 导入导出测试全部通过，手动验证导入/导出文件内容正确。

---

## Gate 11：MCP Read Tools

**目标：** 实现 MCP Server，注册只读工具，与 HTTP Route 共用 Service。

**输入：**
- Gate 4 的 Student Service
- `docs/planning/architecture-decisions.md`（ADR-008, ADR-009, ADR-010, ADR-013）

**输出：**
- `app/mcp/__init__.py`
- `app/mcp/server.py` — FastMCP 服务器
- `app/mcp/student_tools.py` — 只读工具注册
- `app/mcp/client.py` — MCP Client（stdio 启动 + 工具转换）

**允许修改：**
- `app/mcp/`（新增）
- `pyproject.toml`（添加 mcp 依赖、注册脚本入口）

**禁止范围：**
- 写入工具
- AI Chat
- 前端修改

**初始只读工具：**

| 工具名 | 参数 | 返回值 |
|--------|------|--------|
| `list_students` | page, page_size, sort_by, sort_order | 学生列表 + 分页信息 |
| `search_students` | keyword, page, page_size | 匹配的学生列表 |
| `get_student_by_id` | student_id | 单个学生 |
| `get_student_by_number` | student_number | 单个学生 |
| `count_students` | (无) | 总数 |
| `get_student_stats` | (无) | 统计数据 |

**验证命令：**
```powershell
# 方式一：MCP Inspector
mcp dev app/mcp/server.py

# 方式二：Python 测试
pytest tests/test_mcp_tools.py -q
```

**验收条件：**
1. 所有只读工具正确返回数据。
2. 工具返回格式与 API 响应一致（共用 Service）。
3. 工具不暴露数据库内部信息。
4. 工具调用错误返回清晰错误信息（不堆栈泄露）。
5. stdio 传输正常工作。

**完成证据：** MCP 工具测试全部通过，可通过 MCP Inspector 验证。

---

## Gate 12：AI Chat

**目标：** 实现 AI 聊天功能：MCP Client、Chat Service、Chat API、前端 AI 侧边栏。

**输入：**
- Gate 11 的 MCP Server
- Gate 6 的 REST API

**输出：**
- `app/services/chat_service.py` — 聊天业务逻辑
- `app/routes/chat.py` — Chat Blueprint
- `static/js/components/ai_assistant.js` — AI 侧边栏
- `templates/components/ai_assistant.html` — AI 侧边栏模板
- 修改 `templates/base.html`（集成 AI 侧边栏）
- `tests/test_chat.py`

**允许修改：**
- `app/services/chat_service.py`（新增）
- `app/routes/chat.py`（新增）
- `static/js/components/ai_assistant.js`（新增）
- `templates/`（新增/修改）
- `app/__init__.py`（注册 Chat Blueprint）
- `tests/test_chat.py`（新增）
- `app/mcp/client.py`（可能修改）

**禁止范围：**
- 修改已稳定的学生 CRUD 逻辑
- 写入型 MCP 工具

**Chat API 端点：**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 发送消息 |
| GET | `/api/chat_sessions` | 会话列表 |
| POST | `/api/chat_sessions` | 新建会话 |
| GET | `/api/chat_sessions/<id>/messages` | 获取消息历史 |
| PUT | `/api/chat_sessions/<id>/rename` | 重命名会话 |

**调用流程：**

```
用户消息 → POST /api/chat
  → ChatService.send_message()
    1. 加载最近 N 条上下文
    2. 构建 system prompt + 历史 + 当前消息
    3. 附加 MCP OpenAI Tool 格式
    4. 调用 LLM API（OpenAI-compatible）
    5. 处理 tool_calls（通过 MCP Client 执行）
    6. 再次调用 LLM API（含工具结果）
    7. 返回回复
```

**MCP Client 职责（`app/mcp/client.py`）：**
- 通过 stdio 启动 MCP Server 子进程
- 调用 MCP Tool
- 将 MCP Tool schema 转换为 OpenAI-compatible 格式
- 健康检查

**验证命令：**
```powershell
pytest tests/test_chat.py -q
# 手动测试：打开 AI 侧边栏进行对话
```

**验收条件：**
1. AI Chat 可正常对话。
2. MCP Tool Call 正确执行并返回结果到对话。
3. 会话创建、重命名、历史查询正常。
4. 错误处理不暴露 API Key。
5. 前端 AI 侧边栏正确集成到页面。

**完成证据：** Chat 测试通过，手动对话验证 Tool Call 正常。

---

## Gate 13：Legacy Data Migration

**目标：** 创建可重复运行的迁移脚本，将旧项目数据库迁移到 V2 数据库。

**输入：**
- V2 完整代码
- 旧项目数据库文件（`D:\Python\student-management-system\data\students.db`）

**输出：**
- `scripts/migrate_v1_to_v2.py` — 迁移脚本
- `scripts/__init__.py`

**允许修改：**
- `scripts/`（新增）

**禁止范围：**
- 修改任何业务代码
- 修改数据库 schema

**迁移脚本设计：**

```
scripts/migrate_v1_to_v2.py [--source PATH] [--target PATH] [--dry-run]
```

**处理流程：**
1. 连接旧数据库（只读模式）。
2. 连接 V2 数据库。
3. 检查是否已迁移（检查 meta 表或标志）。
4. 读取旧 `students` 表。
5. 处理字段变更：
   - `grade`（旧：TEXT 年级）→ `cohort`（TEXT）
   - `grade`（新：INTEGER 成绩）← 默认值或跳过
   - `phone`/`email` NULL 处理
   - `updated_at` 可能为 NULL → 设为当前时间
   - `created_at` ← 设为 `updated_at` 或当前时间
6. 读取旧 `users` 表。
7. 批量 INSERT OR IGNORE 到 V2。
8. 报告迁移结果（记录数对比）。

**验证命令：**
```powershell
python scripts/migrate_v1_to_v2.py --dry-run
python scripts/migrate_v1_to_v2.py
# 对比记录数
```

**验收条件：**
1. `--dry-run` 正确报告将要迁移的记录数而不实际写入。
2. 迁移后 V2 数据库记录数与旧数据库一致。
3. 迁移脚本可重复运行（第二次运行提示已迁移或跳过已迁移记录）。
4. 字段映射正确（特别是 `grade` → `cohort` 的转换）。
5. 迁移后 V2 应用可正常加载数据。

**完成证据：** 迁移成功，数据完整性验证通过。

---

## Gate 14：Final Verification

**目标：** 全量验证：运行所有测试、代码审查、Git Diff 审查、文档更新。

**输入：** 全部代码。

**输出：** 验证报告（可记录在项目根目录或 docs 中）。

**允许修改：** 仅修复 bug（不新增功能）。

**禁止范围：** 任何新功能。

**验证清单：**

| 检查项 | 命令 | 预期 |
|--------|------|------|
| 全部测试 | `pytest -q` | 全部通过 |
| Git 状态 | `git status` | 无意外未跟踪文件 |
| Git Diff | `git diff --check` | 无空白错误 |
| 提交信息 | 审查 | 符合规范 |
| 文档 | 审查 | 与实现一致 |
| 安全 | 审查 | 无硬编码凭据、无密钥泄露 |
| E2E 手动测试 | 浏览器操作 | 全部功能正常 |

**验收条件：**
1. 所有测试通过。
2. Git Diff 无不相关文件变更。
3. 文档与实现一致。
4. 无安全泄露。
5. 所有核心功能通过手动验证。

**完成证据：** 测试报告 + Git Diff 审查通过 + 手动测试完成。

---

## 验证命令速查表

```powershell
# 运行全部测试
pytest -q

# 运行特定测试文件
pytest tests/test_student_repository.py -q
pytest tests/test_students_api.py -q

# Git 检查
git status
git diff
git diff --check

# 启动应用
python run.py

# MCP 检查
mcp dev app/mcp/server.py

# CLI 检查
flask init-admin --help
flask init-admin

# 迁移脚本
python scripts/migrate_v1_to_v2.py --dry-run
python scripts/migrate_v1_to_v2.py
```
