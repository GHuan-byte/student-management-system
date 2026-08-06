# Tasks — add-ai-guided-student-actions

> 任务类型标注约定：`[TDD]` 自动化单元测试先行、`[API]` API/路由测试、`[SVC]`
> Service 层测试、`[JS]` JavaScript 行为测试、`[INT]` 集成测试、`[USER]` 用户人工验收。
> 依赖说明见各阶段开头。

## 1. 基础契约（阶段一）

> 目标：定义结构化动作模型、状态机、幂等规则与前后端接口契约。无 UI 改动。
> 依赖：本阶段内部按 1.1 → 1.2 → 1.3 → … 顺序执行；其余阶段依赖本阶段完成。

- [x] 1.1 定义动作类型白名单与读/写分类（`create_student`/`update_student`/`delete_student` 写；`search_students`/`get_student`/`count_students` 读）
- [x] 1.2 定义动作状态枚举与合法状态转换（`pending`/`animating`/`waiting_confirmation`/`executing`/`succeeded`/`failed`/`cancelled`/`expired`）
- [x] 1.3 定义结构化动作数据模型（`action_id`/`action_type`/`payload`/`target`/`changes`/`requires_confirmation`/`status`/`created_at`/`expires_at`/`result`/`error`）
- [x] 1.4 定义动作状态机校验模块（`app/services/ai_action.py`）及非法转换拒绝逻辑
- [x] 1.5 定义幂等执行规则：`action_id` 至多执行一次、Token 单次消费、动作状态前置检查
- [x] 1.6 定义前后端接口契约：`data.action`（浏览器安全 action 对象）、`GET /api/chat/actions/<id>`（安全展示数据，不含 Token）、`POST /api/chat/actions/<id>/confirm`（action_id 确认，服务端消费 Token）、`POST /api/chat/actions/<id>/cancel`
- [x] 1.7 [TDD] 动作状态机单元测试（合法/非法转换、终止态、过期）
- [x] 1.8 [SVC] 动作模型校验单元测试（payload/target 白名单与 `StudentService` 规则一致）

## 2. 前端基础动画框架（阶段二）

> 依赖：阶段一（动作模型/契约）。目标：动画运行时与稳定标识，不含具体动作流程。

- [x] 2.1 为学生页元素添加稳定且页面内唯一的 `data-ai-target`（新增按钮、搜索框/按钮、弹窗、表单字段、提交/取消）
- [x] 2.2 添加动画资源入口：`app/static/js/ai_action_runner.js` 与 `app/static/css/ai_action_runner.css`（`ai-guide-` 前缀），在 `base.html`/`students.html` 按需加载一次
- [x] 2.3 实现模拟鼠标元素（`moveTo`/`setCursor`，跟随滚动）
- [x] 2.4 实现页面遮罩 `.ai-guide-mask` 与当前字段高亮 `.ai-guide-field-highlight`
- [x] 2.5 实现步骤提示 `.ai-guide-status`（中文步骤文案）
- [x] 2.6 实现 `AIActionRunner` 核心：步骤队列、async/await 顺序、`waitFor(data-ai-target)` 元素等待、元素缺失报错
- [x] 2.7 实现取消控制（确认栏取消 → 服务端取消 → 不执行写）；暂停/继续/跳过留待后续阶段复用同一框架
- [x] 2.8 实现人工干预检测（关键步骤前 DOM 状态校验，缺失即安全中止）
- [x] 2.9 实现受控 action JSON 解析与本地 `action_type` 白名单校验（未知类型拒绝且不播放）
- [x] 2.10 实现语义字段名 → `data-ai-target` 固定映射（仅前端固定代码，后端不返回选择器）
- [x] 2.11 实现统一 Action Executor 封装（确认后仅调用 `POST /api/chat/actions/<id>/confirm`，服务端消费 Token）
- [x] 2.12 [JS] 动画框架测试（waitFor 超时、鼠标移动、逐字填写、选择下拉、取消；以静态+模板测试落地）
- [x] 2.13 [JS] 缺失 `data-ai-target` 时报"目标元素不存在"、中止动画且不进入写操作
- [x] 2.14 [JS] JSON 解析/白名单/固定映射测试（未知 `action_type`、注入选择器被忽略、标识唯一性；以静态+模板测试落地）

