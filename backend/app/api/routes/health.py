from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import api_error
from app.api.schemas.simulation import COMMON_RESPONSES, HealthResponse
from app.infra.db import get_db_session
from app.infra.logging import warning

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="健康检查",
    description="检查 API 服务是否正常运行",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "服务健康", "model": HealthResponse},
    },
)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


async def check_database(session: AsyncSession) -> None:
    await session.execute(text("SELECT 1"))


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="就绪检查",
    description="检查 API 服务及数据库是否可接收请求",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "服务已就绪", "model": HealthResponse},
        503: {"description": "关键依赖不可用"},
    },
)
async def readiness_check(
    session: AsyncSession = Depends(get_db_session),
) -> HealthResponse:
    try:
        await check_database(session)
    except Exception as exc:
        warning("Readiness database check failed", exc_info=exc)
        raise api_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
            code="DATABASE_UNAVAILABLE",
        ) from exc
    return HealthResponse(status="ready")
