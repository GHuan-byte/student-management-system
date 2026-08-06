# Design — add-ai-guided-student-actions

## Context

现有 V2 系统已具备：学生 CRUD（REST + 页面）、搜索/分页/排序/全选/批量删除、
Dashboard、AI Chat（DeepSeek + MCP 工具循环）、MCP 学生工具、AI 写操作的"确认后
执行"（itsdangerous 签名 Token、TTL、防篡改、单次消费）、统一日志与脱敏、
`request_id`、Viewer/Staff/Admin 权限。

当前 AI 写操作的确认流程完全发生在聊天面板内：`AIChatService._build_pending_action()`
返回 `{summary, safe_arguments, confirmation_token}`，用户在面板点击"确认"后，
`POST /api/chat/actions/confirm` 消费 Token 并经 `MCPToolAdapter → MCP write tool →
StudentService → SQLite` 执行。整个过程中学生管理页面没有任何可视化反馈，用户难以
判断操作会作用到哪些字段、哪条记录。

本 Change 在保留上述后端链路不变的前提下，为 AI 驱动的学生操作增加前端可视化动画，
并建立"动画可视化 / 后端真实操作"的清晰边界。

## Goals / Non-Goals

**Goals**

- 为 AI 学生操作建立统一的结构化动作模型与状态机（含幂等、单次执行语义）。
- 提供原生 JavaScript 的 `AIActionRunner` 动画框架（模拟鼠标、逐字填写、高亮、
  遮罩、步骤提示、暂停/继续/跳过/取消）。
- 为学生页关键元素增加稳定 `data-ai-target`，动画不依赖脆弱选择器。
- 写操作动画在提交前暂停等待用户确认；搜索不实现引导动画，仍为聊天只读能力。
- 支持跨页面（Dashboard → `/students`）动作恢复与刷新恢复，且不重复执行。
- 复用现有确认 Token、`AIChatService.confirm_action`、MCP 写工具与 `StudentService`
  作为唯一真实写入路径。
- 交付"AI 添加学生"端到端动画（本 Change 唯一动画目标）；搜索/修改/删除不做引导动画。

**Non-Goals**

- 不让 AI 执行任意 JavaScript / 任意 CSS 选择器 / 任意 SQL / 任意 URL 跳转。
- 不引入浏览器自动化框架（Playwright、Selenium 等）与 React/Vue 等前端框架。
- 不新增数据库表持久化动作（本阶段，见 D12）。
- 不实现 AI 搜索/修改/删除学生动画（搜索仍为聊天只读能力；修改、删除仍走既有聊天
  确认流程）。
- 不修改学生业务规则、现有手工 CRUD 交互契约、MCP 工具 schema。
- 不绕过用户确认；动画不替代后端权限与参数验证。

## 总体流程

```text
用户自然语言输入
      ↓
AI 意图解析（DeepSeek Tool Loop）
      ↓
结构化动作（action_type / payload / target）
      ↓
服务端白名单 + 参数 + 权限校验
      ↓
创建 pending action（服务端动作存储 + 签名 Token，写操作）
      ↓
聊天响应返回受控 action JSON（`data.action`，payload 仅语义字段名；现有
`pending_action`/`confirmation_token` 契约保持不变）
      ↓
前端 JSON 控制器校验 action_type 白名单 → 保存最小 action_id 引用并跳转 /students
      ↓
页面加载后按 action_id 重新读取动作（GET 仅返回安全展示数据，不含 Token）
      ↓
AIActionRunner 播放动画（打开弹窗 → 逐字段填写 → 停在提交前 → waiting_confirmation）
      ↓
用户确认（统一 Action Executor = POST /api/chat/actions/<action_id>/confirm，新端点；
服务端持 Token，浏览器不接触 Token）
      ↓
单次执行：校验用户/状态 → consume 存储的 Token → MCP write tool → StudentService → SQLite
      ↓
返回结果（action_id/status/action_result）→ 刷新学生列表 → 高亮新记录
      ↓
AI 助手显示最终结果（成功/失败）
```

只读动作（查询/统计）无确认步骤。AI 搜索不实现引导动画：搜索仍由既有聊天只读流程
调用 MCP `search_students` 工具并直接返回结果，不进入前端动画。

## 动作类型

| action_type        | 读/写 | requires_confirmation | 动画目标 |
| ------------------ | ----- | --------------------- | -------- |
| `create_student`   | 写    | true                  | 打开新增弹窗，填写字段，提交前确认 |
| `update_student`   | 写    | true                  | 不做引导动画；仍走既有聊天确认流程 |
| `delete_student`   | 写    | true                  | 不做引导动画；仍走既有聊天确认流程 |
| `search_students`  | 读    | false                 | 不做引导动画；仍为聊天只读能力 |
| `get_student`      | 读    | false                 | 定位并高亮目标行（或仅聊天返回） |
| `count_students`   | 读    | false                 | 无动画，聊天返回计数 |

规则：

- 搜索与查询是只读操作，不要求确认。
- 添加、修改、删除是写操作，必须保留确认步骤（服务端 Token + 用户确认）。
- 删除必须精确定位目标学生：`target` 必须解析为唯一的 `student_id` 或
  `student_number`；仅凭姓名且存在多个同名者时，动作必须被拒绝或先进入消歧。
- 只读动作的 `target` 用于高亮定位；写动作的 `target` 用于精确定位与二次校验。

## 动作数据结构

统一结构化动作模型（服务端权威状态，前端镜像）：

