"""Tests for EconomicEffectLog model and repository."""

import pytest
import pytest_asyncio


from app.store.models import Agent, SimulationRun
from app.store.repositories import EconomicEffectLogRepository


@pytest.fixture
def effect_log_repo(db_session):
    return EconomicEffectLogRepository(db_session)


@pytest_asyncio.fixture
async def sample_run(db_session):
    run = SimulationRun(
        id="run-1",
        name="Test Run",
        status="running",
        current_tick=0,
    )
    db_session.add(run)
    await db_session.commit()
    return run


@pytest_asyncio.fixture
async def sample_agent(db_session, sample_run):
    agent = Agent(
        id="agent-1",
        run_id=sample_run.id,
        name="Alice",
        occupation="barista",
    )
    db_session.add(agent)
    await db_session.commit()
    return agent


class TestEconomicEffectLogRepository:
    """Test EconomicEffectLogRepository CRUD operations."""

    @pytest.mark.asyncio
    async def test_create(self, db_session, effect_log_repo, sample_run, sample_agent):
        log = await effect_log_repo.create(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            tick_no=20,
            effect_type="governance_work_loss",
            cash_delta=-10.0,
            food_security_delta=-0.1,
            housing_security_delta=0.0,
            employment_status_before="stable",
            employment_status_after="suspended",
            reason="work_ban active",
            case_id="case-1",
        )

        assert log.id is not None
        assert log.run_id == sample_run.id
        assert log.agent_id == sample_agent.id
        assert log.tick_no == 20
        assert log.effect_type == "governance_work_loss"
        assert log.cash_delta == -10.0
        assert log.food_security_delta == -0.1
        assert log.housing_security_delta == 0.0
        assert log.employment_status_before == "stable"
        assert log.employment_status_after == "suspended"
        assert log.reason == "work_ban active"
        assert log.case_id == "case-1"

    @pytest.mark.asyncio
    async def test_list_for_agent(self, db_session, effect_log_repo, sample_run, sample_agent):
        for i in range(5):
            await effect_log_repo.create(
                run_id=sample_run.id,
                agent_id=sample_agent.id,
                tick_no=i * 10,
                effect_type="daily_work_income",
                cash_delta=10.0,
            )

        logs = await effect_log_repo.list_for_agent(sample_run.id, sample_agent.id)
        assert len(logs) == 5

    @pytest.mark.asyncio
    async def test_list_for_agent_with_limit(
        self, db_session, effect_log_repo, sample_run, sample_agent
    ):
        for i in range(10):
            await effect_log_repo.create(
                run_id=sample_run.id,
                agent_id=sample_agent.id,
                tick_no=i * 10,
                effect_type="daily_work_income",
                cash_delta=10.0,
            )

        logs = await effect_log_repo.list_for_agent(sample_run.id, sample_agent.id, limit=3)
        assert len(logs) == 3

    @pytest.mark.asyncio
    async def test_list_for_agent_by_type(
        self, db_session, effect_log_repo, sample_run, sample_agent
    ):
        await effect_log_repo.create(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            tick_no=10,
            effect_type="daily_work_income",
            cash_delta=10.0,
        )
        await effect_log_repo.create(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            tick_no=20,
            effect_type="governance_work_loss",
            cash_delta=-10.0,
        )

        logs = await effect_log_repo.list_for_agent(
            sample_run.id, sample_agent.id, effect_type="governance_work_loss"
        )
        assert len(logs) == 1
        assert logs[0].effect_type == "governance_work_loss"

    @pytest.mark.asyncio
    async def test_list_for_run(self, db_session, effect_log_repo, sample_run, sample_agent):
        for i in range(3):
            await effect_log_repo.create(
                run_id=sample_run.id,
                agent_id=sample_agent.id,
                tick_no=i * 10,
                effect_type="daily_work_income",
                cash_delta=10.0,
            )

        logs = await effect_log_repo.list_for_run(sample_run.id)
        assert len(logs) == 3

    @pytest.mark.asyncio
    async def test_get_recent_logs(self, db_session, effect_log_repo, sample_run, sample_agent):
        for i in range(20):
            await effect_log_repo.create(
                run_id=sample_run.id,
                agent_id=sample_agent.id,
                tick_no=i,
                effect_type="daily_work_income",
                cash_delta=10.0,
            )

        logs = await effect_log_repo.get_recent_logs(sample_run.id, sample_agent.id, limit=5)
        assert len(logs) == 5
        # Most recent first
        assert logs[0].tick_no == 19
