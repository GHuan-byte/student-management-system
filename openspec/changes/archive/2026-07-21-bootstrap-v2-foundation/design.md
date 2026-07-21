## Context

Student Management System V2 当前只有规划文档，尚未建立可运行的应用骨架。本 Change 的职责是提供 Flask Foundation，为后续阶段提供统一入口、配置边界、响应结构、错误处理和健康检查能力。

当前由于本地代理模式、Python 虚拟环境识别和测试执行存在环境问题，本阶段不建立完整 pytest 自动化测试体系，也不要求 Codex 创建、激活或识别虚拟环境，不要求 Codex 自动安装依赖。依赖安装只在 README 中提供用户手动执行命令。完整测试将在后续独立的 Testing / Final Verification Change 中补充。

## Goals / Non-Goals

**Goals**

- 建立最小可运行的 Flask Foundation
- 提供应用工厂、配置模块、统一 JSON 响应、异常与错误处理、Blueprint 注册、健康检查、日志配置和启动入口
- 保持模块划分清晰，便于后续补充测试和业务能力

**Non-Goals**

- 当前 Change 内编写 pytest 基础设施或自动化测试代码
- 创建 `tests/conftest.py`、`tests/test_*.py`
- 自动创建或识别虚拟环境
- 自动安装依赖
- 数据库、Repository、Service、认证、学生 CRUD、模板前端、MCP、AI Chat、导入导出、数据迁移

## Decisions

### D1: Configuration module

使用集中配置模块定义 `Config`、`DevelopmentConfig`、`TestingConfig` 和 `ProductionConfig`，通过应用工厂统一解析，避免配置分散硬编码。

设计要求：

- `config_name` 优先级高于 `APP_ENV`
- 未指定时默认回退到 `development`
- 未知配置名抛出明确异常
- Foundation 阶段不要求数据库相关配置

### D2: Environment variable loading

应用工厂负责在配置解析前决定是否加载 `.env`，以确保环境变量边界清晰。

设计要求：

- `load_env=True` 时允许读取 `.env`
- 不覆盖已有系统环境变量
- `config_overrides` 在配置装配完成后应用，并拥有最高优先级

### D3: Unified JSON response

统一响应格式如下：

```json
{
  "success": true,
  "data": null,
  "message": "",
  "error": null,
  "meta": {}
}
```

Foundation 阶段提供统一响应辅助函数，用于成功、错误和分页场景，确保后续 Route 与 API 能复用同一结构。

### D4: Application exceptions and global error handling

Foundation 阶段提供基础异常类型和全局错误处理注册函数，覆盖：

- 应用异常
- `HTTPException`
- 未预期异常

设计要求：

- 所有错误响应都返回统一 JSON 结构
- 不伪造成功结果
- 不暴露内部异常细节到客户端
- 保留日志记录入口用于排查

### D5: Blueprint registration and health check

通过集中注册函数管理 Blueprint，当前只引入健康检查端点，为后续模块扩展保留统一挂载位置。

设计要求：

- `GET /api/health` 返回 200
- 响应必须使用统一 JSON 结构
- Blueprint 导入路径保持简单，避免循环依赖

### D6: Logging configuration

提供独立日志配置函数，由应用工厂统一调用。

设计要求：

- 日志级别通过配置读取
- 日志配置保持幂等
- 当前仅关注基础控制台日志
- 不输出敏感信息

### D7: Application entry point

提供 `run.py` 作为启动入口，用于本地手动运行 Foundation。

设计要求：

- 支持基础 host / port 参数
- 参数优先级为 CLI > 环境变量 > 默认值
- 保持入口逻辑独立，方便后续补充自动化验证

## Deferred Testing

以下测试内容延期到后续独立的 Testing / Final Verification Change：

- Application Factory 测试
- Configuration 测试
- Response Helper 测试
- Error Handler 测试
- Logging 测试
- Entry Point 测试
- HTTP API 集成测试

延期说明：

- 当前 Change 仍需保持模块化、低耦合和清晰边界，以便后续补充测试
- 当前不创建 `tests/conftest.py`
- 当前不创建 `tests/test_*.py`
- 当前不引入测试数据库、`tmp_path`、`mock app.run` 等测试实现细节

## Manual Dependency Handling

当前 Change 不要求 Codex 创建、激活或识别虚拟环境，也不要求 Codex 自动安装依赖。

本阶段只要求：

- 在 README 中写明 Python 版本要求
- 在 README 中提供用户手动安装依赖的命令
- 在 README 中提供手动启动和健康检查步骤

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| 当前不建立自动化测试，可能延后发现回归问题 | 在规范中显式延期测试，并要求保持模块化结构，便于后续独立补测 |
| 开发环境差异影响本阶段验证 | 当前只要求手动运行和最小健康检查，不绑定虚拟环境实现细节 |
| Foundation 范围被扩张到业务实现 | 通过 proposal、spec 和 tasks 明确排除数据库、Service、CRUD、MCP 等后续范围 |