```json
{
  "action_id": "uuid-hex",
  "action_type": "create_student",
  "payload": {"student_number": "20260001", "name": "张三", "major": "计算机科学",
              "year_level": "大一", "score": 88},
  "target": {"student_id": 123},
  "target_page": "/students",
  "changes": {"add": ["student_number", "name", "major", "year_level", "score"]},
  "requires_confirmation": true,
  "status": "pending",
  "created_at": "…",
  "expires_at": "…",
  "result": null,
  "error": null
}
```

- `action_id`：服务端生成的唯一 ID，作为幂等键与跨页面恢复键。
- `action_type`：白名单动作类型。
- `payload`：写操作字段或读操作查询参数（**仅语义字段名**，如 `student_number`、
  `name`），服务端按 `StudentService` 规则校验；不含任何选择器或可执行内容。
- `target`：`{student_id}` 或 `{student_number}`，用于精确定位与动画定位。
- `target_page`：动画播放的目标页面（如 `/students`），供前端导航与恢复。
- `changes`：人类可读的字段/行变更说明，用于步骤提示与确认摘要。
- `requires_confirmation`：写 true / 读 false。
- `status`：见状态机。
- `created_at` / `expires_at`：动作生命周期；过期后不可确认/执行。
- `result` / `error`：执行后的结果或错误（脱敏后返回浏览器）。

浏览器可见的 `action` 对象含 `action_id`、`action_type`、`payload`（语义字段名）、
`target`、`target_page`、`status`、`created_at`、`expires_at`，**不含 Token、完整
学生记录、选择器与敏感字段**。

### Action JSON 契约（字段来源与处理规则）

| 字段 | 来源 | 前端可读 | 客户端可否修改 |
| ---- | ---- | -------- | -------------- |
| `action_id` | 服务端生成（uuid hex，不可预测） | 是 | 否（只读标识） |
| `action_type` | AI 语义意图，服务端白名单校验 | 是 | 否（不得自行改判） |
| `payload` | AI 提供学生字段，服务端按 `StudentService` 校验 | 是（用于动画回填） | 否（执行以 Token 绑定参数为准） |
| `target` | AI 解析 + 服务端唯一性校验 | 是 | 否 |
| `target_page` | **服务端按 action_type 固定映射**（全部 `/students`），非 AI 输出 | 是 | 否 |
| `status` | 服务端权威 | 是（展示） | 否（客户端不得置 succeeded 等） |
| `requires_confirmation` / `created_at` / `expires_at` | 服务端生成 | 是 | 否 |
| `changes` / `result` / `error` | 服务端生成 | 是 | 否 |

规则：

- **双重白名单**：`action_type` 必须同时通过服务端白名单与前端本地白名单校验；任一
  失败即拒绝且不播放。
- **未知字段**：服务端按白名单构造 action 对象，未知字段不出现；前端解析时忽略未知
  字段，遇到未知 `action_type` 直接拒绝。
- **缺少必填字段**（如 `action_id`/`action_type`）：服务端拒绝创建；前端收到缺字段的
  action JSON 也拒绝播放。
- **payload 多余字段**：服务端复用 `StudentService` 的未知字段拒绝规则（现有
  `_normalize_payload` 会拒绝未知字段）；动画只填写前端固定映射中的字段，多余字段不
  用于 DOM。
- **Token 不在 action 对象内**：`data.action` 永不携带 `confirmation_token`；写操作
  的 Token 由服务端持有（引导流程），或作为既有 `data.confirmation_token` 单独返回
  （兼容既有契约与测试）。

## 状态机

合法状态与转换：

```text
                ┌────────────────────────────────────────────┐
                │                 pending                    │
                │  (服务端创建动作，等待前端接管)              │
                └────────────────────────────────────────────┘
                   │            │
         (前端开始播放)       (TTL 到期)
                   │            │
                   ▼            ▼
              animating      expired（终止）
                   │
        ┌──────────┴──────────┐
        │ (写操作)            │ (读操作)
        ▼                    ▼
 waiting_confirmation     succeeded / failed
        │  (停在提交前)      (只读执行完成)
        │
   ┌────┴────┐
   │确认/执行 │ 取消
   ▼         ▼
executing  cancelled（终止）
   │
   ├── 成功 → succeeded（终止）
   └── 失败 → failed（终止）
```

转换规则：

- `pending → animating`：前端接管并开始播放。
- `animating → waiting_confirmation`：写操作在提交步骤前暂停。
- `waiting_confirmation → executing`：用户确认后，服务端原子消费 Token 并执行。
- `executing → succeeded | failed`：后端结果决定；二者均为终止态。
- `animating | waiting_confirmation → cancelled`：用户取消或服务端取消接口。
- `pending | waiting_confirmation → expired`：TTL 到期；`expired` 为终止态。
- 读操作：`pending → animating → succeeded | failed`，无 `waiting_confirmation`。
- 非法转换（如对 `cancelled`/`expired`/`succeeded` 动作再确认、再执行）一律拒绝。

状态权威在服务端动作存储；前端保存本地镜像用于 UI 恢复，但执行与确认判定以服务端为准。

**前端状态与服务端状态的关系**：

- 服务端权威状态（存入动作存储，决定可否执行/确认）：`pending`、`waiting_confirmation`、
  `executing`、`succeeded`、`failed`、`cancelled`、`expired`。
- `animating` 是**前端展示态**：用于动画播放中的 UI 反馈，服务端仅作参考记录，
  **不作为执行门禁**；客户端 SHALL NOT 将动作置为 `executing`/`succeeded`/`failed`/
  `cancelled`/`expired`。
