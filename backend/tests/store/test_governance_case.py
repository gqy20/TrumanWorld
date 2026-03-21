"""Tests for GovernanceCase model and repository."""

import pytest
from datetime import datetime

from sqlalchemy import select

from app.store.models import GovernanceCase, SimulationRun, Agent
from app.store.repositories import GovernanceCaseRepository


@pytest.fixture
def governance_case_repo(db_session):
    return GovernanceCaseRepository(db_session)


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


class TestGovernanceCaseModel:
    """Test GovernanceCase model creation and attributes."""

    def test_create_governance_case_minimal(self, db_session, sample_run, sample_agent):
        case = GovernanceCase(
            id="case-1",
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            status="open",
            opened_tick=0,
            primary_reason="late_night_activity",
        )
        db_session.add(case)
        db_session.commit()

        assert case.id == "case-1"
        assert case.run_id == sample_run.id
        assert case.agent_id == sample_agent.id
        assert case.status == "open"
        assert case.opened_tick == 0
        assert case.primary_reason == "late_night_activity"

    def test_create_governance_case_full_fields(self, db_session, sample_run, sample_agent):
        case = GovernanceCase(
            id="case-2",
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            status="warned",
            opened_tick=5,
            last_updated_tick=10,
            primary_reason="noise_complaint",
            severity="medium",
            record_count=3,
            active_restriction_count=1,
            metadata_json={"notes": "multiple warnings issued"},
        )
        db_session.add(case)
        db_session.commit()

        assert case.status == "warned"
        assert case.last_updated_tick == 10
        assert case.severity == "medium"
        assert case.record_count == 3
        assert case.active_restriction_count == 1
        assert case.metadata_json["notes"] == "multiple warnings issued"


