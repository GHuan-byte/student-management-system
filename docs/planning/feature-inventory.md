# Feature Inventory — V1 → V2 Mapping

> 用于追踪旧项目（V1）已有功能与 V2 规划的关系。

---

## 图例

| 标记 | 含义 |
|------|------|
| ✅ V1 已有 | 旧项目已实现 |
| 🔄 V2 改进 | V2 须重写/改进 |
| 🆕 V2 新增 | V2 全新功能 |
| ❌ V2 废弃 | V1 有但 V2 不用 |

---

## 功能清单

### 认证模块

| 功能 | V1 | V2 | 优先级 | 说明 |
|------|----|----|--------|------|
| 登录 | ✅ | 🔄 | P0 | V2 改用 Flask-Login |
| 登出 | ✅ | 🔄 | P0 | V2 改用 Flask-Login |
| 当前用户查询 | ✅ | 🔄 | P0 | `/api/auth/me` |
| Session 会话管理 | ✅ | 🔄 | P0 | Flask Session，无 hardcoded 凭据 |
| 角色权限 (admin/teacher) | ✅ | 🔄 | P0 | 保留 `@login_required` + `@role_required` |
| 默认管理员初始化 | ✅ | ❌ | P0 | V1 源码硬编码 → V2 用 `flask init-admin` CLI |
| 用户注册 | ❌ | ❌ | -- | 不在 V2 范围内 |

### 学生 CRUD

| 功能 | V1 | V2 | 优先级 | 说明 |
|------|----|----|--------|------|
| 学生列表（分页） | ✅ | 🔄 | P0 | V2 统一响应格式 + meta 分页 |
| 学生详情 | ✅ | 🔄 | P0 |  |
| 新增学生 | ✅ | 🔄 | P0 | V2 通过 Service 层验证 |
| 编辑学生 | ✅ | 🔄 | P0 | V2 通过 Service 层验证 |
| 单条删除 | ✅ | 🔄 | P0 | admin only |
| 批量删除 | ✅ | 🔄 | P0 | admin only，`DELETE /api/students/batch` |

### 搜索与排序

| 功能 | V1 | V2 | 优先级 | 说明 |
|------|----|----|--------|------|
| 跨字段关键词搜索 | ✅ | 🔄 | P0 |  |
| 多字段排序（白名单） | ✅ | 🔄 | P0 |  |
| 当前页全选 | ✅ | 🔄 | P0 | V2 用 ES Modules 重构 |

### 导入导出

| 功能 | V1 | V2 | 优先级 | 说明 |
|------|----|----|--------|------|
| CSV 导入 | ✅ | 🔄 | P1 | pandas + 中英文列名映射 |
| Excel 导入 | ✅ | 🔄 | P1 | openpyxl |
| CSV 导出 | ✅ | 🔄 | P1 | UTF-8 BOM |
| Excel 导出 | ✅ | 🔄 | P1 |  |
| 列名映射（中/英） | ✅ | 🔄 | P1 | 保留 V1 的双向映射设计 |
| 导入去重 | ✅ | 🔄 | P1 | 按 student_number upsert |

### MCP 工具

| 功能 | V1 | V2 | 优先级 | 说明 |
|------|----|----|--------|------|
| health_check | ✅ | 🔄 | P1 | 基础工具 |
| echo_message | ✅ | 🔄 | P1 | 基础工具 |
| database_status | ✅ | ❌ | -- | V2 不再暴露内部 schema 信息 |
| get_student_table_schema | ✅ | ❌ | -- | 同上，安全考虑 |
| count_students | ✅ | 🔄 | P1 | 只读 |
| list_students | ✅ | 🔄 | P1 | 只读 |
| search_students | ✅ | 🔄 | P1 | 只读 |
| get_student_by_id | ✅ | 🔄 | P1 | 只读 |
| get_student_by_number | ✅ | 🔄 | P1 | 只读 |
| get_student_stats | ✅ | 🔄 | P1 | 只读 |
| add_student | ✅ | 🆕 | P2 | V2 第一版仅只读，写入工具后续开放 |
| update_student | ✅ | 🆕 | P2 | 同上 |
| upsert_student | ✅ | 🆕 | P2 | 同上 |

