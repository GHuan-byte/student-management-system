# Architecture Decisions — Student Management System V2

> 记录 V2 项目的关键架构决策（Architecture Decision Records, ADR）。

---

## ADR-001：分层架构

**状态：** ✅ 已确认

**决策：**
系统采用严格的三层架构，依赖方向不可逆：

```
HTTP Route / MCP Tool
        ↓
    Service
        ↓
  Repository
        ↓
    SQLite
```

**规则：**
1. HTTP Route 不得直接执行 SQL。
2. MCP Tool 不得直接执行 SQL。
3. Repository 只负责数据库访问和参数化 SQL。
4. Service 负责业务规则、验证和数据标准化。
5. HTTP Route 与 MCP Tool 必须复用同一个 Service。
6. 不得吞掉异常或伪造成功结果。

---

## ADR-002：应用工厂模式

**状态：** ✅ 已确认

**决策：**
Flask 应用使用 `create_app()` 应用工厂模式 + Blueprint 注册。

**理由：**
- 便于测试（每次测试创建独立应用实例）
- Blueprint 便于路由按模块组织
- 配置可在创建时注入

**文件结构：**
```
app/
├── __init__.py          # create_app()
├── config.py            # 配置类
├── database.py          # 数据库连接管理
├── repositories/
│   ├── __init__.py
│   ├── student_repository.py
│   └── user_repository.py
├── services/
│   ├── __init__.py
│   ├── student_service.py
│   ├── auth_service.py
│   └── chat_service.py
├── routes/
│   ├── __init__.py
│   ├── auth.py          # auth Blueprint
│   ├── students.py      # students Blueprint
│   └── chat.py          # chat Blueprint
├── utils/
│   ├── __init__.py
│   ├── response.py      # 统一响应工具
│   └── errors.py        # 错误处理装饰器
└── mcp/
    ├── __init__.py
    ├── server.py        # FastMCP 服务器
    ├── student_tools.py # 学生工具注册
    └── client.py        # MCP Client
```

---

## ADR-003：认证方式

**状态：** ✅ 已确认

**决策：**
采用 Flask-Login + Flask Session cookie 认证。

**理由：**
- 单体应用的成熟方案
- V1 已使用类似模式，迁移成本低
- 无需引入 JWT 等额外依赖
- Flask-Login 提供 `login_required`、`current_user` 等便利设施

**角色：** `"admin"` 和 `"teacher"`

**初始管理员：** 通过 `flask init-admin` CLI 命令创建，交互式输入用户名和密码。源码中不硬编码任何凭据。

---

## ADR-004：数据模型 — grade 字段重定义

**状态：** ✅ 已确认

**决策：**
- `grade` 字段改为 INTEGER 类型，表示"成绩"，取值范围 0–100。
- 原 V1 中 `grade` 表示的"年级"语义，改用 `cohort` 字段（TEXT）。

**`students` 表最终字段：**

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PK, AUTOINCREMENT | 内部标识 |
| `student_number` | TEXT | NOT NULL, UNIQUE | 学号 |
| `name` | TEXT | NOT NULL | 姓名 |
| `gender` | TEXT | NOT NULL | 性别 |
| `age` | INTEGER | NOT NULL | 年龄 |
| `major` | TEXT | NOT NULL | 专业 |
| `cohort` | TEXT | NOT NULL | 届/年级（如 "2023级"） |
| `grade` | INTEGER | NOT NULL, CHECK(0-100) | 成绩 |
| `phone` | TEXT | NULLABLE | 电话 |
| `email` | TEXT | NULLABLE | 邮箱 |
| `created_at` | TEXT | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | TEXT | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 更新时间 |

---

## ADR-005：统一 API 响应格式

**状态：** ✅ 已确认

**决策：**
所有 API 响应使用统一 JSON 结构：

```json
{
  "success": true,
  "data": null,
  "message": "",
  "error": null,
  "meta": {}
}
```

**分页信息** 放在 `meta` 中：

```json
{
  "success": true,
  "data": [...],
  "message": "",
  "error": null,
  "meta": {
    "page": 1,
    "page_size": 15,
    "total": 100,
    "total_pages": 7
  }
}
```

---

## ADR-006：API 字段使用英文

**状态：** ✅ 已确认

**决策：**
- API 请求和响应的字段名统一使用英文（如 `student_number`、`cohort`）。
- 前端显示时映射为中文标签（如 `student_number` → "学号"）。
- 导入导出时保留 V1 的中英文列名双向映射机制。

