## Why

Student Management System V2 是从零重写的项目。当前项目仅有文档（AGENTS.md、README、规划文档），没有任何可运行的代码。需要一个坚实的 Flask 应用骨架作为所有后续功能的起点——包括应用工厂、配置管理、统一响应格式、错误处理和测试基础设施。

管理员初始化属于后续认证 Change，不在本阶段范围内。

## What Changes

- 声明 `pyproject.toml` 项目元数据和依赖
- 搭建 `create_app()` Flask 应用工厂，支持开发/测试/生产配置
- 配置集中管理（`app/config.py`），通过 `python-dotenv` 从 `.env` 加载
- 实现统一 JSON 响应工具（`success`, `data`, `message`, `error`, `meta`）
- 实现应用异常类和错误处理装饰器
- 配置日志基础配置
- 添加 Blueprint 注册基础设施
- 添加 `GET /api/health` 健康检查端点
- 添加 `run.py` 启动入口
- 添加 pytest 基础设施（conftest.py、共享 fixture、基础测试）
- 更新 `.gitignore` 按 Foundation 需求
- 更新 `.env.example`
- 更新 `README.md`，补充安装、测试、启动和健康检查说明

## Capabilities

### New Capabilities
- `project-foundation`: Flask 应用骨架，包括：
  - `pyproject.toml` 与依赖声明
  - `create_app()` 应用工厂
  - Development、Testing、Production 配置边界
  - 环境变量加载（`python-dotenv`）
  - Blueprint 注册基础设施
  - 统一 JSON 响应工具
  - 应用异常与错误处理
  - 日志基础配置
  - `GET /api/health` 健康检查
  - `run.py` 启动入口
  - pytest 基础设施
  - README 更新

### Modified Capabilities

（无 — 这是初始变更，不存在已有 specs）

## Impact

- `pyproject.toml`：新建，声明项目和依赖
- `run.py`：新建，应用启动入口
- `app/__init__.py`：新建，`create_app()` 应用工厂
- `app/config.py`：新建，配置类
- `app/utils/__init__.py`：新建
- `app/utils/response.py`：新建，统一 JSON 响应
- `app/utils/errors.py`：新建，异常类和错误处理
- `tests/conftest.py`：新建，pytest 共享 fixture
- `tests/test_app.py`：新建，基础测试
- `.gitignore`：更新（按 Foundation 需求）
- `.env.example`：更新
- `README.md`：更新（安装、测试、启动、健康检查说明）

**明确排除在本 Change 范围之外：**

- 数据库 Schema 与初始化
- Repository 层
- Service 层
- 认证与管理员创建（属于后续认证 Change）
- 学生 CRUD
- Jinja2 模板和前端静态文件
- MCP Server 与 MCP Client
- AI Chat
- 导入导出
- 数据迁移
