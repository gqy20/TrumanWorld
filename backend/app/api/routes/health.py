from fastapi import APIRouter

from app.api.schemas.simulation import COMMON_RESPONSES, HealthResponse

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
