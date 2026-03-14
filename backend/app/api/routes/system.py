from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas.simulation import COMMON_RESPONSES, SystemOverviewResponse
from app.infra.system_overview import get_system_overview_payload

router = APIRouter()


@router.get(
    "/system/overview",
    response_model=SystemOverviewResponse,
    summary="项目运行总览",
    description="返回 backend/frontend/postgres 的聚合资源占用，供前端状态面板使用。",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "系统运行总览", "model": SystemOverviewResponse},
    },
)
async def system_overview() -> SystemOverviewResponse:
    return SystemOverviewResponse.model_validate(get_system_overview_payload())