class TestGovernanceCaseRepository:
    """Test GovernanceCaseRepository CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_case(self, db_session, governance_case_repo, sample_run, sample_agent):
        case = GovernanceCase(
            id="case-1",
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            status="open",
            opened_tick=0,
            primary_reason="test_reason",
        )
        result = await governance_case_repo.create(case)

        assert result.id == "case-1"
        assert result.status == "open"

    @pytest.mark.asyncio
    async def test_get_case_by_id(self, db_session, governance_case_repo, sample_run, sample_agent):
        case = GovernanceCase(
            id="case-get",
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            status="open",
            opened_tick=0,
            primary_reason="test_reason",
        )
        db_session.add(case)
        await db_session.commit()

        result = await governance_case_repo.get_by_id("case-get")
        assert result is not None
        assert result.id == "case-get"
        assert result.primary_reason == "test_reason"

    @pytest.mark.asyncio
    async def test_get_case_by_id_not_found(self, db_session, governance_case_repo):
        result = await governance_case_repo.get_by_id("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_cases_for_agent(
        self, db_session, governance_case_repo, sample_run, sample_agent
    ):
        for i in range(3):
            case = GovernanceCase(
                id=f"case-list-{i}",
                run_id=sample_run.id,
                agent_id=sample_agent.id,
                status="open",
                opened_tick=i * 10,
                primary_reason=f"reason_{i}",
            )
            db_session.add(case)
        await db_session.commit()

        results = await governance_case_repo.list_for_agent(sample_run.id, sample_agent.id)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_list_cases_for_run(
        self, db_session, governance_case_repo, sample_run, sample_agent
    ):
        for i in range(3):
            case = GovernanceCase(
                id=f"case-run-{i}",
                run_id=sample_run.id,
                agent_id=sample_agent.id,
                status="open",
                opened_tick=i * 10,
                primary_reason=f"reason_{i}",
            )
            db_session.add(case)
        await db_session.commit()

        results = await governance_case_repo.list_for_run(sample_run.id)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_list_open_cases_for_agent(
        self, db_session, governance_case_repo, sample_run, sample_agent
    ):
        # Create 2 open cases and 1 closed
        for status, i in [("open", 0), ("open", 1), ("closed", 2)]:
            case = GovernanceCase(
                id=f"case-status-{i}",
                run_id=sample_run.id,
                agent_id=sample_agent.id,
                status=status,
                opened_tick=i * 10,
                primary_reason=f"reason_{i}",
            )
            db_session.add(case)
        await db_session.commit()

        results = await governance_case_repo.list_open_cases_for_agent(sample_run.id, sample_agent.id)
        assert len(results) == 2
        assert all(c.status == "open" for c in results)

    @pytest.mark.asyncio
    async def test_update_case_status(self, db_session, governance_case_repo, sample_run, sample_agent):
        case = GovernanceCase(
            id="case-update",
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            status="open",
            opened_tick=0,
            primary_reason="test_reason",
            record_count=1,
        )
        db_session.add(case)
        await db_session.commit()

        await governance_case_repo.update_status(
            case_id="case-update",
            new_status="warned",
            record_count=2,
        )

        result = await governance_case_repo.get_by_id("case-update")
        assert result.status == "warned"
        assert result.record_count == 2
        assert result.last_updated_tick == 0  # tick not set in update

    @pytest.mark.asyncio
    async def test_increment_record_count(self, db_session, governance_case_repo, sample_run, sample_agent):
        case = GovernanceCase(
            id="case-increment",
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            status="open",
            opened_tick=0,
            primary_reason="test_reason",
            record_count=1,
        )
        db_session.add(case)
        await db_session.commit()

        await governance_case_repo.increment_record_count("case-increment", tick_no=5)

        result = await governance_case_repo.get_by_id("case-increment")
        assert result.record_count == 2
        assert result.last_updated_tick == 5


class TestGovernanceCaseMerge:
    """Test governance case merge/lookup logic."""

    @pytest.mark.asyncio
    async def test_find_mergeable_case_returns_existing_open(
        self, db_session, governance_case_repo, sample_run, sample_agent
    ):
        """When an open case exists for same agent+reason within window, return it."""
        existing_case = GovernanceCase(
            id="case-existing",
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            status="open",
            opened_tick=5,
            primary_reason="late_night_activity",
        )
        db_session.add(existing_case)
        await db_session.commit()

        mergeable = await governance_case_repo.find_mergeable_case(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            primary_reason="late_night_activity",
            current_tick=10,
            merge_window_ticks=20,
        )

        assert mergeable is not None
        assert mergeable.id == "case-existing"

    @pytest.mark.asyncio
    async def test_find_mergeable_case_returns_none_when_too_old(
        self, db_session, governance_case_repo, sample_run, sample_agent
    ):
        """When existing case is outside merge window, return None."""
        existing_case = GovernanceCase(
            id="case-old",
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            status="open",
            opened_tick=0,
            primary_reason="late_night_activity",
        )
        db_session.add(existing_case)
        await db_session.commit()

        # Current tick 50, merge window 20, case opened at 0 -> outside window
        mergeable = await governance_case_repo.find_mergeable_case(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            primary_reason="late_night_activity",
            current_tick=50,
            merge_window_ticks=20,
        )

        assert mergeable is None

    @pytest.mark.asyncio
    async def test_find_mergeable_case_returns_none_when_closed(
        self, db_session, governance_case_repo, sample_run, sample_agent
    ):
        """When existing case is closed, return None."""
        existing_case = GovernanceCase(
            id="case-closed",
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            status="closed",
            opened_tick=5,
            primary_reason="late_night_activity",
        )
        db_session.add(existing_case)
        await db_session.commit()

        mergeable = await governance_case_repo.find_mergeable_case(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            primary_reason="late_night_activity",
            current_tick=10,
            merge_window_ticks=20,
        )

        assert mergeable is None

    @pytest.mark.asyncio
    async def test_find_mergeable_case_returns_none_when_different_reason(
        self, db_session, governance_case_repo, sample_run, sample_agent
    ):
        """When existing case has different reason, return None."""
        existing_case = GovernanceCase(
            id="case-diff-reason",
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            status="open",
            opened_tick=5,
            primary_reason="noise_complaint",
        )
        db_session.add(existing_case)
        await db_session.commit()

        mergeable = await governance_case_repo.find_mergeable_case(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            primary_reason="late_night_activity",
            current_tick=10,
            merge_window_ticks=20,
        )

        assert mergeable is None

    @pytest.mark.asyncio
    async def test_find_mergeable_case_returns_none_when_different_agent(
        self, db_session, governance_case_repo, sample_run, sample_agent
    ):
        """When existing case belongs to different agent, return None."""
        existing_case = GovernanceCase(
            id="case-diff-agent",
            run_id=sample_run.id,
            agent_id="other-agent",
            status="open",
            opened_tick=5,
            primary_reason="late_night_activity",
        )
        db_session.add(existing_case)
        await db_session.commit()

        mergeable = await governance_case_repo.find_mergeable_case(
            run_id=sample_run.id,
            agent_id=sample_agent.id,
            primary_reason="late_night_activity",
            current_tick=10,
            merge_window_ticks=20,
        )

        assert mergeable is None
