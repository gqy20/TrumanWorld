from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.scenario.base import Scenario
from app.scenario.open_world.scenario import OpenWorldScenario
from app.scenario.narrative_world.scenario import NarrativeWorldScenario

ScenarioBuilder = Callable[[str, AsyncSession | None], Scenario]


class ScenarioAdapterRegistry:
    def __init__(self) -> None:
        self._builders: dict[str, ScenarioBuilder] = {}

    def register(self, adapter: str, builder: ScenarioBuilder) -> None:
        self._builders[adapter] = builder

    def build(
        self,
        adapter: str,
        *,
        scenario_id: str,
        session: AsyncSession | None = None,
    ) -> Scenario:
        builder = self._builders.get(adapter)
        if builder is None:
            msg = f"Unknown scenario adapter: {adapter}"
            raise ValueError(msg)
        return builder(scenario_id, session)


def _build_narrative_world_scenario(
    scenario_id: str,
    session: AsyncSession | None,
) -> Scenario:
    return NarrativeWorldScenario(session, scenario_id=scenario_id)


def _build_open_world_scenario(
    scenario_id: str,
    session: AsyncSession | None,
) -> Scenario:
    return OpenWorldScenario(session)


def create_default_scenario_adapter_registry() -> ScenarioAdapterRegistry:
    registry = ScenarioAdapterRegistry()
    registry.register("narrative_world", _build_narrative_world_scenario)
    registry.register("open_world", _build_open_world_scenario)
    return registry


def get_scenario_adapter_registry() -> ScenarioAdapterRegistry:
    return create_default_scenario_adapter_registry()
