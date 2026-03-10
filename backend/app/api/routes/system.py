from __future__ import annotations

from fastapi import APIRouter

from app.infra.system_overview import get_system_overview_payload


router = APIRouter()


@router.get(
    "/system/overview",
    summary="项目运行总览",
    description="返回 backend/frontend/postgres 的聚合资源占用，供前端状态面板使用。",
    tags=["health"],
)
async def system_overview() -> dict[str, object]:
    return get_system_overview_payload()
