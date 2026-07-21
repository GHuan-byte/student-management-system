## Why

Student Management System V2 目前仍处于从零重写的早期阶段，当前 Change 的目标是建立一个最小、清晰、可运行的 Flask Foundation，作为后续数据库、Service、REST API、MCP 和 AI 能力的统一基础。

由于当前本地代理模式、Python 虚拟环境识别以及测试执行存在环境问题，本阶段不再要求建立完整 pytest 自动化测试体系，也不要求测试优先开发。完整测试将在后续独立的 Testing / Final Verification Change 中统一补充。

## What Changes

- 声明 `pyproject.toml` 项目元数据和基础依赖
- 搭建 `create_app()` Flask 应用工厂
- 建立集中配置模块与环境变量加载边界
- 提供统一 JSON 响应结构与响应辅助函数
- 定义应用异常与全局错误处理机制
- 提供 Blueprint 注册基础设施
- 添加 `GET /api/health` 健康检查端点
- 提供日志配置入口
- 添加 `run.py` 应用启动入口
- 更新 `README.md` 与 `.env.example`，说明手动安装和手动验证方式

本 Change 只负责创建可运行的 Flask Foundation。完整测试将在后续独立的 Testing / Final Verification Change 中实现。

## Goals

- 创建可运行的 Flask Foundation，而不是完整业务系统
- 提供 `create_app(config_name=None, config_overrides=None, load_env=True)` 应用工厂
- 建立 Development / Testing / Production 配置边界
- 在配置加载阶段支持 `.env` 环境变量读取
- 提供统一 JSON 响应结构：`success`、`data`、`message`、`error`、`meta`
- 定义基础应用异常和全局错误处理机制
- 提供 Blueprint 注册基础设施和健康检查端点
- 提供 `run.py` 启动入口和最小可运行文档
- 保持代码结构模块化，便于后续独立 Change 补充自动化测试

## Non-Goals

- 完整自动化测试体系
- pytest fixtures
- 单元测试、集成测试和端到端测试
- 虚拟环境创建和解释器识别
- 自动安装依赖
- 数据库、Schema 和初始化
- Repository
- Service
- 认证
- 学生 CRUD
- 模板和前端
- MCP
- AI Chat
- 导入导出
- 数据迁移

## Capabilities

### New Capabilities

- `project-foundation`
  - `pyproject.toml` 项目元数据与基础依赖声明
  - `create_app()` 应用工厂
  - 配置模块与环境变量加载边界
  - 统一 JSON 响应工具
  - 应用异常与全局错误处理
  - Blueprint 注册基础设施
  - `GET /api/health` 健康检查
  - 日志配置入口
  - `run.py` 启动入口
  - README 与 `.env.example` 文档基础

### Modified Capabilities

- 无。本 Change 为 Foundation 初始化 Change。

## Impact

- 新增或更新 Foundation 相关 OpenSpec 设计与任务定义
- 将测试自动化要求显式延期到后续独立 Testing / Final Verification Change
- 当前阶段的验证方式改为手动运行与格式检查，不执行 pytest

## Scope Exclusions

以下内容仍明确排除在本 Change 之外：

- 数据库
- Repository
- Service
- 认证
- 学生 CRUD
- 模板和前端
- MCP
- AI Chat
- 导入导出
- 数据迁移
