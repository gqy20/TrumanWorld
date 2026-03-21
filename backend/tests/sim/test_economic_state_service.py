"""Tests for economic_state_service."""

from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.sim.action_resolver import ActionResult
from app.sim.economic_state_service import EconomicStateService
from app.sim.world import AgentState, RestrictionState, WorldState
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


class TestEconomicStateServiceWorkIncome:
    """Test work income processing."""

    @pytest.mark.asyncio
    async def test_process_work_income_adds_cash(self, db_session):
        """When agent works, add income to cash."""
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        # Ensure economic state exists
        await service.ensure_economic_state(world, agent_id, tick_no=10)

        result = await service.process_work_income(
            world=world,
            agent_id=agent_id,
            tick_no=10,
        )

        assert result is not None
        assert result.cash > 100.0  # Initial cash was 100

    @pytest.mark.asyncio
    async def test_process_work_income_records_last_income_tick(self, db_session):
        """Work income updates last_income_tick."""
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        await service.ensure_economic_state(world, agent_id, tick_no=10)

        result = await service.process_work_income(
            world=world,
            agent_id=agent_id,
            tick_no=10,
        )

        assert result.last_income_tick == 10


class TestEconomicStateServiceWorkBan:
    """Test work ban economic effects."""

    @pytest.mark.asyncio
    async def test_work_ban_reduces_food_security_over_time(self, db_session):
        """When agent cannot work due to work_ban, food_security decreases."""
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        # Set up initial state with last income at tick 0
        await service.ensure_economic_state(world, agent_id, tick_no=0)
        state = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == agent_id)
        )
        econ_state = state.scalars().first()
        econ_state.last_income_tick = 0
        econ_state.food_security = 1.0
        await db_session.commit()

        # Agent has work_ban, no income for several ticks
        # Process tick 10 with work_ban active
        world.add_restriction(
            agent_id,
            RestrictionState(
                id="ban-1",
                restriction_type="work_ban",
                scope_type="action",
                scope_value="work",
                start_tick=0,
                end_tick=50,
                reason="block",
            ),
        )

        result = await service.process_tick_economic_effects(
            world=world,
            agent_id=agent_id,
            tick_no=10,
        )

        assert result.food_security < 1.0  # Should decrease

    @pytest.mark.asyncio
    async def test_work_ban_sets_employment_to_suspended(self, db_session):
        """When work_ban active, employment status becomes suspended."""
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        await service.ensure_economic_state(world, agent_id, tick_no=0)

        world.add_restriction(
            agent_id,
            RestrictionState(
                id="ban-1",
                restriction_type="work_ban",
                scope_type="action",
                scope_value="work",
                start_tick=0,
                end_tick=50,
                reason="block",
            ),
        )

        result = await service.process_tick_economic_effects(
            world=world,
            agent_id=agent_id,
            tick_no=10,
        )

        assert result.employment_status == "suspended"

    @pytest.mark.asyncio
    async def test_no_income_ticks_threshold(self, db_session):
        """After N ticks without income, food_security decreases."""
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        # Create economic state with last income at tick 0
        await service.ensure_economic_state(world, agent_id, tick_no=0)
        state = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == agent_id)
        )
        econ_state = state.scalars().first()
        econ_state.last_income_tick = 0
        econ_state.food_security = 1.0
        await db_session.commit()

        # Current tick is 10, no income since tick 0
        result = await service.process_tick_economic_effects(
            world=world,
            agent_id=agent_id,
            tick_no=10,
        )

        # After 10 ticks without income, food_security should decrease
        assert result.food_security < 1.0


class TestEconomicStateServiceEnsure:
    """Test economic state initialization."""

    @pytest.mark.asyncio
    async def test_ensure_economic_state_creates_new(self, db_session):
        """Ensure creates economic state if not exists."""
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        result = await service.ensure_economic_state(world, agent_id, tick_no=0)

        assert result is not None
        assert result.cash == 100.0
        assert result.employment_status == "stable"
        assert result.food_security == 1.0

    @pytest.mark.asyncio
    async def test_ensure_economic_state_returns_existing(self, db_session):
        """Ensure returns existing state if exists."""
        service = EconomicStateService(db_session)
        world = _build_world_with_agent()
        agent_id = "alice"

        await service.ensure_economic_state(world, agent_id, tick_no=0)

        # Update cash
        state = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == agent_id)
        )
        econ_state = state.scalars().first()
        econ_state.cash = 200.0
        await db_session.commit()

        result = await service.ensure_economic_state(world, agent_id, tick_no=5)

        assert result.cash == 200.0
