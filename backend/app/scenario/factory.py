from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.scenario.base import Scenario
from app.scenario.open_world.scenario import OpenWorldScenario
from app.scenario.truman_world.scenario import TrumanWorldScenario


def create_scenario(
    scenario_type: str | None,
    session: AsyncSession | None = None,
) -> Scenario:
    if scenario_type == "open_world":
        return OpenWorldScenario(session)
    return TrumanWorldScenario(session)