- `succeeded` 只能在服务端真实执行成功后由服务端设置；客户端不得自行改为成功。
- 前端可把状态镜像用于展示与恢复，但任何写判定（能否确认、能否执行、是否已执行）
  一律以服务端返回为准。

## 单次执行机制

防止以下重复执行：

1. **页面刷新后重复添加**：确认路径是现有 `POST /api/chat/actions/confirm`，Token 在
   服务端被原子消费并记录 `action_id`（`AIActionConfirmation` 的 `threading.Lock` +
   consumed set）。刷新后即使前端再次确认，也会得到 `ai_confirmation_replayed`，
   不会二次执行；前端据此判定"已执行"，仅刷新列表。
2. **连续点击确认**：`confirm_action` 在锁内"先消费再执行"，同一 Token 并发确认
   至多一个成功（现有 2.5.8 并发测试已覆盖）。
3. **MCP 与前端双重执行**：设计上唯一真实写入路径是服务端确认路径
   （Token → MCP → `StudentService`）。前端动画只做可视化，**绝不**在动画里通过
   学生 REST API 再次提交写请求；引导期间 `students.js` 的 `handleModalSubmit` 被
   "引导模式"守卫置为无效，杜绝模拟点击提交按钮触发真实表单提交。前端与 MCP 各自
   "执行一次"的担心通过该单一入口消除：前端不调用 `POST/PUT/DELETE /api/students`，
   只调用统一 Action Executor。
4. **网络超时自动重试**：前端确认请求失败后不自动重发写请求，而是进入可恢复的
   `failed` 状态并向用户展示；是否重试由用户显式发起新动作。
5. **动画重播再执行**：动画重播只改变视觉状态，不调用任何写接口；`action_id` 已
   `succeeded`/`cancelled`/`expired` 时服务端拒绝任何执行/确认。

组合校验：

- **服务端**：`consume_token`（签名 + TTL + 单次消费 + `action_id` 幂等）→ 动作存储
  状态检查（`waiting_confirmation` 且未 `cancelled`/`expired` 才允许执行）。
- **前端**：本地 `action_id` + 状态镜像 + 服务端动作恢复接口，用于展示与恢复，不
  作为执行依据。
- **统一 Action Executor**：前端确认后只调用统一服务端执行入口——引导流程使用新增
  `POST /api/chat/actions/<action_id>/confirm`（服务端持 Token，浏览器不接触 Token），
  现有 `POST /api/chat/actions/confirm`（Token 式）保留以兼容既有契约与测试；两者共用
  同一单次消费 Token 与 MCP→`StudentService` 核心，动画、确认与真实执行共享同一
  `action_id`，因此真实写操作至多成功一次。

## action_id 与 confirmation token 的关系

- `action_id` 识别业务动作（幂等键、恢复键）；`confirmation_token` 证明用户确认的是
  哪一个动作（签名 + 短 TTL + 单次消费）。
- Token 载荷（既有 `AIActionConfirmation`）绑定：`action_id`、`tool_name`（对应
  `action_type`）与 `arguments`（服务端校验后的参数）。
- 动作存储以 `action_id` 为键保存 `{token, action_type, tool_name, arguments,
  status, user_id, created_at, expires_at}`。
- **一致性校验**：确认时服务端校验 ① Token 签名/过期/消费；② Token 内 `action_id`
  与确认的 `action_id` 一致；③ Token 内 `tool_name` 与动作 `action_type` 的映射一致；
  ④ 动作归属与当前用户一致；⑤ 动作状态为 `waiting_confirmation` 且未
  `cancelled`/`expired`/`succeeded`。任一不满足 → 结构化错误，**不执行任何写**。
- **消费后不可再执行**：Token 被 `consume_token` 标记消费后，无论从 Token 端点还是
  action_id 端点都不可再次执行。
- **`executing`/`succeeded`/`failed`/`cancelled`/`expired` 的重复确认**：服务端返回
  对应结构化错误（如 `ai_confirmation_replayed` / `action_not_executable`），不执行。
- **`failed` 是否允许重试**：第一阶段 `failed` 为终止态；重试 = 创建**新动作**
  （新 `action_id`、新 Token），由用户重新发起。原因：Token 消费后不可复用，失败动作
  不应被无界重放。
- **网络超时不得盲目重试**：客户端确认超时后先调用 GET 查询动作状态；已
  `succeeded` → 仅刷新列表；仍 `waiting_confirmation` → 询问用户是否重试；
  `expired`/`cancelled` → 提示重新发起。绝不自动重发写请求。

## 前端动画控制器（AIActionRunner）

基于原生 JavaScript 的动画控制器，建议模块名 `app/static/js/ai_action_runner.js`。
控制器是 **JSON 驱动的**：它读取 AI Chat 或待执行动作接口返回的受控 JSON，先在本
地白名单中校验 `action_type`，再按 `action_type` 选择固定的步骤序列播放。后端只返回
语义动作与学生字段名，**所有 DOM 定位由前端固定映射完成**（语义字段名 →
`data-ai-target`），后端 JSON 中不存在任何 JavaScript、DOM/CSS 选择器、SQL、URL 或
可执行字符串。

- **步骤队列**：每个 `action_type` 对应一个固定步骤序列（如 create：
  `navigate → openModal → fillFields → waitAtSubmit → confirm → refresh → highlight`）。
