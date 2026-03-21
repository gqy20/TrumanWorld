"""Tests for AgentEconomicState model and repository."""

import pytest
from datetime import datetime

from sqlalchemy import select

from app.store.models import AgentEconomicState, SimulationRun, Agent
from app.store.repositories import AgentEconomicStateRepository


@pytest.fixture
def economic_state_repo(db_session):
    return AgentEconomicStateRepository(db_session)


@pytest.fixture
def sample_run(db_session):
    run = SimulationRun(
        id="run-1",
        name="Test Run",
        status="running",
        current_tick=0,
    )
    db_session.add(run)
    db_session.commit()
    return run


@pytest.fixture
def sample_agent(db_session, sample_run):
    agent = Agent(
        id="agent-1",
        run_id=sample_run.id,
        name="Alice",
        occupation="barista",
    )
    db_session.add(agent)
    db_session.commit()
    return agent


class TestAgentEconomicStateModel:
    """Test AgentEconomicState model creation and attributes."""

    def test_create_economic_state_minimal(self, db_session, sample_run, sample_agent):
        state = AgentEconomicState(
            id="econ-1",
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            cash=100.0,
            employment_status="stable",
        )
        db_session.add(state)
        db_session.commit()

        assert state.id == "econ-1"
        assert state.run_id == sample_run.id
        assert state.agent_id == sample_agent.id
        assert state.cash == 100.0
        assert state.employment_status == "stable"

    def test_create_economic_state_full_fields(self, db_session, sample_run, sample_agent):
        state = AgentEconomicState(
            id="econ-2",
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            cash=50.0,
            employment_status="unstable",
            food_security=0.8,
            housing_security=1.0,
            work_restriction_until_tick=20,
            last_income_tick=5,
        )
        db_session.add(state)
        db_session.commit()

        assert state.food_security == 0.8
        assert state.housing_security == 1.0
        assert state.work_restriction_until_tick == 20
        assert state.last_income_tick == 5


class TestAgentEconomicStateRepository:
    """Test AgentEconomicStateRepository CRUD operations."""

    @pytest.mark.asyncio
    async def test_upsert_creates_new(self, db_session, economic_state_repo, sample_run, sample_agent):
        state = await economic_state_repo.upsert(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            cash=100.0,
            employment_status="stable",
        )

        assert state.cash == 100.0
        assert state.employment_status == "stable"

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, db_session, economic_state_repo, sample_run, sample_agent):
        # Create first
        await economic_state_repo.upsert(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            cash=100.0,
            employment_status="stable",
        )

        # Update
        updated = await economic_state_repo.upsert(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            cash=80.0,
            employment_status="unstable",
        )

        assert updated.cash == 80.0
        assert updated.employment_status == "unstable"

    @pytest.mark.asyncio
    async def test_get_for_agent(self, db_session, economic_state_repo, sample_run, sample_agent):
        await economic_state_repo.upsert(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            cash=100.0,
            employment_status="stable",
        )

        state = await economic_state_repo.get_for_agent(sample_run.id, sample_agent.id)
        assert state is not None
        assert state.cash == 100.0

    @pytest.mark.asyncio
    async def test_get_for_agent_not_found(self, db_session, economic_state_repo, sample_run):
        state = await economic_state_repo.get_for_agent(sample_run.id, "nonexistent")
        assert state is None

    @pytest.mark.asyncio
    async def test_add_cash(self, db_session, economic_state_repo, sample_run, sample_agent):
        await economic_state_repo.upsert(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            cash=100.0,
            employment_status="stable",
        )

        updated = await economic_state_repo.add_cash(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            amount=50.0,
        )

        assert updated.cash == 150.0

    @pytest.mark.asyncio
    async def test_deduct_cash(self, db_session, economic_state_repo, sample_run, sample_agent):
        await economic_state_repo.upsert(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            cash=100.0,
            employment_status="stable",
        )

        updated = await economic_state_repo.deduct_cash(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            amount=30.0,
        )

        assert updated.cash == 70.0

    @pytest.mark.asyncio
    async def test_deduct_cash_cannot_go_negative(self, db_session, economic_state_repo, sample_run, sample_agent):
        await economic_state_repo.upsert(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            cash=10.0,
            employment_status="stable",
        )

        updated = await economic_state_repo.deduct_cash(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            amount=50.0,
        )

        # Should not go below 0
        assert updated.cash == 0.0

    @pytest.mark.asyncio
    async def test_update_food_security(self, db_session, economic_state_repo, sample_run, sample_agent):
        await economic_state_repo.upsert(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            cash=100.0,
            employment_status="stable",
            food_security=1.0,
        )

        updated = await economic_state_repo.update_food_security(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            delta=-0.2,
        )

        assert updated.food_security == 0.8

    @pytest.mark.asyncio
    async def test_update_employment_status(self, db_session, economic_state_repo, sample_run, sample_agent):
        await economic_state_repo.upsert(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            cash=100.0,
            employment_status="stable",
        )

        updated = await economic_state_repo.update_employment_status(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            new_status="suspended",
        )

        assert updated.employment_status == "suspended"

    @pytest.mark.asyncio
    async def test_set_work_restriction(self, db_session, economic_state_repo, sample_run, sample_agent):
        await economic_state_repo.upsert(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            cash=100.0,
            employment_status="stable",
        )

        updated = await economic_state_repo.set_work_restriction(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            until_tick=50,
        )

        assert updated.work_restriction_until_tick == 50