## 3. 添加学生动画（阶段三，最小端到端切片）

> 依赖：阶段一、阶段二。本阶段优先交付完整可验收切片。

- [x] 3.1 扩展 `AIChatService._build_pending_action`：生成 `data.action` 元数据（`action_id`/`action_type`/`payload`/`target`/`target_page`/`status`/时间戳）并把 Token 写入动作存储
- [x] 3.2 实现进程内动作存储 `app/services/ai_action_store.py`（按 `action_id` 索引 `{token, action_type, tool_name, arguments, status, user_id, created_at, expires_at}`）
- [x] 3.3 新增 `GET /api/chat/actions/<action_id>`（同用户、未过期未执行未取消才返回安全展示数据，不含 Token，`Cache-Control: no-store`）
- [x] 3.4 新增 `POST /api/chat/actions/<action_id>/confirm`（CSRF + Session + 同用户 + 状态 + 工具角色校验；消费服务端持有 Token，经现有 MCP→`StudentService` 链路执行；返回 `action_id`/`status`/`action_result`）
- [x] 3.5 新增 `POST /api/chat/actions/<action_id>/cancel`（服务端置 `cancelled`，阻止后续确认）
- [x] 3.6 前端：读取受控 action JSON → 本地白名单校验 `action_type` → 保存最小 `action_id` 引用后跳转 `/students` → 页面加载后按 `action_id` GET 安全动作数据
- [x] 3.7 前端：模拟鼠标移动并点击 `student-add-button`（非提交按钮），经现有按钮事件打开新增弹窗
- [x] 3.8 前端：按 `payload` 逐字段填写（触发标准 `input`/`change` 事件），定位并高亮 `student-submit-button`，停在提交前等待确认
- [x] 3.9 前端：引导模式守卫——`students.js` 的 `handleModalSubmit` 在引导期间失效；动画不对提交按钮派发 click/submit
- [x] 3.10 前端：用户确认后经统一 Action Executor 调用 `POST /api/chat/actions/<action_id>/confirm` → 成功后刷新列表 + 高亮新记录 → AI 面板显示结果
- [x] 3.11 表单"预览锁定"：AI 引导期间输入框只读/下拉禁用并显示 AI 确认栏
- [x] 3.12 [SVC] `_build_pending_action` 生成动作元数据且不含 Token/敏感字段
- [x] 3.13 [API] `GET /api/chat/actions/<id>` 权限/过期/已执行/跨用户隔离/不含 Token 测试
- [x] 3.14 [API] `POST /api/chat/actions/<id>/confirm` 越权、状态、action_id↔Token 一致性、单次消费测试
- [x] 3.15 [API] `POST /api/chat/actions/<id>/cancel` 取消后确认被拒绝测试
- [x] 3.16 [TDD] 确认前数据库不变化、确认后只新增一条（含重复确认/并发确认）
- [x] 3.17 [JS] 添加动画流程测试（弹窗打开、逐字填写、暂停点、确认后单次请求；以静态+模板测试落地）
- [x] 3.18 [JS] 视觉点击提交按钮不触发 click/submit、不产生第二次写请求（静态断言 + 后端单次消费测试）
- [x] 3.19 [JS] 引导模式下 `handleModalSubmit` 失效、不调用学生 REST 写 API（静态断言）
- [x] 3.20 [INT] 端到端：AI 指令 → 动作 → 动画 → 确认 → 列表出现新记录 → 高亮；重复确认不重复创建（后端集成测试）
- [x] 3.21 [JS] 学号重复/后端失败时不刷新为成功、不播放成功动画（后端 failed 状态 + 前端失败分支静态断言）
- [x] 3.22 [USER] 浏览器人工验收：AI 输入添加学生指令，确认前数据不变，确认后列表新增并高亮