- **async/await 顺序控制**：每个步骤是 `async` 函数，前一步完成后进入下一步。
- **元素等待**：`waitFor(data-ai-target, timeout)` 轮询 DOM，而非长 `setTimeout`。
- **模拟鼠标**：一个跟随页面滚动的圆形光标元素；`moveTo(element)` 平滑移动。
  `clickAt(element)` 对**非提交类元素**（如"新增学生"按钮）触发既有 click 事件以打开
  弹窗；对 **`student-submit-button`（`<button type="submit">`）只做视觉"按下"效果，
  绝不调用 `.click()`、绝不派发 `submit`**——真实写由 Action Executor 发起。
- **逐字填写**：`typeInto(input, text)` 逐字符 set value + 输入事件 + 当前字段高亮。
- **下拉框选择**：`selectOption(select, value)` 设置值并触发 `change`。
- **当前字段高亮**：`.ai-guide-highlight` 类 + 遮罩；焦点环/呼吸效果。
- **页面遮罩**：半透明遮罩（`.ai-guide-mask`）压暗非目标区域，突出当前步骤。
- **步骤提示**：`.ai-guide-tooltip` 显示中文提示（如"正在打开新增学生弹窗…"、
  "正在填写学号…"、"已填写完成，请确认是否添加"）。
- **暂停/继续/跳过/取消**：控制器暴露 `pause()/resume()/skip()/cancel()`；跳过仅跳过
  视觉步骤，写操作仍停在提交前等待确认；取消调用服务端取消接口并将动作置为
  `cancelled`。
- **人工干预检测**：关键步骤前校验期望 DOM 状态；若用户关闭弹窗/改字段/翻页，
  暂停并提示"检测到页面状态变化"，不继续陈旧动画。

约束：**AI 不生成 JS、不生成选择器**；步骤序列与目标定位全部由前端固定代码与
`data-ai-target` 完成，AI 只提供 `action_type` 与经服务端校验的 `payload`/`target`。

**统一 Action Executor**：用户确认后，前端只调用统一服务端执行入口——引导流程使用
新增 `POST /api/chat/actions/<action_id>/confirm`（服务端持 Token），不再通过学生
REST API 单独提交写请求；动画、确认与真实执行共享同一 `action_id`，真实写操作因此
至多成功一次。

**视觉点击、DOM click、表单 submit 与后端执行请求的隔离**：

1. **视觉点击动画**：模拟鼠标移动、高亮、按钮"按下"光影，全部是 CSS/视觉表现。
2. **DOM click 事件**：允许对"新增学生"等**非提交**按钮触发既有 click 事件（用于打开
   弹窗，无写副作用）；**禁止**对 `student-submit-button`（`<button type="submit">`）
   派发真实 `click()`。
3. **表单 submit 事件**：引导流程**绝不**触发表单 `submit`；`students.js` 在引导模式
   下使 `handleModalSubmit` 失效（直接返回，不发请求），从根上杜绝"先表单提交、再调
   确认接口"的双写。
4. **后端真实执行请求**：唯一由统一 Action Executor（`POST /api/chat/actions/
   <action_id>/confirm` 或既有 Token 端点）发起；动画本身绝不调用
   `POST/PUT/DELETE /api/students`。

用户确认前：允许移动模拟鼠标并高亮提交按钮。用户确认后：允许播放视觉"点击"效果，
但真实写仍只由 Action Executor 发起。

**create_student 播放序列（最小切片，端到端）**：

1. 用户发送添加学生指令。
2. 后端解析并验证字段（`StudentService` 规则 + 白名单）。
3. 生成受控 action JSON（`data.action`）；写操作创建 pending action，Token 存入服务端
   动作存储。
4. 用户确认前数据库不发生变化。
5. 前端 JSON 控制器读取 JSON 并校验 `action_type` 本地白名单。
6. 当前不在 `/students` 时保存最小 `action_id` 引用并跳转。
7. 页面加载后按 `action_id` 重新读取动作（GET 仅返回安全展示数据）。
8. 通过 `student-add-button` 既有 click 事件打开已有新增学生弹窗。
9. 按 `payload` 依次填写学生字段。
10. 填写时触发标准 `input`/`change` 事件。
11. 定位并高亮"确定添加"按钮（`student-submit-button`），停在提交前
    （`waiting_confirmation`）。
12. 用户确认后调用唯一 Action Executor（`POST /api/chat/actions/<action_id>/confirm`）。
13. 服务端验证：Token 签名/过期/消费、action_id 与 Token 一致、用户归属、动作状态
    （`waiting_confirmation` 且未取消/过期/成功）、权限、参数（以 Token 绑定参数为准）。
14. 通过现有 MCP→`StudentService` 链路执行一次真实添加。
15. 执行成功后刷新学生列表。
16. 高亮新增学生记录。
17. AI Chat 显示成功结果。
18. 执行失败时关闭（或保留并标记错误）弹窗并显示失败，不播放成功动画。
19. 重复确认/刷新不会重复创建学生（Token 单次消费 + 动作状态机）。

## 页面元素稳定标识（data-ai-target）

学生页关键元素统一加 `data-ai-target`（新增到 `students.html` 与
`_student_form_fields.html`），例如：

- `student-add-button`、`student-search-input`、`student-search-button`
- `student-form-modal`、`student-cancel-button`、`student-submit-button`
- `student-number-input`、`student-name-input`、`student-gender-input`、
  `student-age-input`、`student-major-input`、`student-year-level-select`、
  `student-score-input`、`student-phone-input`、`student-email-input`

为什么不用 `nth-child` 等脆弱选择器：

- `nth-child` 依赖 DOM 顺序与表格列结构，模板加一列/改排序即失效。
- 与现有 `students.js` 已使用的 `data-*` 属性（`data-open-create-modal`、
  `data-submit-button`、`data-action` 等）风格一致，可读、稳定、自文档化。
