## Why

AI Chat 目前可以把用户的自然语言解析为写操作（新增、修改、删除）并生成待确认的
Pending Action，但整个流程只发生在聊天面板内：用户看到的只是文字摘要和确认按钮，
学生管理页面没有任何对应的可视化过程。非技术用户无法直观判断 AI 即将执行的操作
到底会改哪些字段、改在哪条记录上，误操作风险高、可解释性差。本 Change 为 AI 驱动
的学生操作增加前端可视化动画：AI 解析出结构化动作后，前端自动进入学生管理页、
打开对应弹窗、逐字段填写、停在提交前等待用户确认，确认后才由后端执行一次真实操作。

## What Changes

- 新增"结构化 AI 学生动作"模型：`action_id`、`action_type`（`create_student`、
  `update_student`、`delete_student`、`search_students`、`get_student`、
  `count_students`）、`payload`、`target`、`target_page`、`changes`、
  `requires_confirmation`、`status`、`created_at`、`expires_at`、`result`、`error`，
  以及完整状态机（`pending` → `animating` → `waiting_confirmation` → `executing` →
  `succeeded`/`failed`，另有 `cancelled`、`expired` 终止态）。
- 扩展 AI Chat 响应：新增浏览器可安全消费的 `data.action`（`action_id`、
  `action_type`、`payload`、`target`、`target_page`、`status`、`requires_confirmation`、
  `created_at`、`expires_at`），供前端动画控制器使用；现有 `pending_action` 摘要与
  `confirmation_token` 契约保持不变。
- 新增轻量级服务端动作存储（进程内，按 `action_id` 索引），提供按 `action_id`
  安全查询/恢复动作（不含 Token）、action_id 确认（服务端消费 Token）与服务端取消
  接口；引导写操作复用同一单次签名 Token 核心执行路径（既有 Token 式确认端点保留
  兼容）。
- 新增基于原生 JavaScript 的 JSON 驱动前端动画控制器 `AIActionRunner`：读取后端
  受控 action JSON，先在本地白名单校验 `action_type`，再按步骤队列播放动画；
  支持 async/await 顺序控制、元素等待、模拟鼠标移动与点击、输入框逐字填写
  （触发标准 `input`/`change` 事件）、下拉框选择、当前字段高亮、页面遮罩、
  步骤提示，以及暂停、继续、跳过、取消。
- 新增统一 Action Executor：动画、确认与真实执行共享同一 `action_id`，用户确认后
  前端只调用统一服务端执行入口（引导流程为新增 `POST /api/chat/actions/<action_id>/confirm`，
  服务端持有并消费 Token；既有 `POST /api/chat/actions/confirm` 保留兼容），真实写
  操作至多成功一次；动画本身绝不直接写数据库。
- 为学生管理页的弹窗、表单、按钮、表格等关键元素增加稳定的 `data-ai-target`
  标识（不使用 `nth-child` 等脆弱选择器）。
- 规定后端动作 JSON 只含受控语义动作与学生字段名（`student_number`、`name` 等），
  不含任何 JavaScript、DOM/CSS 选择器、SQL、URL 或可执行字符串；DOM 定位由前端
  本地固定映射（语义字段名 → `data-ai-target`）完成。
- 新增添加学生动画（本 Change 的唯一动画目标）；写操作动画在提交前暂停等待用户确认。
  AI 搜索、修改、删除均不实现引导动画：搜索仍为聊天只读能力，修改/删除仍走既有
  聊天确认流程。
- 新增跨页面动作恢复：AI 助手在 Dashboard 发起、操作发生在 `/students` 时，
  `sessionStorage` 仅保存最小非敏感动作引用；页面加载后通过服务端按 `action_id`
  重新查询安全动作展示数据（不含 Token），写确认走 action_id 端点（服务端持
  Token），Token 不跨页传递；页面刷新不会重复执行动作。
- 更新 `.env.example` 与相关文档（动作 TTL 等新增配置占位）。
- 为动作模型、状态机、动画控制器、幂等执行、日志脱敏、异常恢复等新增测试。

## Capabilities

### New Capabilities
- `ai-guided-student-actions`: 结构化 AI 学生动作模型、状态机、单次执行语义、
  前端 `AIActionRunner` 动画框架、`data-ai-target` 稳定标识契约、跨页面动作恢复，
  以及"动画可视化 / 后端真实操作"边界与安全约束。

