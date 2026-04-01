"""Tests for delta_applier."""

from datetime import datetime

import pytest
from sqlalchemy import select

from app.sim.delta_applier import DeltaApplier
from app.sim.economic_state_service import EconomicStateService
from app.sim.state_delta_models import AgentDelta, StateDelta
from app.sim.world import AgentState, WorldState


def _build_world(run_id: str = "run-1") -> WorldState:
    """Build a test world."""
    return WorldState(
        current_time=datetime(2026, 3, 7, 8, 0, 0),
        agents={
            "alice": AgentState(
                id="alice",
                name="Alice",
                location_id="cafe",
                status={},
            ),
            "bob": AgentState(
                id="bob",
                name="Bob",
                location_id="cafe",
                status={},
            ),
        },
        locations={},
        world_effects={"run_id": run_id},
    )


class TestDeltaApplierCashDelta:
    """Test cash delta application."""

    @pytest.mark.asyncio
    async def test_apply_positive_cash_delta(self, db_session):
        """Test applying positive cash delta."""
        from app.store.models import AgentEconomicState

        # Setup: create initial economic state
        service = EconomicStateService(db_session)
        world = _build_world()
        await service.ensure_economic_state(world, "alice", tick_no=0, run_id="run-1")

        # Apply positive delta
        applier = DeltaApplier(db_session)
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(cash_delta=50.0),
            },
            effect_type="gift_received",
            reason="Received gift from friend",
        )

        affected = await applier.apply(delta, run_id="run-1", tick_no=1)

        assert "alice" in affected

        # Verify cash increased
        state = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == "alice")
        )
        result = state.scalars().first()
        assert result.cash == 150.0  # 100 initial + 50

    @pytest.mark.asyncio
    async def test_apply_negative_cash_delta(self, db_session):
        """Test applying negative cash delta."""
        from app.store.models import AgentEconomicState

        service = EconomicStateService(db_session)
        world = _build_world()
        await service.ensure_economic_state(world, "alice", tick_no=0, run_id="run-1")

        applier = DeltaApplier(db_session)
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(cash_delta=-30.0),
            },
            effect_type="trade_payment",
            reason="Paid for coffee",
        )

        affected = await applier.apply(delta, run_id="run-1", tick_no=1)

        assert "alice" in affected

        state = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == "alice")
        )
        result = state.scalars().first()
        assert result.cash == 70.0  # 100 initial - 30

    @pytest.mark.asyncio
    async def test_apply_trade_delta_balanced(self, db_session):
        """Test applying balanced trade delta (currency conserved)."""
        from app.store.models import AgentEconomicState

        service = EconomicStateService(db_session)
        world = _build_world()
        await service.ensure_economic_state(world, "alice", tick_no=0, run_id="run-1")
        await service.ensure_economic_state(world, "bob", tick_no=0, run_id="run-1")

        applier = DeltaApplier(db_session)
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(cash_delta=-30.0),
                "bob": AgentDelta(cash_delta=30.0),
            },
            effect_type="trade",
            reason="Alice bought coffee from Bob",
        )

        affected = await applier.apply(delta, run_id="run-1", tick_no=1)

        assert "alice" in affected
        assert "bob" in affected

        # Verify currency conservation: total should still be 200
        alice_state = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == "alice")
        )
        bob_state = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == "bob")
        )
        alice_cash = alice_state.scalars().first().cash
        bob_cash = bob_state.scalars().first().cash

        assert alice_cash == 70.0
        assert bob_cash == 130.0
        assert (alice_cash + bob_cash) == 200.0  # Currency conserved


class TestDeltaApplierFoodSecurity:
    """Test food security delta application."""

    @pytest.mark.asyncio
    async def test_apply_food_security_delta(self, db_session):
        """Test applying food security delta."""
        from app.store.models import AgentEconomicState

        service = EconomicStateService(db_session)
        world = _build_world()
        state = await service.ensure_economic_state(world, "alice", tick_no=0, run_id="run-1")
        state.food_security = 0.8
        await db_session.commit()

        applier = DeltaApplier(db_session)
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(food_security_delta=-0.2),
            },
            effect_type="food_consumption",
            reason="Ate meal",
        )

        affected = await applier.apply(delta, run_id="run-1", tick_no=1)

        assert "alice" in affected

        result = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == "alice")
        )
        econ_state = result.scalars().first()
        assert econ_state.food_security == pytest.approx(0.6)


class TestDeltaApplierEmploymentStatus:
    """Test employment status delta application."""

    @pytest.mark.asyncio
    async def test_apply_employment_status_delta(self, db_session):
        """Test applying employment status change."""
        from app.store.models import AgentEconomicState

        service = EconomicStateService(db_session)
        world = _build_world()
        await service.ensure_economic_state(world, "alice", tick_no=0, run_id="run-1")

        applier = DeltaApplier(db_session)
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(employment_status="suspended"),
            },
            effect_type="work_ban",
            reason="Employment suspended due to work ban",
        )

        affected = await applier.apply(delta, run_id="run-1", tick_no=1)

        assert "alice" in affected

        result = await db_session.execute(
            select(AgentEconomicState).where(AgentEconomicState.agent_id == "alice")
        )
        econ_state = result.scalars().first()
        assert econ_state.employment_status == "suspended"
