"""Tests for daily consumption in economic_state_service."""

from datetime import datetime

import pytest
from sqlalchemy import select

from app.sim.economic_state_service import (
    DEFAULT_DAILY_LIVING_COST,
    DEFAULT_FOOD_COST,
    DEFAULT_HOUSING_COST,
    EconomicStateService,
)
from app.sim.world import AgentState, WorldState
from app.store.models import AgentEconomicState


def _build_world_with_agent(agent_id: str = "alice", run_id: str = "run-1") -> WorldState:
    return WorldState(
        current_time=datetime(2026, 3, 7, 8, 0, 0),
        current_tick=10,
        world_effects={"run_id": run_id},
        agents={
            agent_id: AgentState(
                id=agent_id,
                name="Alice",
                location_id="home",
                status={},
            )
        },
        locations={},
    )


class TestProcessTickConsumption:
    """Test process_tick_consumption method."""

    @pytest.mark.asyncio
    async def test_consumption_deducts_cash(self, db_session):
        """Test that consumption deducts cash from agent."""
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        # Ensure economic state exists
        await service.ensure_economic_state(world, agent_id, tick_no=0, run_id="run-1")

        # Get initial cash
        initial_state = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == agent_id)
        )
        initial_cash = initial_state.scalars().first().cash

        # Process consumption
        result = await service.process_tick_consumption(
            world=world,
            agent_id=agent_id,
            tick_no=1,
            run_id="run-1",
        )

        total_cost = DEFAULT_DAILY_LIVING_COST + DEFAULT_HOUSING_COST + DEFAULT_FOOD_COST
        expected_cash = initial_cash - total_cost

        assert result.cash == expected_cash

    @pytest.mark.asyncio
    async def test_consumption_creates_effect_log(self, db_session):
        """Test that consumption creates an effect log entry."""
        from app.store.models import EconomicEffectLog

        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        await service.ensure_economic_state(world, agent_id, tick_no=0, run_id="run-1")

        await service.process_tick_consumption(
            world=world,
            agent_id=agent_id,
            tick_no=1,
            run_id="run-1",
        )

        # Check effect log was created
        logs = await db_session.execute(
            select(EconomicEffectLog).where(
                EconomicEffectLog.agent_id == agent_id,
                EconomicEffectLog.tick_no == 1,
            )
        )
        log = logs.scalars().first()

        assert log is not None
        assert log.effect_type == "daily_living_cost"
        total_cost = DEFAULT_DAILY_LIVING_COST + DEFAULT_HOUSING_COST + DEFAULT_FOOD_COST
        assert log.cash_delta == -total_cost

    @pytest.mark.asyncio
    async def test_suspended_agent_skips_consumption(self, db_session):
        """Test that suspended agents don't pay consumption."""
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        # Set up suspended state
        await service.ensure_economic_state(world, agent_id, tick_no=0, run_id="run-1")
        state = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == agent_id)
        )
        state.scalars().first().employment_status = "suspended"
        await db_session.commit()

        initial_cash = (await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == agent_id)
        )).scalars().first().cash

        result = await service.process_tick_consumption(
            world=world,
            agent_id=agent_id,
            tick_no=1,
            run_id="run-1",
        )

        # Cash should not change for suspended agents
        assert result.cash == initial_cash

    @pytest.mark.asyncio
    async def test_custom_consumption_costs(self, db_session):
        """Test consumption with custom costs."""
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        await service.ensure_economic_state(world, agent_id, tick_no=0, run_id="run-1")

        initial_cash = (await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == agent_id)
        )).scalars().first().cash

        custom_living = 5.0
        custom_housing = 2.0
        custom_food = 3.0
        total_custom = custom_living + custom_housing + custom_food

        await service.process_tick_consumption(
            world=world,
            agent_id=agent_id,
            tick_no=1,
            run_id="run-1",
            daily_living_cost=custom_living,
            housing_cost=custom_housing,
            food_cost=custom_food,
        )

        final_state = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == agent_id)
        )
        assert final_state.scalars().first().cash == initial_cash - total_custom

    @pytest.mark.asyncio
    async def test_cash_clamped_at_zero_does_not_go_negative(self, db_session):
        """Test that cash is clamped at 0 and does not go negative.

        Note: add_cash implementation uses max(0, cash + delta) to prevent negative cash.
        The food_insecurity_warning is designed for a future version where negative
        cash is allowed.
        """
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        # Set up with low cash
        await service.ensure_economic_state(world, agent_id, tick_no=0, run_id="run-1")
        state = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == agent_id)
        )
        state.scalars().first().cash = 3.0  # Less than consumption cost (~6)
        await db_session.commit()

        result = await service.process_tick_consumption(
            world=world,
            agent_id=agent_id,
            tick_no=1,
            run_id="run-1",
        )

        # Cash should be clamped to 0, not negative
        assert result.cash == 0.0


class TestEconomicFlow:
    """Test the complete economic flow with consumption."""

    @pytest.mark.asyncio
    async def test_work_and_consumption_flow(self, db_session):
        """Test that working + consumption results in net positive."""
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        # Tick 0: Initial state
        await service.ensure_economic_state(world, agent_id, tick_no=0, run_id="run-1")

        # Tick 1: Work
        world.current_tick = 1
        await service.process_work_income(
            world=world,
            agent_id=agent_id,
            tick_no=1,
            run_id="run-1",
        )

        # Tick 1: Consumption
        consumption_result = await service.process_tick_consumption(
            world=world,
            agent_id=agent_id,
            tick_no=1,
            run_id="run-1",
        )

        total_cost = DEFAULT_DAILY_LIVING_COST + DEFAULT_HOUSING_COST + DEFAULT_FOOD_COST
        net_income = 10.0 - total_cost  # work income - consumption

        # Cash should be 100 + net_income
        assert consumption_result.cash == 100.0 + net_income

    @pytest.mark.asyncio
    async def test_no_work_with_consumption_depletes_cash(self, db_session):
        """Test that without working, consumption depletes cash."""
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        # Tick 0: Initial state
        await service.ensure_economic_state(world, agent_id, tick_no=0, run_id="run-1")

        # Tick 1-5: No work, just consumption
        for tick in range(1, 6):
            world.current_tick = tick
            await service.process_tick_consumption(
                world=world,
                agent_id=agent_id,
                tick_no=tick,
                run_id="run-1",
            )

        final_state = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == agent_id)
        )
        total_cost = (DEFAULT_DAILY_LIVING_COST + DEFAULT_HOUSING_COST + DEFAULT_FOOD_COST) * 5
        expected_cash = 100.0 - total_cost

        assert final_state.scalars().first().cash == expected_cash