### Modified Capabilities
- `ai-chat`: AI 由"调用 MCP 工具"扩展为"生成受控结构化学生动作"；Pending Action
  响应扩展 `action` 元数据；写操作确认仍走现有单次签名 Token；新增按 `action_id`
  查询/取消动作的服务端契约；Token 仍不得进入 `sessionStorage`。
- `student-management-ui`: 学生管理页为关键交互元素提供稳定的 `data-ai-target`
  标识，支持 AI 引导动画叠加层与 AI 成功后列表刷新/高亮，同时保持现有手工 CRUD
  交互契约不变。

## Impact

- **New code areas**: 前端动画运行时（`app/static/js/ai_action_runner.js` 等）、
  动画样式（`app/static/css/ai_action_runner.css`）、结构化动作模型与状态机
  （`app/services/ai_action.py`）、服务端动作存储（`app/services/ai_action_store.py`）、
  动画集成测试与 JavaScript 行为测试。
- **Modified files**: `app/services/ai_chat_service.py`（生成 `data.action` 元数据、
  动作存储集成）、`app/routes/chat.py`（动作查询/确认/取消端点）、`app/templates/students.html`
  与 `_student_form_fields.html`（`data-ai-target`）、`app/static/js/students.js`（监听
  AI 动作事件、刷新与高亮）、`app/static/js/ai_chat.js`（发起引导动画）、
  `app/templates/_ai_chat.html`、`app/static/css/style.css` 或新增独立 CSS、
  `.env.example`（动作 TTL 配置占位）。
- **API changes**: 新增 `GET /api/chat/actions/<action_id>`（安全动作查询/恢复，不含
  Token）、`POST /api/chat/actions/<action_id>/confirm`（action_id 确认，服务端消费
  Token）与 `POST /api/chat/actions/<action_id>/cancel`（取消）；现有 `POST /api/chat`
  响应新增 `data.action`（浏览器安全 action 对象）；现有
  `POST /api/chat/actions/confirm`（Token 式）契约不变以兼容既有测试。
- **Dependency impact**: 无新增运行时依赖；仍为原生 JavaScript、pytest。
- **No schema changes**: 本阶段不新增数据库表；动作存储在进程内存中，限制与后续
  迁移方案在 design.md 中说明。

## Non-Goals

- 不让 AI 执行任意 JavaScript、不引入浏览器自动化框架（Playwright/Selenium 等）。
- 不让 AI 返回并执行任意 CSS 选择器。
- 不让 AI 直接执行 SQL。
- 不操作学生管理范围以外的系统页面（登录页、用户管理页等）。
- 不绕过用户确认机制；动画不能替代真实的后端权限与参数验证。
- 不新增数据库表持久化动作（本阶段）；不引入 React/Vue 等前端框架。
- 不修改学生业务规则、不修改现有手工 CRUD/搜索/分页/排序/批量删除的交互契约。
- 不实现 AI 搜索/修改/删除学生动画（搜索仍为聊天只读能力；修改、删除仍走既有聊天
  确认流程）。

## Risks

- 跨页面（Dashboard → `/students`）时 Pending Action 与 Token 的传递与恢复，
  若实现不当可能导致 Token 丢失或进入 `sessionStorage`。
- 页面刷新/网络超时/重复点击确认导致的重复执行，需要依赖 Token 单次消费与
  `action_id` 幂等校验共同保证。
- 动画播放期间用户手工操作页面（关闭弹窗、改字段、翻页）导致 DOM 状态漂移。
- 动画目标元素（`data-ai-target`）在模板改动后丢失，需要尽早发现机制。
- 误把"动画已播放"当作"后端已成功"，后端失败时仍显示成功效果。

## Success Criteria

1. 用户可通过 AI 助手发出添加学生指令，AI 生成受控结构化动作。
2. 写操作确认前数据库不发生变化；确认后只执行一次。
3. 页面可自动进入学生管理页、打开对应弹窗、依次填写字段并停在提交前等待确认。
4. 动画支持暂停、继续、跳过、取消；跳过动画不能跳过写操作确认。
5. 页面刷新不导致重复执行；后端失败不显示成功效果；日志遵守现有脱敏规范。
6. 现有学生 CRUD、AI Chat、MCP、日志测试不回归。