- 便于自动化测试：可直接断言每个 `data-ai-target` 存在，模板改动后尽早发现丢失。

`data-ai-target` 的**丢失检测**：新增测试（渲染 `/students` 后断言所有预期
`data-ai-target` 存在）；可选在页面初始化时由 `AIActionRunner` 校验一次。

**固定映射**：前端维护一个本地固定映射（如 `student_number →
"[data-ai-target=student-number-input]"`），后端只下发语义字段名 `student_number` 等，
前端据此解析出目标元素。该映射只存在于前端固定代码，AI 无法通过 JSON 注入选择器。

**唯一性**：每个 `data-ai-target` 值在页面内唯一（一个标识只对应一个元素）；模板测试
断言唯一性，避免重复标识导致动画定位歧义。

**缺失即中止且不写**：若动画所需任一 `data-ai-target` 缺失，动画中止并提示"目标元素
不存在"；此时**绝不**继续任何真实写操作（不进入确认、不调用 Action Executor）。

## 跨页面动作恢复

场景：AI 助手位于 Dashboard，操作发生在 `/students`。

- **sessionStorage 只保存最小非敏感动作引用**：`{action_id, action_type, target,
  status}`，键如 `ai-guided-action`。Token、完整 payload、完整学生记录一律不落盘。
- **安全恢复（不重新发放 Token）**：恢复时前端以 `action_id` 调用新增的
  `GET /api/chat/actions/<action_id>`，服务端校验"同一登录用户、动作未过期未执行未
  取消"后**只返回安全展示数据**（与 `data.action` 同构的浏览器安全 action 对象），
  **不返回 `confirmation_token`**。
- **引导确认使用 action_id**：写操作确认走新增
  `POST /api/chat/actions/<action_id>/confirm`（CSRF + Session + 同用户 + 状态 +
  工具角色校验），服务端持有 Token 并消费，**Token 在引导流程中无需进入浏览器跨页
  传递**。因此没有、也不需要任何 GET 端点重新发放 Token；现有 `data.confirmation_token`
  仅为兼容既有契约而保留。
- **刷新恢复**：页面刷新后从 sessionStorage 读取引用 → GET 恢复安全动作数据 →
  `AIActionRunner` 从对应步骤恢复。若动作已 `succeeded`/`failed`/`cancelled`/
  `expired`，前端不重播、不重执行，仅展示结果或清理引用。
- **已执行动作为什么不能重新执行**：`action_id` 已被服务端消费/记录，`consume_token`
  与动作存储双重拒绝；确认端点对非 `waiting_confirmation` 状态返回结构化错误。
- **为什么不把完整敏感数据放进前端存储**：Token 是"签名而非加密"，可被解码；完整
  payload/学生记录属于隐私数据；sessionStorage 与 localStorage 都可能被 XSS 读取。
  因此只存最小引用，其余走服务端恢复。

## 动画和真实操作的边界

- **动画负责可视化**：模拟鼠标、填写、高亮、遮罩、提示，全部是视觉表现。
- **后端负责真实操作**：数据写入唯一路径为服务端确认路径
  （`/api/chat/actions/confirm` → `AIChatService.confirm_action` → MCP write tool →
  `StudentService` → SQLite）。
- **`StudentService` 是学生数据操作统一入口**：AI、MCP、页面三者都不得各自维护独立
  写入逻辑；前端动画不调用写 REST API。
- **前端动画成功 ≠ 后端操作成功**：只有确认接口返回 `success` 后，前端才刷新列表并
  播放成功高亮/淡出；失败则显示失败，不播放成功效果。
- **表单作为预览**：写操作动画在真实弹窗里逐字填写字段以"可视化将要执行的操作"，
  但真实写入使用 Token 绑定的、服务端校验过的原始参数（anti-tamper，浏览器改表单
  不影响执行）。为避免歧义，AI 引导期间表单处于"预览锁定"（输入框只读 + 顶部提示
  "AI 将执行以下操作"）。
- **表单永不自动提交**：引导期间 `students.js` 的 `handleModalSubmit` 被"引导模式"
  守卫置为无效；动画不得对提交按钮派发 click/submit，杜绝"动画点击→表单提交→再调
  确认接口"的双写。

## 错误处理

| 场景 | 行为 |
| ---- | ---- |
| 学号重复 | 后端返回 `duplicate` 错误；不播放成功效果；AI 显示失败并给出原因 |
| 目标学生不存在 | `update_student`/`delete_student` 校验 target 不存在 → 拒绝动作；执行时再校验一次 |
| 搜索多个同名 | 结果正常展示并高亮；依赖唯一目标的写动作被拒绝，提示用户消歧 |
| 参数验证失败 | 服务端按 `StudentService` 规则拒绝，返回结构化错误 |
| 页面元素不存在 | `AIActionRunner` 报"目标元素不存在"，动作进入 `failed` 并清理 |
| 弹窗未成功打开 | `waitFor(student-form-modal)` 超时 → 报错并中止 |
| Token 过期 | `ai_confirmation_expired`；动作 `expired` |
| Token 被篡改 | `ai_confirmation_invalid` |
| action_id 已执行 | `ai_confirmation_replayed` / 动作存储拒绝；前端仅刷新列表 |
| 用户取消 | 调用服务端取消接口 → `cancelled`；不执行任何写 |
| 用户手动关闭弹窗 | 人工干预检测 → 暂停并提示，不继续 |
| 网络错误 | 显示安全失败信息；不自动重发写请求 |
| 后端执行失败 | `ai_confirmation_execution_failed`；动作 `failed`；不显示成功效果 |
| 页面刷新 | 通过 sessionStorage 引用 + 服务端恢复；不重复执行 |
| 动画中手工操作页面 | 关键步骤前 DOM 状态校验 → 暂停/中止并提示 |

