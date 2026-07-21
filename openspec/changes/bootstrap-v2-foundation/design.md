## Context

Student Management System V2 当前仅有规划文档，无任何可运行代码。本 Change 搭建 Flask 应用骨架，为后续所有功能（认证、学生 CRUD、MCP、AI Chat 等）提供统一基础。

**相关架构决策（ADR）：**
- ADR-001：分层架构（Route → Service → Repository）
- ADR-002：应用工厂模式 + Blueprint
- ADR-005：统一 API 响应格式
- ADR-014：Clean Baseline 已完成，Project Foundation 是第一个实现阶段

## Goals / Non-Goals

**Goals:**
- `create_app(config_name, config_overrides=None, load_env=True)` 应用工厂可创建 Flask 实例
- 三层配置边界：Development / Testing / Production
- 环境变量通过 `python-dotenv` 从 `.env` 文件加载，且加载时机在配置类实例化之前
- 统一的 JSON 响应辅助函数（`api_success()`, `api_error()`, `api_paginated()`）
- 应用级异常类（`AppError`, `NotFoundError`, `ValidationError`, `DuplicateError`, `ForbiddenError`）
- 全局错误处理三层覆盖：`AppError` → 业务异常；`HTTPException` → Werkzeug 原生异常；未预期 `Exception` → 500
- Blueprint 注册基础设施：提供 `register_blueprints(app)` 函数
- 健康检查端点 `GET /api/health` 使用统一 API 响应，`data` 为 `{"status": "ok"}`
- 日志配置：幂等 `configure_logging(app)`，优先使用 `logging.config.dictConfig`，级别由独立 `LOG_LEVEL` 环境变量控制
- `run.py` 启动入口，支持 `--host` 和 `--port` 参数，参数优先级：命令行参数 > 环境变量 > 默认值
- pytest 基础设施：conftest.py 提供 `app`（`load_env=False`）、`client` 等 fixture
- `pyproject.toml` 项目元数据和依赖声明
- README 更新

**Non-Goals:**
- 数据库 Schema 与初始化（后续 Gate 3: Database and Repository）
- Repository 层（后续 Gate 3: Database and Repository）
- Service 层（后续 Gate 4: Service Layer）
- 认证与管理员创建（后续 Gate 5: Authentication）
- 学生 CRUD（后续 Gate 6: REST API — Student CRUD）
- 模板和前端（后续 Gate 7–9）
- MCP 相关代码（后续 Gate 11: MCP Read Tools）
- AI Chat（后续 Gate 12: AI Chat）
- 导入导出（后续 Gate 10: Import and Export）
- 数据迁移（后续 Gate 13: Legacy Data Migration）

## Decisions

### D1：配置类设计

**决策：** 使用 Python 类继承实现配置边界。Foundation 阶段不要求 `DATABASE_PATH`，避免因缺少数据库配置导致启动失败。

```python
class Config:
    SECRET_KEY: str = "dev-secret-change-in-production"  # 开发/测试非生产默认值
    # DATABASE_PATH 由后续 Gate 3 定义，Foundation 阶段不校验

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True

class ProductionConfig(Config):
    SECRET_KEY: str  # 生产环境无默认值，启动时校验
```

**理由：** Flask 官方推荐模式，类继承减少重复，`app.config.from_object()` 原生支持。

**备选方案：**
- JSON/YAML 配置文件：增加格式解析依赖，不如 Python 类灵活。
- 单字典模式：缺少类型提示和配置边界隔离。

---

### D2：环境变量加载与配置读取顺序

**决策：** `create_app()` 先根据 `load_env` 参数决定是否调用 `load_dotenv()`，再将配置类的默认值与 `os.environ` 合并。

**关键时序：**
1. 配置类定义时声明静态默认值（如 `SECRET_KEY` 的 dev 默认值）。
2. `create_app()` 被调用时，若 `load_env=True` 则先执行 `load_dotenv()`（.env 文件写入 `os.environ`）。
3. 配置类实例化时从 `os.environ.get()` 读取——此时 .env 已生效，因此值正确覆盖。
4. `config_overrides` 在配置类实例化后通过 `app.config.update()` 应用，**优先级最高**。

**测试调用：**
```python
create_app("testing", load_env=False)  # 避免本机 .env 污染测试
```

**理由：** 先加载 .env 再读取配置类，确保配置类构造时环境变量已就位。`config_overrides` 最后应用，使其具有最高优先级。

---

### D3：统一响应工具设计

**决策：** 提供三个辅助函数：

```python
def api_success(data=None, message="", meta=None) -> tuple:
    """返回 200 成功响应"""
    # {"success": true, "data": data, "message": message, "error": null, "meta": meta or {}}

def api_error(message="", error=None, status_code=400) -> tuple:
    """返回错误响应。error 为标准结构，不得放入原始 Exception。"""
    # {"success": false, "data": null, "message": message,
    #  "error": {"code": "...", "details": null}, "meta": {}}

def api_paginated(data, total, page, page_size, message="") -> tuple:
    """返回分页成功响应"""
    # {"success": true, "data": data, "message": message, "error": null,
    #  "meta": {"page": page, "page_size": page_size, "total": total, "total_pages": ceil(total/page_size)}}
```

