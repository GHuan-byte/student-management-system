# AGENTS.md

## 1. 项目定位

本仓库是 **Student Management System V2**，用于从零重写学生管理系统。

旧项目位于：

`D:\Python\student-management-system`

V2 项目位于：

`D:\Python\student-management-system-v2`

旧项目只用于读取、分析和迁移参考。除非用户明确要求，否则不得修改旧项目中的任何文件。

---

## 2. 当前阶段

当前项目处于：

**需求分析、OpenSpec 规划和架构设计阶段。**

在规划通过之前，不得直接生成完整业务代码，不得一次性实现全部系统。

---

## 3. 技术约束

默认使用以下技术栈：

- Python
- Flask
- SQLite
- Jinja2
- HTML
- CSS
- Vanilla JavaScript
- MCP
- OpenAI-compatible Chat Completions API
- pytest

除非经过用户确认并写入 OpenSpec Change，否则不得引入：

- React
- Vue
- Django
- FastAPI
- Redis
- Celery
- 微服务
- 消息队列
- 第二种数据库
- 复杂前端状态管理框架

---

## 4. 架构规则

系统必须遵守以下依赖方向：

```text
HTTP Route / MCP Tool
        ↓
Service
        ↓
Repository
        ↓
SQLite
```

必须遵守：

1. HTTP Route 不得直接执行 SQL。
2. MCP Tool 不得直接执行 SQL。
3. Repository 只负责数据库访问和 SQL。
4. Service 负责业务规则、验证和数据标准化。
5. HTTP Route 与 MCP Tool 必须复用同一个 Service。
6. 配置必须集中管理。
7. 数据库路径不得分散硬编码。
8. V2 开发数据库不得直接使用旧项目数据库。
9. MCP stdio 与 HTTP 传输必须通过适配层分离。
10. 前端列表状态必须只有一个事实来源。
11. 所有 API 必须使用统一 JSON 响应结构。
12. 不得吞掉异常或伪造成功结果。

推荐 API 响应结构：

```json
{
  "success": true,
  "data": null,
  "message": "",
  "error": null,
  "meta": {}
}
```

---

## 5. 计划功能范围

V2 计划支持：

- 学生列表
- 学生详情
- 新增学生
- 编辑学生
- 单个删除
- 批量删除
- 搜索
- 分页
- 排序
- 当前页全选
- Excel 或 CSV 导入
- Excel 或 CSV 导出
- 学生统计
- AI 助手
- MCP 学生工具
- 旧数据库迁移

不得一次性实现全部功能。每次只能实施用户明确指定的一个阶段。

---

## 6. OpenSpec 工作流

中大型功能必须使用 OpenSpec。

执行顺序：

1. Explore：分析需求与现有上下文。
2. Propose：创建 Change。
3. Review：审查 proposal、spec、design 和 tasks。
4. Apply：只实施已批准范围。
5. Verify：验证实现与规范一致。
6. Sync：同步正式规范。
7. Archive：完成后归档 Change。

没有明确规范时，不得直接开始复杂功能实现。

---

## 7. Harness 式阶段门

每个阶段必须明确：

- 阶段目标
- 输入
- 输出
- 允许修改的文件
- 禁止修改的范围
- 验证命令
- 验收标准
- 完成证据

建议阶段：

1. Clean Baseline
2. Legacy Audit
3. V2 Architecture
4. Project Foundation
5. Database and Repository
6. Service Layer
7. REST API
8. Student List Frontend
9. Search, Pagination, Sorting and Selection
10. Create, Edit and Delete
11. Import and Export
12. MCP Server
13. MCP Client and AI Chat
14. Legacy Data Migration
15. Final Verification

不得自动进入下一阶段。

---

## 8. 测试与验证

每次实现后必须：

1. 添加或更新测试。
2. 运行最小相关测试。
3. 阶段完成前运行完整测试。
4. 检查 Git Diff。
5. 报告实际执行的命令。
6. 基于真实输出说明结果。
7. 未验证时不得声称完成。

常用命令：

