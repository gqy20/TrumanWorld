from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.scenario.base import Scenario
from app.scenario.adapter_registry import get_scenario_adapter_registry
from app.scenario.bundle_registry import get_scenario_bundle_registry, resolve_default_scenario_id


def create_scenario(
    scenario_type: str | None,
    session: AsyncSession | None = None,
) -> Scenario:
    registry = get_scenario_bundle_registry()
    bundle = registry.get_bundle(scenario_type)
    if bundle is None:
        bundle = registry.get_bundle(resolve_default_scenario_id())
    adapter_registry = get_scenario_adapter_registry()
    scenario_id = bundle.manifest.id if bundle is not None else resolve_default_scenario_id()
    adapter = bundle.manifest.adapter if bundle is not None else scenario_id
    return adapter_registry.build(adapter, scenario_id=scenario_id, session=session)
