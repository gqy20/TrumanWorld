"""Economic state service - handles agent economic state updates."""

from __future__ import annotations


from app.sim.world import WorldState
from app.store.models import AgentEconomicState
from app.store.repositories import AgentEconomicStateRepository, EconomicEffectLogRepository


# Default values
DEFAULT_WORK_INCOME = 10.0  # Cash per work tick
DEFAULT_FOOD_DECAY_RATE = 0.05  # Food security decay per tick without income
DEFAULT_FOOD_RECOVERY_RATE = 0.02  # Food security recovery per tick with regular income
DEFAULT_NO_INCOME_THRESHOLD = 3  # Ticks without income before food starts decaying
DEFAULT_FOOD_RECOVERY_THRESHOLD = 2  # Ticks with income before recovery starts
DEFAULT_DAILY_LIVING_COST = 3.0  # Cash deducted per tick for basic living expenses
DEFAULT_HOUSING_COST = 1.0  # Cash deducted per tick for housing
DEFAULT_FOOD_COST = 2.0  # Cash deducted per tick for food


class EconomicStateService:
    """Service for managing agent economic state."""

    def __init__(self, session) -> None:
        self.session = session
        self.econ_repo = AgentEconomicStateRepository(session)
        self.effect_log_repo = EconomicEffectLogRepository(session)

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
            # Log work income effect
            await self.effect_log_repo.create(
                run_id=run_id,
                agent_id=agent_id,
                tick_no=tick_no,
                effect_type="daily_work_income",
                cash_delta=DEFAULT_WORK_INCOME,
                reason="work performed",
            )
            return updated

        return state

    async def process_tick_economic_effects(
        self,
        world: WorldState,
        agent_id: str,
        tick_no: int,
        run_id: str | None = None,
        case_id: str | None = None,
    ) -> AgentEconomicState:
        """Process economic effects at end of tick."""
        if run_id is None:
            run_id = self._get_run_id(world)
        state = await self.ensure_economic_state(world, agent_id, tick_no, run_id)

        employment_before = state.employment_status
        food_before = state.food_security

        # Check if agent has work_ban
        if world.has_restriction(agent_id, "work_ban", scope_value="work"):
            # Employment suspended while work banned
            if state.employment_status != "suspended":
                state = (
                    await self.econ_repo.update_employment_status(run_id, agent_id, "suspended")
                    or state
                )
                # Log governance work loss
                await self.effect_log_repo.create(
                    run_id=run_id,
                    agent_id=agent_id,
                    tick_no=tick_no,
                    effect_type="governance_work_loss",
                    cash_delta=0.0,
                    employment_status_before=employment_before,
                    employment_status_after="suspended",
                    reason="work_ban active",
                    case_id=case_id,
                )

        # Check food security changes (decay or recovery)
        if state.last_income_tick is not None:
            ticks_since_income = tick_no - state.last_income_tick
            if ticks_since_income >= DEFAULT_NO_INCOME_THRESHOLD:
                # Apply food decay when no income for too long
                decay = DEFAULT_FOOD_DECAY_RATE * (
                    ticks_since_income - DEFAULT_NO_INCOME_THRESHOLD + 1
                )
                state = await self.econ_repo.update_food_security(run_id, agent_id, -decay) or state
                # Log food decay effect (only if actually decayed)
                if state.food_security < food_before:
                    await self.effect_log_repo.create(
                        run_id=run_id,
                        agent_id=agent_id,
                        tick_no=tick_no,
                        effect_type="food_insecurity_decay",
                        cash_delta=0.0,
                        food_security_delta=state.food_security - food_before,
                        reason=f"no income for {ticks_since_income} ticks",
                    )
            elif ticks_since_income <= DEFAULT_FOOD_RECOVERY_THRESHOLD:
                # Recover food security when agent is earning regular income
                # Only recover if food_security is below maximum
                if state.food_security < 1.0:
                    state = (
                        await self.econ_repo.update_food_security(
                            run_id, agent_id, DEFAULT_FOOD_RECOVERY_RATE
                        )
                        or state
                    )
                    # Log food recovery effect (only if actually increased)
                    if state.food_security > food_before:
                        await self.effect_log_repo.create(
                            run_id=run_id,
                            agent_id=agent_id,
                            tick_no=tick_no,
                            effect_type="food_security_recovery",
                            cash_delta=0.0,
                            food_security_delta=state.food_security - food_before,
                            reason="regular income, food security recovering",
                        )

        return state

    async def process_tick_consumption(
        self,
        world: WorldState | None,
        agent_id: str,
        tick_no: int,
        run_id: str | None = None,
        daily_living_cost: float = DEFAULT_DAILY_LIVING_COST,
        housing_cost: float = DEFAULT_HOUSING_COST,
        food_cost: float = DEFAULT_FOOD_COST,
    ) -> AgentEconomicState | None:
        """Process daily consumption costs for an agent.

        Deducts living expenses from agent's cash each tick.
        This creates economic pressure - agents need to work to afford living costs.

        Args:
            world: The world state (used to determine time period)
            agent_id: The agent ID
            tick_no: Current tick number
            run_id: The simulation run ID
            daily_living_cost: Base daily living cost per tick
            housing_cost: Housing cost per tick
            food_cost: Food cost per tick

        Returns:
            Updated economic state or None if agent doesn't exist
        """
        if run_id is None and world is not None:
            run_id = self._get_run_id(world)

        if run_id is None:
            return None

        state = await self.ensure_economic_state(world, agent_id, tick_no, run_id)

        # Skip consumption for suspended agents (work_ban active)
        if state.employment_status == "suspended":
            return state

        total_cost = daily_living_cost + housing_cost + food_cost
        if total_cost <= 0:
            return state

        # Apply consumption cost
        cash_before = state.cash
        updated = await self.econ_repo.add_cash(run_id, agent_id, -total_cost)

        # Log the consumption effect
        await self.effect_log_repo.create(
            run_id=run_id,
            agent_id=agent_id,
            tick_no=tick_no,
            effect_type="daily_living_cost",
            cash_delta=-total_cost,
            reason=f"daily consumption (living={daily_living_cost}, housing={housing_cost}, food={food_cost})",
        )

        # If cash went negative, log food insecurity
        if updated and updated.cash < 0 and cash_before >= 0:
            # Agent just went into debt - increase food insecurity concern
            await self.effect_log_repo.create(
                run_id=run_id,
                agent_id=agent_id,
                tick_no=tick_no,
                effect_type="food_insecurity_warning",
                cash_delta=0.0,
                food_security_delta=-0.1,
                reason="cash depleted, food security at risk",
            )

        return updated or state

    def _get_run_id(self, world: WorldState) -> str:
        """Get run_id from world - stored in world_effects or derived."""
        # For now, use a placeholder - in actual use, this would come from context
        return world.world_effects.get("run_id", "unknown")