## 4. 异常恢复与安全（阶段四）

> 依赖：阶段二、阶段三。跨场景健壮性。

- [x] 4.1 页面刷新恢复：sessionStorage 最小引用 + 服务端按 `action_id` 恢复安全展示数据，不重播已执行动作
- [x] 4.2 Token 过期/被篡改/已使用、action_id 与 Token 不一致：结构化错误、动作拒绝、无写入
- [x] 4.3 防重复执行：重复确认、刷新后重试、并发确认均至多一次写入
- [x] 4.4 用户取消：服务端取消 + 前端取消均不执行写；取消后不可再确认
- [x] 4.5 用户手动干预：动画中关闭弹窗/改字段/翻页 → 检测并安全中止，不继续陈旧动画
- [x] 4.6 网络失败：不自动重发写请求，显示安全失败信息；网络超时先查动作状态再决定是否重试（前端状态查询细化留待后续）
- [x] 4.7 DOM 目标丢失：`waitFor` 超时报"目标元素不存在"、中止动画且不进入写操作
- [x] 4.8 安全校验：禁止 `eval`/`new Function`/AI 输出脚本与任意选择器/任意 SQL/未确认写
- [x] 4.9 日志与脱敏：Token、cookie、session、学生整条记录脱敏；带 `request_id`；不记录完整学生敏感信息
- [x] 4.10 [TDD] 幂等与并发确认测试（复用现有 `AIActionConfirmation` 并发思路）
- [x] 4.11 [API] 查询/确认/取消端点越权、跨用户、已执行、过期、action_id↔Token 不一致测试
- [x] 4.12 [JS] 刷新恢复、人工干预、网络失败、DOM 丢失前端运行时测试（本轮为静态/模板断言，运行时测试留待后续）
- [x] 4.13 [SVC] 日志脱敏验证（动作/确认过程日志无敏感值）
- [x] 4.14 [TDD] failed 为终止态：重试需创建新动作（新 `action_id`、新 Token）
- [x] 4.15 [SVC] 客户端不得自行置 `succeeded`/`executing` 等；`succeeded` 仅由服务端在真实成功后设置
- [x] 4.16 进程内动作存储限制验证与文档：重启后动作安全过期、不误执行；在 design/代码 docstring 记录限制与未来持久化升级点（不扩展为 Redis/Celery/微服务）

## 5. 测试与验收汇总（阶段五）

> 依赖：阶段一至四。回归与全量验证。

- [x] 5.1 运行最小相关测试（动作模型、状态机、动作存储、确认链路）
- [x] 5.2 运行完整测试套件（`pytest -q`），确认学生 CRUD/AI Chat/MCP/日志无回归
- [x] 5.3 执行 `git diff --check` 与 Git Diff 审查，确认无无关文件变更
- [x] 5.4 [JS] 补充 `data-ai-target` 存在性与唯一性渲染测试（模板改动尽早发现丢失/重复）
- [ ] 5.5 [USER] 全量浏览器验收：添加学生动画、刷新恢复、取消、失败场景（搜索/修改/删除不做动画）
- [x] 5.6 更新 `.env.example`、README 与任务状态；生成最终验证证据（真实命令与结果）（无新增环境变量，`.env.example` 无变化；README 能力清单已补充 AI 引导动画；完整测试证据见本轮 5.1/5.2 输出）
- [ ] 5.7 停止：不自动进入下一阶段、不自动归档/合并

## 实现顺序注记

- 阶段三（添加学生动画）是本 Change 的**唯一动画实现目标**。
- 搜索、修改、删除均不做引导动画（仍为既有聊天只读/确认能力）。
- 阶段四、五的测试应在阶段三切片交付时同步开始编写，避免最后一刻集中补测。