### AI Chat

| 功能 | V1 | V2 | 优先级 | 说明 |
|------|----|----|--------|------|
| AI 对话接口 | ✅ | 🔄 | P1 | POST /api/chat |
| MCP Tool Call 编排 | ✅ | 🔄 | P1 | V2 改进错误处理 |
| 会话管理（CRUD） | ✅ | 🔄 | P1 | V2 命名为 chat_sessions |
| 会话重命名 | ✅ | 🔄 | P1 |  |
| 消息历史查询 | ✅ | 🔄 | P1 |  |
| 上下文窗口限制 | ✅ | 🔄 | P1 | V2 保留最近 N 条机制 |
| 语音输入 | ✅ | 🔄 | P2 | Web Speech API |
| Markdown 渲染 | ✅ | 🔄 | P1 |  |
| 数据持久化（SQLite） | ❌ | 🆕 | P2 | V1 用 JSON 文件，V2 未来迁移到 SQLite |

### 统计仪表盘

| 功能 | V1 | V2 | 优先级 | 说明 |
|------|----|----|--------|------|
| 学生总数统计 | ✅ | 🔄 | P1 | GET /api/students/stats |
| 性别分布统计 | ✅ | 🔄 | P1 |  |
| 专业分布统计 | ✅ | 🔄 | P1 |  |
| 仪表盘首页 | ✅ | 🔄 | P1 |  |
| 成绩分布统计 | ❌ | 🆕 | P2 | 新增（grade 字段引入后） |

### 数据迁移

| 功能 | V1 | V2 | 优先级 | 说明 |
|------|----|----|--------|------|
| 旧数据库迁移脚本 | ❌ | 🆕 | P2 | 从 V1 迁移到 V2 |
| 可重复运行 | ❌ | 🆕 | P2 | 识别已迁移状态 |
| 数据完整性验证 | ❌ | 🆕 | P2 | 迁移后校验 |

### 基础设施

| 功能 | V1 | V2 | 优先级 | 说明 |
|------|----|----|--------|------|
| 分层架构 | ❌ | 🆕 | P0 | Route → Service → Repository |
| 统一响应格式 | ❌ | 🆕 | P0 | `{success, data, message, error, meta}` |
| 配置集中管理 | ❌ | 🆕 | P0 | `config.py` |
| 数据验证（Service） | ❌ | 🆕 | P0 | V1 验证混在 db.py 中 |
| 测试覆盖 | ❌ | 🆕 | P0 | pytest |
| MCP 传输适配 | ❌ | 🆕 | P1 | stdio / Streamable HTTP 适配层 |
| 错误处理装饰器 | ✅ | 🔄 | P0 | V2 更严格、不吞异常 |

---

## 优先级定义

| 等级 | 含义 | 阶段 |
|------|------|------|
| P0 | 必须包含，MVP 核心 | 阶段 4–10 |
| P1 | 重要功能，MVP 后尽快完成 | 阶段 11–13 |
| P2 | 增强功能，有明确需求时实施 | 阶段 14（含后续） |
| ❌ | 废弃/不在范围 | -- |

---

## 字段变更记录（V1 → V2）

| V1 字段 | V2 字段 | 类型 | 变更说明 |
|---------|---------|------|---------|
| `grade` (年级) | `cohort` | TEXT | 重命名，语义为"届/年级" |
| -- (无) | `grade` | INTEGER (0-100) | 新增，表示"成绩" |
| `updated_at` (后期添加) | `updated_at` | TEXT NOT NULL | 正式纳入 schema |
| -- (无) | `created_at` | TEXT NOT NULL | 新增 |