## 安全设计

保留并强化现有安全属性：

- 操作白名单：仅 6 种 `action_type`。
- 参数验证：复用 `StudentService` 校验。
- 权限验证：复用 `ENDPOINT_ROLES` / AI 工具角色映射（Staff 可增改，Admin 可删）。
- 确认 Token：现有 `AIActionConfirmation`（签名、TTL、单次消费、防篡改）。
- 防重复执行：`consume_token` + 动作存储状态机。
- 日志脱敏：`logging_config.sanitize_log_value`（Token、cookie、session、学生整条
  记录 → 占位符），带 `request_id`。
- MCP stdout/stderr 边界：MCP 协议只走 stdout，诊断走 stderr/日志。
- 禁止：`eval`、`new Function`、AI 输出脚本执行、AI 输出任意 DOM 选择器执行、
  任意 SQL、任意 URL 跳转、未确认写操作。
- Token 不进入 sessionStorage/localStorage；学生敏感信息不进入日志与浏览器存储。

## 关键设计决定（含备选方案对比）

### D1. 复用哪些现有代码？

**直接复用**：

- `AIActionConfirmation`（Token 签名/验证/单次消费/并发保护）——不改。
- `AIChatService.chat/confirm_action` 与 Tool Loop ——扩展而非重写。
- `MCPToolAdapter`、MCP 写工具（`add_student` 等）与 `StudentService` ——不改。
- `POST /api/chat/actions/confirm` 端点与 `_public_confirm_data` ——不改。
- `students.js` 的 `state`（单一事实来源）、`loadStudents()`、弹窗开合、`data-*`
  属性、`student-modal-opened` 自定义事件模式 ——复用并扩展。
- `logging_config` 脱敏、`request_id`、`log_security_event` ——不改。
- `ai_chat.js` 的 sessionStorage 会话历史、确认卡片 ——扩展以接入动画。

### D2. 哪些现有代码不适合直接复用、需要扩展？

- `_build_pending_action` 返回的 `pending_action` 只含 `summary/safe_arguments`，
  需要扩展出浏览器安全 `action` 元数据并写入服务端动作存储。
- `AIChatService` 需要新增"创建/查询/取消动作"的存储协作；动作存储建议独立模块
  `app/services/ai_action_store.py`。
- `students.js` 需要新增"监听 AI 动作事件（如 `ai-action-succeeded`）→ 刷新 + 高亮"
  的集成点，但不得复制列表状态。
- `ai_chat.js` 需要发起跨页面引导动画并处理恢复。
- `base.html`/`students.html`/`_student_form_fields.html` 需要加 `data-ai-target` 与
  动画资源（独立 CSS/JS，前缀 `ai-guide-`）。

### D3. 最终真实操作由谁执行？

**由后端服务端确认路径执行**：`/api/chat/actions/confirm` → `confirm_action` →
MCP write tool → `StudentService` → SQLite。前端动画只负责可视化；前端**不**通过
学生 REST API 提交写请求。

- 优点：复用现有单次 Token 语义与权限校验；前后端单一写入路径；防篡改。
- 备选：由前端在确认后提交真实表单到 `POST/PUT/DELETE /api/students`。
  - 优点：与手工 CRUD 同路径、直观。
  - 缺点：需要新建一套"防止刷新/重放重复提交"的幂等机制（无 Token 语义）；需要把
    Token/action_id 与 REST 请求绑定，改动更大；与"浏览器不得重新提交参数"的现有
    安全规则冲突。**不推荐**，作为已评估备选记录。

### D4. 如何防止 MCP 和前端双重执行？

唯一真实写入路径是服务端确认路径；前端动画不调用写 REST API；确认请求失败不自动
重试；服务端 `consume_token` + 动作存储状态机双重防重。MCP 只在确认后被调用一次。

### D5. 如何保证 action_id 只能执行一次？

- 服务端 `consume_token` 在锁内"校验 → 标记消费 → 执行"（现有）。
- 新增动作存储：`action_id → {status, ...}`，执行前必须处于 `waiting_confirmation`
  且未被取消/过期/成功；执行成功后置 `succeeded`。
- 查询/恢复接口对已执行动作不返回 Token；确认接口对非 `waiting_confirmation` 状态
  返回结构化错误。

### D6. 动画在确认前完整播放，还是在提交按钮前暂停？

**写操作在提交按钮前暂停**（`waiting_confirmation`），等待用户确认后再播放"点击
提交"并调用确认接口。理由：动画模拟真实操作必须在破坏性步骤前停下，让用户有明确
否决点；与现有"确认后执行"语义一致。
只读查询无破坏性步骤；搜索不做引导动画。

### D7. 搜索操作是否需要确认？

**搜索不做引导动画**：AI 搜索仍作为聊天只读能力直接返回结果，无需确认。写动作依赖
唯一目标时，若目标不唯一会被拒绝直到用户消歧。

### D8. 用户跳过动画后，是否仍需要确认写操作？

**是**。跳过只跳过视觉步骤，写操作仍必须经过用户确认（服务端 Token + 明确点击确认）
才能执行；"跳过动画"绝不等于"跳过确认"。

### D9. 页面刷新后如何恢复未完成动作？

