from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas.simulation import COMMON_RESPONSES
from app.infra.system_overview import get_system_overview_payload


router = APIRouter()


@router.get(
    "/system/overview",
    summary="项目运行总览",
    description="返回 backend/frontend/postgres 的聚合资源占用，供前端状态面板使用。",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "系统运行总览"},
    },
)
async def system_overview() -> dict[str, object]:
    return get_system_overview_payload()
