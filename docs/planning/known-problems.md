# Known Problems — V1 Anti-patterns & Risks

> 旧项目中发现的架构问题、反模式和安全隐患。V2 须逐一解决。

---

## 架构反模式

### AP-01：无分层架构

`db.py` 混合了连接管理、数据验证、学生 CRUD、用户 CRUD 和排序白名单。

```
db.py
├── 数据库连接（get_db）
├── 错误处理装饰器（handle_errors）
├── 数据验证（validate_student_data）
├── 学生 CRUD（get_students, get_student_by_id, add_student, ...）
├── 用户操作（get_user_by_username, create_user, ...）
├── 排序白名单（SORT_WHITELIST）
├── 统计（get_student_stats, get_gender_distribution, ...）
└── Schema 初始化（init_db）
```

**影响：** 难以测试、难以维护、MCP 和 HTTP 无法复用逻辑。

### AP-02：MCP Server 直接导入 db.py

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db import (get_students, get_student_by_id, add_student, ...)
```

**影响：** 业务逻辑分散、认证/授权无法统一、绕过应用层。

### AP-03：无测试覆盖

零测试文件。所有功能仅靠手动测试验证。

**影响：** 回归风险高、重构无安全网、无法 CI。

### AP-04：无数据库迁移系统

`updated_at` 列通过 try/except 的 `ALTER TABLE ADD COLUMN` 添加。

```python
try:
    cursor.execute("ALTER TABLE students ADD COLUMN updated_at TEXT")
except sqlite3.OperationalError:
    pass  # 列已存在
```

**影响：** 无法可靠追踪 schema 变更、难以回滚。

---

## 安全风险

### SEC-01：默认管理员凭据硬编码

```python
# auth.py 中
if username == "admin" and password == "admin123":
    # 创建默认管理员
```

**影响：** 源码泄露即密码泄露。所有部署实例使用相同默认凭据。

### SEC-02：MCP 写入工具无权限控制

任何能连接 MCP Server 的客户端都可以调用 `add_student`、`update_student`、`upsert_student`。

**影响：** 无认证、无授权、无审计。

### SEC-03：错误处理可能泄露内部信息

`handle_errors` 装饰器捕获所有异常并返回 JSON，但异常信息可能暴露内部路径或 schema。

### SEC-04：日志可能输出完整学生信息

未对日志中的个人身份信息（PII）进行脱敏。

---

## 数据问题

### DATA-01：缺少 created_at 字段

`students` 表没有 `created_at`，无法追踪记录创建时间。

### DATA-02：updated_at 为 NULLABLE

通过 ALTER TABLE 添加，存量数据为 NULL。

### DATA-03：JSON 文件存储会话和聊天历史

- 无索引，查询效率低
- 无并发控制，多请求可能损坏数据
- 随数据量增长，加载耗时递增
- 事务安全性缺失

### DATA-04：page_size 上限 100

```python
page_size = min(page_size, 100)
```

**影响：** 大数据集可能意外截断。需根据实际情况评估上限是否合理。

### DATA-05：字段语义混淆

`grade` 字段既是"年级"（TEXT）又可能被误解为"成绩"（数值）。

---

## 代码质量问题

### CODE-01：run.py 为空文件

无实际启动脚本。

### CODE-02：不良的 asyncio.run() 嵌套

`ai_service.py` 在同步函数内调用 `asyncio.run()` 执行 MCP Client 的异步操作。如果 Flask 运行在异步 WSGI 服务器上可能导致运行时错误。

### CODE-03：错误响应格式不一致

某些端点返回 `{"success": ..., "data": ...}`，其他端点返回扁平数组或不同结构。

### CODE-04：students.db/ 目录为空

项目中有 `students.db/` 目录（注意是目录），但实际数据库文件在 `data/students.db`。可能是命名错误或遗留。

---

## 前端问题

### UI-01：前端状态在全局作用域

`students.js` 中的状态变量（`currentPage`、`selectedStudentIds` 等）全部在全局作用域，可能与其他脚本冲突。

### UI-02：无模块化

~500 行的 `students.js` 是单体文件，所有逻辑耦合在一起。

### UI-03：事件监听器重复绑定风险

手动 DOM 操作中，如果多次调用渲染函数，可能导致事件监听器重复绑定。

### UI-04：登录默认凭据暴露在页面底部

`login.html` 底部硬编码显示 `admin / admin123`。

---

## V2 必须解决的项目

| 编号 | 问题 | 方案 | 优先级 |
|------|------|------|--------|
| AP-01 | 无分层架构 | Route → Service → Repository | P0 |
| AP-02 | MCP 直接导入 db | MCP Tool → Service → Repository | P1 |
| AP-03 | 无测试 | pytest + 分层测试 | P0 |
| AP-04 | 无迁移系统 | 独立迁移脚本 | P2 |
| SEC-01 | 凭据硬编码 | `flask init-admin` CLI | P0 |
| SEC-02 | MCP 写入无权限 | V2 第一版仅只读 | P1 |
| SEC-03 | 错误信息泄露 | 统一错误处理，不暴露内部细节 | P0 |
| SEC-04 | 日志 PII 泄露 | 日志脱敏策略 | P1 |
| DATA-01 | 缺 created_at | schema 正式纳入 | P0 |
| DATA-02 | updated_at NULLABLE | schema 设为 NOT NULL | P0 |
| DATA-03 | JSON 存聊天数据 | 未来迁移到 SQLite | P2 |
| DATA-04 | page_size 上限 | 保留上限但根据场景调整 | P0 |
| DATA-05 | grade 语义混淆 | 拆分 cohort + grade | P0 |
| CODE-01 | run.py 为空 | 实现启动脚本 | P0 |
| CODE-02 | asyncio.run() 嵌套 | 统一同步调用 | P1 |
| CODE-03 | 响应格式不一致 | 统一响应工具函数 | P0 |
| CODE-04 | 空目录 | 清理 | P0 |
| UI-01 | 全局作用域状态 | ES Modules 封装 | P0 |
| UI-02 | 单体 JS | 拆分为模块 | P0 |
| UI-03 | 事件重复绑定 | 事件委托或绑定检查 | P0 |
| UI-04 | 页面显示默认密码 | 删除硬编码显示 | P0 |