sessionStorage 仅存最小引用 `{action_id, action_type, target, status}`；刷新后前端
调用 `GET /api/chat/actions/<action_id>` 恢复**安全动作展示数据**（不含 Token），从
对应步骤继续播放或停在确认点；写操作确认走 action_id 端点（服务端持 Token）。

### D10. 页面刷新后如何识别已执行动作？

服务端动作存储保留 `succeeded/failed/cancelled/expired` 状态；查询接口对已执行动作
返回"已执行/不可恢复"标记且不返回 Token。前端据此不重播、不重执行，仅刷新列表或
显示结果。

### D11. 是否需要新增数据库表保存动作，还是沿用当前 Token/会话机制？

**本阶段不新增数据库表**，沿用进程内 Token + 新增**进程内动作存储**（
`AIActionStore`，按 `action_id` 索引 `{token, status, payload-ref, target, user_id,
created_at, expires_at}`）。

- 优点：改动小、无 schema 迁移、满足单进程开发（与现有 `AIActionConfirmation`
  的进程内 consumed set 一致）。
- 备选一：新增 SQLite 动作表。优点：跨重启/多 worker 可靠、可审计；缺点：schema
  变更、清理策略、并发与事务成本，超出本阶段。**留待后续阶段**。
- 备选二：完全无状态（只靠 Token）。缺点：无法服务端取消、无法按 `action_id` 恢复、
  刷新后无法区分"未执行/已执行"。**不推荐**。

### D12. 如果暂时不新增数据库表，其限制是什么？

- 动作存储在进程内存中：应用重启即丢失；多进程/多 worker 部署下各实例状态不共享。
- 限制缓解：本阶段面向单进程开发（`python run.py`）；重启后未完成动作自然过期，
  用户重新发起即可；后续多 worker 需迁移到 DB 动作表（记录在 D11）。
- 与现有 `AIActionConfirmation` 的进程内 consumed set 限制一致，风险可接受。

### D13. sessionStorage 中允许保存什么、不允许保存什么？

**允许**：最小非敏感动作引用 `{action_id, action_type, target, status}`、聊天历史
（现有 `ai-chat-history`，仅 user/assistant）。

**不允许**：`confirmation_token`、完整 `payload`、完整学生记录、API Key、内部签名
密钥、MCP 原始结果、`reasoning_content`。Token 通过服务端按 `action_id` 获取。

### D14. AI Chat 侧栏如何显示动画状态和执行结果？

- 动画进行中：面板显示"正在页面中执行：<动作摘要>（<status>）"与步骤提示同步更新。
- 停在确认点：面板显示与页面一致的确认卡片（现有确认卡片扩展显示 action 摘要）。
- 执行结果：复用现有 `confirm` 返回的确定性中文 `reply`（如"学生新增成功。"）与
  `action_result`；失败显示失败信息。
- 面板不重复执行；用户在页面提交处确认与在面板确认等价（同一 Token，单次消费）。

### D15. 页面 DOM 改动后如何尽早发现 data-ai-target 丢失？

- 新增渲染测试：渲染 `/students` 后断言全部预期 `data-ai-target` 存在。
- `AIActionRunner` 初始化时对动作所需目标做一次校验，缺失即报"目标元素不存在"。
- 可选启动自检（复用 `mcp_client/self_check.py` 思路）。

### D16. 如何测试"动画播放了，但数据没有提前写入"？

- 服务端测试：创建写动作后、确认前，断言数据库学生数不变（对比确认前后）。
- 前端行为测试：模拟动作开始、填写、暂停，断言未发出任何写请求（拦截 fetch，
  断言仅出现 GET/页面导航，不出现 POST/PUT/DELETE `/api/students` 与 confirm）。
- 集成测试：动画执行完成但确认接口被拒绝时，数据库无变化。

### D17. 如何测试重复确认不会重复创建学生？

复用现有并发确认测试思路：同一 Token/`action_id` 并发或顺序确认多次，断言至多
一次写入（学生数只 +1），其余得到 `ai_confirmation_replayed`/状态拒绝；新增前端
连续点击确认按钮的防抖/幂等测试。

### D18. 如何测试后端失败时不会显示成功动画？

- 服务端返回失败（如 duplicate / not found / execution failed）后，断言前端未触发
  成功高亮类、未刷新为成功态、AI 显示失败信息。
- 前端测试：mock confirm 返回失败，断言列表未刷新成功、无高亮。

### D19. GET 动作查询接口是否保留，以及安全规则

**保留，但只返回安全展示数据、不返回 Token**。

安全规则：
- `action_id` 服务端生成（uuid hex），不可预测。
- 端点走统一登录与会话校验（在 `ENDPOINT_ROLES` 增加对应只读端点，任何已登录用户只
  可查自己的动作）。
- 动作绑定创建它的用户（动作存储 `user_id`）；非本人 → 404/403，不暴露存在性。
- 已取消/已过期/已执行动作不返回可执行状态与敏感数据，返回结构化状态。
- 响应只含浏览器安全 action 对象（`action_id`/`action_type`/`payload`/`target`/
  `target_page`/`status`/`requires_confirmation`/`created_at`/`expires_at`），**不含
  Token**；`payload` 仅为动画恢复所必需、仅本人可见。
- `Cache-Control: no-store`，禁止缓存；`action_id` 在 URL 路径而非查询参数，不进访问
  日志敏感字段。
- 引导确认走 `POST /api/chat/actions/<action_id>/confirm`（非 GET，触发现有 CSRF
  校验），Token 由服务端持有并消费，**不由任何 GET 端点重新发放**。