```powershell
pytest
pytest -q
git status
git diff
git diff --check
```

应用骨架建立后，还应执行启动检查或健康检查。

---

## 9. 数据库规则

1. 使用统一连接模块访问 SQLite。
2. 所有 SQL 必须参数化。
3. 排序字段必须通过显式白名单。
4. Schema、初始化和迁移必须独立于请求处理。
5. 搜索、分页、排序、唯一约束和迁移必须有测试。
6. 迁移旧数据库前必须备份。
7. 迁移脚本应可重复运行，或能识别已迁移状态。
8. 运行时数据库文件不得提交到 Git。

计划学生字段：

- `id`
- `student_number`
- `name`
- `gender`
- `age`
- `major`
- `grade`
- `phone`
- `email`
- `created_at`
- `updated_at`

最终字段与约束必须先通过 OpenSpec 审核。

---

## 10. 前端状态规则

学生列表应维护统一状态：

- `currentPage`
- `pageSize`
- `keyword`
- `sortBy`
- `sortOrder`
- `selectedIds`
- `total`
- `totalPages`
- `loading`

行为规则：

1. 搜索关键词变化后回到第一页。
2. 排序变化后回到第一页。
3. 全选默认只作用于当前页。
4. 翻页后重新计算全选状态。
5. 删除当前页最后一条记录后，可自动退回上一页。
6. 不得重复绑定事件监听器。
7. 不得在多个模块独立保存同一份列表状态。

---

## 11. MCP 与 AI 规则

1. MCP Tool 必须调用 Service。
2. 优先实现并验证只读 MCP Tool。
3. 删除等危险 Tool 必须单独管理并具有安全策略。
4. 工具发现和工具调用必须分开测试。
5. OpenAI-compatible Tool 转换必须独立成模块。
6. 避免嵌套 `asyncio.run()`。
7. stdio 与 HTTP 传输必须分离。
8. 不得把 TaskGroup、ExceptionGroup、Schema 或传输错误包装成假成功。
9. 日志与 API 响应不得暴露密钥。

初始只读工具可包括：

- `list_students`
- `search_students`
- `get_student_by_id`
- `get_student_by_number`
- `count_students`
- `get_student_stats`

写入工具需通过新的 OpenSpec Change 批准。

---

## 12. 安全与隐私

不得提交：

- `.env`
- API Key
- 密码
- Session Secret
- 运行时数据库
- 包含学生隐私的上传文件
- 包含学生隐私的导出文件
- 虚拟环境
- 本地日志

`.env.example` 只能包含占位值。

不得在日志中输出完整学生信息、认证信息或 API Key。

---

## 13. 文件修改规则

修改前：

1. 阅读相关 OpenSpec。
2. 阅读现有实现。
3. 列出需要修改的文件。
4. 限定在当前阶段。
5. 不修改无关模块。
6. 不删除规划文档或 OpenSpec 文件。
7. 不修改旧 Worktree。
8. 不执行与任务无关的大范围格式化。

修改后：

1. 运行测试和检查。
2. 检查 Git Diff。
3. 更新任务状态。
4. 报告新增、修改和删除文件。
5. 停止，不自动进入下一阶段。

---

## 14. Git 规则

V2 Worktree 使用：

`rewrite-v2`

开始工作前执行：

```powershell
git branch --show-current
git status
```

预期分支：

```text
rewrite-v2
```

V2 最终验收通过前不得合并到 `main`。

提交应聚焦单一阶段，例如：

- `Initialize V2 project baseline`
- `Add V2 architecture specification`
- `Add student repository layer`
- `Implement student service validation`
- `Add student list API`
- `Add MCP read tools`

不得把多个无关阶段合并到一次提交。

---

## 15. 完成定义

只有同时满足以下条件，任务或阶段才算完成：

- 用户要求的范围已实现。
- 实现符合已批准的规范。
- 相关测试通过。
- 已执行验证命令。
- 已审查 Git Diff。
- 没有无关文件变更。
- 文档或任务状态已更新。
- 已如实说明剩余限制。

不得自动继续下一阶段。