**error 字段结构：**
```python
{"code": "not_found", "details": None}        # 简单错误
{"code": "validation_error", "details": {...}}  # 详细验证错误
```
- `code`：机器可读的错误标识（snake_case），如 `"not_found"`、`"validation_error"`。
- `details`：可选详细数据（如字段级验证错误），不得将原始 `Exception` 对象放入响应。

**理由：**
- 函数式 API 比自定义 Response 子类更直观。
- ADR-005 强制统一格式，工具函数确保一致性。
- `api_paginated` 封装分页计算（`total_pages`），避免路由重复计算。

---

### D4：异常体系设计

**决策：** 自定义异常继承链：

```
AppError (Base)  ← 携带 code, message, status_code
├── NotFoundError      → 404, code="not_found"
├── ValidationError    → 400, code="validation_error"
├── DuplicateError     → 409, code="duplicate"
└── ForbiddenError     → 403, code="forbidden"
```

全局异常处理三层覆盖：

1. **`AppError`**（含子类）：`@errorhandler(AppError)` → `api_error(message=e.message, error={"code": e.code, "details": e.details}, status_code=e.status_code)`
2. **`werkzeug.exceptions.HTTPException`**：`@errorhandler(HTTPException)` → 提取 `e.code` 和 `e.description`，包装为统一格式。确保 404、405 等原生异常也返回统一 JSON。
3. **未预期 `Exception`**：`@errorhandler(Exception)` → 记录完整堆栈日志，客户端只返回 `{"success": false, "error": {"code": "internal_error", "details": null}, "message": "Internal server error"}`，状态码 500。**绝不暴露内部细节。**

**理由：**
- Service 层抛异常比返回 `(data, error)` 元组更符合 Python 惯例。
- 异常携带 HTTP 状态码、`code` 和错误消息，Route 层无需手动判断。
- ADR-001 第 12 条要求不得吞掉异常。
- 三层覆盖确保所有异常路径都被处理，不遗漏原生 HTTP 异常。

---

### D5：Blueprint 注册基础设施

**决策：** `app/__init__.py` 中提供 `register_blueprints(app)` 函数：

```python
def register_blueprints(app: Flask) -> None:
    """注册所有 Blueprint。路由模块在这里集中导入，避免循环引用。"""
    from app.routes.health import health_bp
    app.register_blueprint(health_bp)
```

**理由：** 集中注册避免循环导入。后续 Blueprint（auth、students、chat）只需在此函数追加一行。

---

### D6：日志配置

**决策：** 提供幂等的 `configure_logging(app)` 函数，优先使用 `logging.config.dictConfig`。日志级别由独立的 `LOG_LEVEL` 环境变量控制。

```python
def configure_logging(app: Flask) -> None:
    """应用日志配置。幂等——多次调用只生效一次。"""
    level = app.config.get("LOG_LEVEL", "INFO").upper()
    dict_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": level,
            },
        },
        "root": {
            "level": level,
            "handlers": ["console"],
        },
    }
    logging.config.dictConfig(dict_config)
```

**`LOG_LEVEL` 环境变量：** 独立于 `APP_ENV`。默认值 `"INFO"`。`create_app()` 读取后存入 `app.config["LOG_LEVEL"]`。

**理由：**
- `dictConfig` 比 `basicConfig` 更灵活、可扩展（未来可追加文件 handler、JSON 格式等）。
- 独立 `LOG_LEVEL` 环境变量避免将日志级别与运行环境耦合。
- 幂等设计防止重复调用时重置已有配置。

---

### D7：pytest 基础设施

**决策：** `conftest.py` 提供 fixture，测试时调用 `create_app("testing", load_env=False)` 避免本机 `.env` 污染。

```python
@pytest.fixture
def app():
    """创建测试用 Flask 应用实例（不加载 .env，避免本机环境干扰）。"""
    app = create_app("testing", load_env=False)
    yield app

@pytest.fixture
def client(app):
    """测试 HTTP 客户端。"""
    return app.test_client()
```

**Foundation 阶段不创建测试数据库。** 测试数据库由后续 Gate 3（Database and Repository）通过 `pytest.tmp_path` 注入临时文件路径实现。

**理由：** 应用工厂模式使测试可以创建独立实例。`load_env=False` 确保测试环境不受开发者本机 `.env` 文件影响。

---

### D8：依赖选择

| 依赖 | 版本 | 用途 |
|------|------|------|
| `flask` | >=3.0 | Web 框架 |
| `python-dotenv` | >=1.0 | 环境变量加载 |
| `pytest` | >=8.0 | 测试框架（dev 依赖） |

**不引入的依赖：** Flask-Login（认证阶段 Gate 5 引入）、pandas/openpyxl（导入导出 Gate 10 引入）、mcp（MCP Gate 11 引入）、httpx/requests（AI Chat Gate 12 引入）。

---

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|---------|
| 环境变量未设置导致运行时错误 | 仅生产环境校验 `SECRET_KEY`，开发/测试使用非生产默认值可启动；`DATABASE_PATH` 在 Foundation 阶段不校验 |
| 测试 fixture 与后续阶段冲突 | `conftest.py` 在 Foundation 阶段提供基础 fixture，后续阶段追加新的 fixture 而非修改已有的 |
| `.env` 文件被提交到 Git | `.gitignore` 已排除 `.env`，`.env.example` 只包含占位值 |
| 日志记录敏感信息 | 基础日志配置不记录请求体，后续阶段添加 PII 脱敏 |