备选（评估）：完全删除 GET，改为 POST 获取。结论：GET 返回的仅是本人、no-store 的
安全展示数据（不含 Token），可接受；Token 决不出现在 GET 中。若后续要求更高，可
统一收敛到 action_id 确认端点（已设计）。

## 可复用组件与缺口总结

**可复用**：`AIActionConfirmation`、`AIChatService`（扩展）、`MCPToolAdapter`、
MCP 写工具、`StudentService`、`students.js` 状态/加载/弹窗、`ai_chat.js` 会话与确认
卡片、`logging_config`、统一 JSON 响应、CSRF/权限、`request_id`。

**缺口（本 Change 补齐）**：结构化动作模型与状态机、进程内动作存储、动作查询/取消
端点、`data-ai-target`、`AIActionRunner`、动画样式与遮罩/鼠标/提示、`students.js`
AI 事件集成（刷新/高亮）、`ai_chat.js` 跨页面引导与恢复、相关测试。

## 与现有 add-ai-chat Change 的关系

- `add-ai-chat` 已归档并建立了 AI Chat 基础：Tool Loop、Pending Action、确认 Token、
  聊天面板。本 Change **在其之上增量演进**，不重写。
- 本 Change 是对现有 AI 交互的**扩展**（结构化动作 + 前端动画），而非修复或重新
  打开旧 Change：`add-ai-chat` 已归档且其契约（Token 不落盘、单次消费、浏览器不得
  重提参数等）被本设计**继承并强化**。若直接修改归档 Change 会破坏历史记录与
  "已验收"状态，因此按项目规范新建独立 Change。

## 第一阶段实现边界（最小可用切片）

先交付并验收端到端最小切片：

```text
AI 添加学生 → 生成 pending action（Token 存服务端）→ 跳转学生页 → 打开新增弹窗
→ 自动填写字段 → 停在提交前等待确认 → 经 action_id 端点执行一次真实添加
→ 刷新列表 → 高亮新增记录 → AI 显示结果
```

搜索、修改、删除均不实现引导动画；本 Change 仅实现添加学生动画。

## Risks / Trade-offs

- [跨页面 Token 传递复杂] → 采用 action_id 端点确认 + 服务端持 Token，Token 不进入
  浏览器、不落盘；GET 仅返回安全展示数据，不重新发放 Token。
- [动画点击提交按钮触发第二次写入] → 引导模式守卫使 `handleModalSubmit` 失效；动画
  不对提交按钮派发 click/submit；写仅由 Action Executor 发起。
- [刷新导致重复执行] → `consume_token` + 动作存储状态机双重防重；前端失败不自动重试。
- [动画与真实操作不同步/误报成功] → 只有确认接口成功才刷新+高亮；边界测试覆盖。
- [DOM 状态漂移/人工干预] → 关键步骤前校验 + 干预检测暂停。
- [`data-ai-target` 模板回归] → 渲染测试断言全部标识存在。
- [进程内动作存储丢失] → 单进程可接受，重启后动作过期，重新发起；后续迁移 DB 表。
- [表单预览与实际写入参数不一致的 UX 风险] → 明确"预览锁定"提示，写入以 Token 绑定
  参数为准。
- [新增端点扩大攻击面] → 查询/取消端点复用登录与会话校验、按用户隔离、结构化错误、
  日志脱敏。

## 验收标准

1. 用户可通过 AI 助手发出添加学生指令。
2. AI 可生成受控的结构化动作（白名单 + 服务端校验）。
3. 用户确认前数据库不发生变化。
4. 页面可自动进入学生管理页。
5. 页面可自动打开新增弹窗。
6. 表单可按动作内容依次填写。
7. 当前填写字段具有明显视觉提示。
8. 模拟鼠标可移动并点击目标元素。
9. 填写完成后停在提交步骤前等待确认。
10. 用户确认后只执行一次添加。
11. 添加成功后列表出现新记录。
12. 新记录具有短暂高亮效果。
13. 后端失败时显示失败结果。
14. 用户可取消未执行动作。
15. 用户可跳过动画，但不能跳过写操作确认。
16. 页面刷新不会导致重复添加。
17. 学号重复时不播放成功效果。
18. AI 不可执行任意 JavaScript。
19. AI 不可执行任意 SQL。
20. 所有数据写入继续经过 `StudentService`。
21. 日志不含密码、Token、Cookie、Session 或完整学生记录。
22. 现有学生 CRUD、AI Chat、MCP、日志测试不回归。

## Migration Plan

1. 定义动作模型与状态机（`app/services/ai_action.py`）。
2. 实现进程内动作存储（`app/services/ai_action_store.py`）。
3. 扩展 `AIChatService._build_pending_action` 生成 action 元数据并把 Token 写入存储。
4. 新增 `GET /api/chat/actions/<id>`（安全展示数据，不含 Token）、
   `POST /api/chat/actions/<id>/confirm`（action_id 确认，服务端消费 Token）与
   `POST /api/chat/actions/<id>/cancel`。
5. 为学生页添加 `data-ai-target` 与动画资源（`ai_action_runner.js/css`）。
6. 实现 `AIActionRunner` 与添加学生动画（仅 create）。
7. `students.js` 监听 AI 动作事件并刷新/高亮；`ai_chat.js` 发起与恢复。
8. 更新 `.env.example`（动作 TTL 等）与文档。
9. 补齐服务端、API、Service、JS 行为、集成与人工验收测试。
10. 回滚：删除新增模块与模板属性改动，回退既有文件；无 schema 迁移。
