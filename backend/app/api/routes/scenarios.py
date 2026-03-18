from fastapi import APIRouter

from app.api.schemas.simulation import COMMON_RESPONSES, ScenarioSummaryResponse
from app.scenario.bundle_registry import get_scenario_bundle_registry

router = APIRouter()


@router.get(
    "/scenarios",
    response_model=list[ScenarioSummaryResponse],
    summary="列出可用场景",
    description="返回当前项目中已注册的场景包列表。",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "场景列表", "model": list[ScenarioSummaryResponse]},
    },
)
async def list_scenarios() -> list[ScenarioSummaryResponse]:
    registry = get_scenario_bundle_registry()
    return [
        ScenarioSummaryResponse(
            id=bundle.manifest.id,
            name=bundle.manifest.name,
            version=bundle.manifest.version,
        )
        for bundle in registry.list_bundles()
    ]
