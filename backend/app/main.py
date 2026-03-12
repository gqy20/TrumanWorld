from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.infra.db import get_db_session_context
from app.infra.logging import get_logger, info
from app.infra.settings import get_settings
from app.store.repositories import RunRepository

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup: Reset all running runs to paused
    info("Application starting up, checking for running runs...")
    try:
        async for session in get_db_session_context():
            repo = RunRepository(session)
            reset_runs = await repo.reset_running_on_startup()
            if reset_runs:
                info(
                    f"Reset {len(reset_runs)} running runs to paused (marked for restore): "
                    f"{[r.id for r in reset_runs]}"
                )
            break  # Only need one session
    except Exception as e:
        logger.error(f"Failed to reset running runs on startup: {e}")

    yield  # Application runs here

    # Shutdown: cleanup if needed
    info("Application shutting down")
    try:
        from app.sim.scheduler import get_scheduler

        await get_scheduler().stop_all()
    except Exception as e:
        logger.warning(f"Failed to stop scheduler on shutdown: {e}")

    try:
        from app.cognition.registry import get_cognition_registry

        await get_cognition_registry().cleanup()
    except Exception as e:
        logger.warning(f"Failed to close connection pool on shutdown: {e}")


def create_app() -> FastAPI:
    settings = get_settings()

    info(f"Starting AI Truman World API in {settings.app_env} mode")
    info(f"Log level: {settings.log_level}")
    info(f"CORS allowed origins: {settings.cors_allowed_origins}")

    app = FastAPI(
        title="AI Truman World API",
        version="0.1.0",
        lifespan=lifespan,
        description="""
## 楚门的世界 AI 版 - 你是导演

AI 居民们不知道自己是 AI。你只能观察、记录、注入事件——**不能操控任何人的想法**。

### 核心功能

- **Run 管理**: 创建、启动、暂停、恢复模拟运行
- **Agent 观测**: 查看任意 agent 的状态、记忆、关系和事件
- **时间线**: 获取完整的事件时间线
- **世界快照**: 查看世界状态的实时快照
- **导演系统**: 注入事件影响世界走向

### 技术栈

- **Backend**: Python + FastAPI
- **AI Cognition**: Claude Agent SDK
- **Database**: PostgreSQL + pgvector
- **Cache**: Redis
        """,
        openapi_tags=[
            {
                "name": "health",
                "description": "健康检查接口",
            },
            {
                "name": "runs",
                "description": """
**模拟运行管理**

创建和控制 AI 模拟运行 (Run)，包括：
- 创建新 run（可选填充演示数据）
- 启动/暂停/恢复运行
- 删除 run
- 查看 run 列表和详情
- 推进 tick
                """,
            },
            {
                "name": "agents",
                "description": """
**Agent 观测**

查看模拟运行中的 agent 详细信息：
- 列出所有 agent
- 获取 agent 详情（状态、记忆、关系、事件）
                """,
            },
            {
                "name": "world",
                "description": """
**世界观测**

查看模拟世界的状态：
- 世界快照（地点、agent 分布、统计）
- 事件时间线（支持多维过滤）
- 世界时钟
                """,
            },
            {
                "name": "director",
                "description": """
**导演系统**

作为导演干预模拟世界：
- 查看世界健康度观察
- 查看干预计划明细
- 注入世界事件（活动、关闭、广播、天气变化等）
                """,
            },
            {
                "name": "system",
                "description": """
**系统监控**

查看系统运行状态：
- backend/frontend/postgres 资源占用
- 进程 CPU/内存统计
                """,
            },
            {
                "name": "observability",
                "description": """
**可观测性**

Prometheus 指标暴露，供监控系统抓取。
                """,
            },
        ],
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.include_router(api_router, prefix=settings.api_prefix)

    info(f"API routes registered with prefix: {settings.api_prefix}")
    return app


app = create_app()
