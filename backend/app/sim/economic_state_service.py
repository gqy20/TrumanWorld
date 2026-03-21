"""Economic state service - handles agent economic state updates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.sim.world import WorldState
from app.store.repositories import AgentEconomicStateRepository

if TYPE_CHECKING:
    pass


# Default values
DEFAULT_WORK_INCOME = 10.0  # Cash per work tick
DEFAULT_FOOD_DECAY_RATE = 0.05  # Food security decay per tick without income
DEFAULT_NO_INCOME_THRESHOLD = 3  # Ticks without income before food starts decaying


class EconomicStateService:
    """Service for managing agent economic state."""

    def __init__(self, session) -> None:
        self.session = session
        self.econ_repo = AgentEconomicStateRepository(session)

    async def ensure_economic_state(
        self,
        world: WorldState,
        agent_id: str,
        tick_no: int,
        run_id: str | None = None,
    ) -> AgentEconomicState:
        """Ensure economic state exists for agent, creating if needed."""
        if run_id is None:
            run_id = self._get_run_id(world)
        state = await self.econ_repo.get_for_agent(run_id, agent_id)
        if state is None:
            state = await self.econ_repo.upsert(
                run_id=run_id,
                agent_id=agent_id,
                cash=100.0,
                employment_status="stable",
                food_security=1.0,
                housing_security=1.0,
            )
        return state

    async def process_work_income(
        self,
        world: WorldState,
        agent_id: str,
        tick_no: int,
        run_id: str | None = None,
    ) -> AgentEconomicState:
        """Process work income for an agent."""
        if run_id is None:
            run_id = self._get_run_id(world)
        state = await self.ensure_economic_state(world, agent_id, tick_no, run_id)

        # Check if agent has work_ban
        if world.has_restriction(agent_id, "work_ban", scope_value="work"):
            return state

        # Add work income
        updated = await self.econ_repo.add_cash(run_id, agent_id, DEFAULT_WORK_INCOME)
        if updated:
            updated.last_income_tick = tick_no
            await self.session.commit()
            return updated

        return state

    async def process_tick_economic_effects(
        self,
        world: WorldState,
        agent_id: str,
        tick_no: int,
        run_id: str | None = None,
    ) -> AgentEconomicState:
        """Process economic effects at end of tick."""
        if run_id is None:
            run_id = self._get_run_id(world)
        state = await self.ensure_economic_state(world, agent_id, tick_no, run_id)

        # Check if agent has work_ban
        if world.has_restriction(agent_id, "work_ban", scope_value="work"):
            # Employment suspended while work banned
            if state.employment_status != "suspended":
                state = await self.econ_repo.update_employment_status(
                    run_id, agent_id, "suspended"
                ) or state

        # Check if agent should get food decay (no income for N ticks)
        if state.last_income_tick is not None:
            ticks_since_income = tick_no - state.last_income_tick
            if ticks_since_income >= DEFAULT_NO_INCOME_THRESHOLD:
                # Apply food decay
                decay = DEFAULT_FOOD_DECAY_RATE * (ticks_since_income - DEFAULT_NO_INCOME_THRESHOLD + 1)
                state = await self.econ_repo.update_food_security(
                    run_id, agent_id, -decay
                ) or state

        return state

    def _get_run_id(self, world: WorldState) -> str:
        """Get run_id from world - stored in world_effects or derived."""
        # For now, use a placeholder - in actual use, this would come from context
        return world.world_effects.get("run_id", "unknown")