---

## ADR-007：前端采用 ES Modules

**状态：** ✅ 已确认

**决策：**
前端 JavaScript 采用原生 ES Modules（`<script type="module">`），不使用打包工具。

**文件结构：**
```
static/
├── css/
│   └── style.css
└── js/
    ├── core/
    │   ├── api.js       # fetch 封装 + 统一错误处理
    │   └── utils.js     # DOM 工具、格式化
    ├── pages/
    │   ├── login.js
    │   ├── students.js  # 学生列表页面主逻辑
    │   └── dashboard.js # 首页统计
    └── components/
        └── ai_assistant.js  # AI 侧边栏
```

**前端统一状态（学生列表）：**

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

**行为规则：**
1. 搜索关键词变化后回到第一页。
2. 排序变化后回到第一页。
3. 全选默认只作用于当前页。
4. 翻页后重新计算全选状态。
5. 删除当前页最后一条记录后自动退回上一页。
6. 不得重复绑定事件监听器。
7. 不得在多个模块独立保存同一份列表状态。

---

## ADR-008：MCP 第一版仅只读

**状态：** ✅ 已确认

**决策：**
MCP Server 第一版仅开放只读工具。写入工具（`add_student`, `update_student`, `upsert_student`）在后续变更中经过安全审查后再开放。

**初始只读工具集：**

| 工具名 | 说明 |
|--------|------|
| `list_students` | 列出学生（带分页） |
| `search_students` | 跨字段搜索 |
| `get_student_by_id` | 按 ID 查询 |
| `get_student_by_number` | 按学号查询 |
| `count_students` | 统计总数 |
| `get_student_stats` | 统计数据 |

---

## ADR-009：MCP 传输策略

**状态：** ✅ 已确认

**决策：**
- **开发期：** 默认使用 stdio 传输（`mcp.run(transport="stdio")`）。
- **未来远程部署：** 采用 **Streamable HTTP** 作为主要远程传输方案。
- 旧式 SSE（Server-Sent Events）不作为主要方案。
- stdio 与 HTTP 传输通过适配层分离，切换传输方式时不修改业务代码。

---

## ADR-010：MCP Tool 与 HTTP Route 共用 Service

**状态：** ✅ 已确认

**决策：**
MCP Tool 和 HTTP Route 必须调用同一套 Service 方法。Service 是业务逻辑的唯一入口，避免以下 V1 的反模式：

```
❌ V1：MCP Server → import db → 直接执行 SQL
✅ V2：MCP Tool → Service → Repository → SQLite
```

---

## ADR-011：聊天数据存储策略

**状态：** ✅ 已确认

**决策：**
- 聊天会话表命名为 `chat_sessions`（不使用 `sessions` 以避免与 Flask Session 混淆）。
- **当前阶段不实现 SQLite 存储。** 消息和会话数据在 AI Chat 功能实现时先用合适方式处理。
- 未来迁移到 SQLite 的时机：当聊天数据持久化需求明确且功能稳定后。

---

## ADR-012：测试数据库策略

**状态：** ✅ 已确认

**决策：**
测试数据库使用 pytest `tmp_path` fixture 创建临时文件数据库，不默认使用独立连接的 `:memory:` 数据库。

**理由：**
- `tmp_path` 临时文件数据库与实际运行环境更接近。
- 避免 `:memory:` 在不同连接间的隔离问题。
- 测试结束后自动清理。

---

## ADR-013：文件命名约定

**状态：** ✅ 已确认

**决策：**
Repository 文件使用完整的蛇形命名（snake_case + 全称）：

| 文件 | 命名 |
|------|------|
| 学生 Repository | `student_repository.py` |
| 用户 Repository | `user_repository.py` |
| MCP Client | `app/mcp/client.py` |

---

## ADR-014：Clean Baseline 已完成

**状态：** ✅ 已确认

**决策：**
项目基线（Git 仓库、目录结构、README、AGENTS.md、openspec/ 初始化）已完成。

**Project Foundation 是第一个实现阶段。** 该阶段将从 Flask 应用工厂、配置管理、统一响应工具和错误处理装饰器开始。

---

## ADR-015：阶段串行执行

**状态：** ✅ 已确认

**决策：**
阶段按顺序串行执行，不并行实施 REST API 和 MCP 阶段。

**理由：**
- 每次聚焦一个交付物，降低认知负载。
- 每个阶段的产出经过验证后再进入下一阶段。
- 便于在任一阶段发现问题时回滚或调整。
