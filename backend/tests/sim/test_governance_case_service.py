"""Tests for governance_case_service."""

from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio

from app.scenario.runtime.world_design_models import GovernanceExecutionResult
from app.sim.action_resolver import ActionResult
from app.sim.governance_case_service import GovernanceCaseService
from app.sim.world import AgentState, WorldState


def _build_world_with_agent(agent_id: str = "alice") -> WorldState:
    return WorldState(
        current_time=datetime(2026, 3, 7, 8, 0, 0),
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


class TestGovernanceCaseServiceProcessRecord:
    """Test processing governance records into cases."""

    @pytest.mark.asyncio
    async def test_process_warn_creates_new_case(self, db_session):
        """When warn decision and no existing case, create new case."""
        service = GovernanceCaseService(db_session)
        world = _build_world_with_agent()
        tick_no = 5
        agent_id = "alice"
        primary_reason = "late_night_activity"

        result = ActionResult(
            accepted=True,
            action_type="move",
            reason="accepted",
            event_payload={"agent_id": agent_id},
            governance_execution=GovernanceExecutionResult(
                decision="warn",
                reason=primary_reason,
                enforcement_action="warning",
            ),
        )

        case = await service.process_governance_record(
            world=world,
            result=result,
            run_id="run-1",
            agent_id=agent_id,
            tick_no=tick_no,
        )

        assert case is not None
        assert case.status == "warned"
        assert case.record_count == 1
        assert case.primary_reason == primary_reason
        assert case.opened_tick == tick_no
        assert case.last_updated_tick == tick_no

    @pytest.mark.asyncio
    async def test_process_warn_merges_into_existing_case(self, db_session):
        """When warn decision and existing open case, merge into it."""
        from app.store.models import GovernanceCase

        # Create existing case
        existing_case = GovernanceCase(
            id=str(uuid4()),
            run_id="run-1",
            agent_id="alice",
            status="open",
            opened_tick=5,
            last_updated_tick=5,
            primary_reason="late_night_activity",
        )
        db_session.add(existing_case)
        await db_session.commit()

        service = GovernanceCaseService(db_session)
        world = _build_world_with_agent()
        tick_no = 10

        result = ActionResult(
            accepted=True,
            action_type="move",
            reason="accepted",
            event_payload={"agent_id": "alice"},
            governance_execution=GovernanceExecutionResult(
                decision="warn",
                reason="late_night_activity",
                enforcement_action="warning",
            ),
        )

        case = await service.process_governance_record(
            world=world,
            result=result,
            run_id="run-1",
            agent_id="alice",
            tick_no=tick_no,
        )

        assert case is not None
        assert case.id == existing_case.id
        # First warn on open case: record_count becomes 1, status stays "open"
        # (warned requires 2+ warns according to doc 6.2)
        assert case.record_count == 1  # Incremented

    @pytest.mark.asyncio
    async def test_process_block_creates_case_with_higher_severity(self, db_session):
        """When block decision, create case with restricted status."""
        service = GovernanceCaseService(db_session)
        world = _build_world_with_agent()
        tick_no = 5
        agent_id = "alice"

        result = ActionResult(
            accepted=False,
            action_type="move",
            reason="location_closed",
            event_payload={"agent_id": agent_id},
            governance_execution=GovernanceExecutionResult(
                decision="block",
                reason="location_closed",
                enforcement_action="intercept",
            ),
        )

        case = await service.process_governance_record(
            world=world,
            result=result,
            run_id="run-1",
            agent_id=agent_id,
            tick_no=tick_no,
        )

        assert case is not None
        assert case.status == "restricted"
        assert case.record_count == 1
        assert case.primary_reason == "location_closed"

    @pytest.mark.asyncio
    async def test_process_record_only_does_not_create_case(self, db_session):
        """When record_only decision, do not create or update case."""
        service = GovernanceCaseService(db_session)
        world = _build_world_with_agent()

        result = ActionResult(
            accepted=True,
            action_type="talk",
            reason="accepted",
            event_payload={"agent_id": "alice"},
            governance_execution=GovernanceExecutionResult(
                decision="record_only",
                reason="soft_risk",
                enforcement_action="record",
            ),
        )

        case = await service.process_governance_record(
            world=world,
            result=result,
            run_id="run-1",
            agent_id="alice",
            tick_no=5,
        )

        # record_only does not create or update case
        assert case is None

    @pytest.mark.asyncio
    async def test_process_allow_does_nothing(self, db_session):
        """When allow decision, do nothing."""
        service = GovernanceCaseService(db_session)
        world = _build_world_with_agent()

        result = ActionResult(
            accepted=True,
            action_type="rest",
            reason="accepted",
            event_payload={"agent_id": "alice"},
            governance_execution=GovernanceExecutionResult(
                decision="allow",
                reason="rest_allowed",
                enforcement_action="none",
            ),
        )

        case = await service.process_governance_record(
            world=world,
            result=result,
            run_id="run-1",
            agent_id="alice",
            tick_no=5,
        )

        assert case is None

    @pytest.mark.asyncio
    async def test_process_multiple_warns_upgrades_to_warned(self, db_session):
        """Multiple warns on same case should upgrade status to warned."""
        from app.store.models import GovernanceCase

        # Create open case
        existing_case = GovernanceCase(
            id=str(uuid4()),
            run_id="run-1",
            agent_id="alice",
            status="open",
            opened_tick=5,
            last_updated_tick=5,
            primary_reason="noise",
        )
        db_session.add(existing_case)
        await db_session.commit()

        service = GovernanceCaseService(db_session)
        world = _build_world_with_agent()

        # First warn: open -> open (record_count: 0 -> 1)
        result1 = ActionResult(
            accepted=True,
            action_type="talk",
            reason="accepted",
            event_payload={"agent_id": "alice"},
            governance_execution=GovernanceExecutionResult(
                decision="warn",
                reason="noise",
                enforcement_action="warning",
            ),
        )
        case1 = await service.process_governance_record(
            world=world,
            result=result1,
            run_id="run-1",
            agent_id="alice",
            tick_no=10,
        )
        assert case1.status == "open"
        assert case1.record_count == 1

        # Second warn: open -> warned (record_count: 1 -> 2)
        result2 = ActionResult(
            accepted=True,
            action_type="talk",
            reason="accepted",
            event_payload={"agent_id": "alice"},
            governance_execution=GovernanceExecutionResult(
                decision="warn",
                reason="noise",
                enforcement_action="warning",
            ),
        )
        case2 = await service.process_governance_record(
            world=world,
            result=result2,
            run_id="run-1",
            agent_id="alice",
            tick_no=15,
        )
        assert case2.status == "warned"
        assert case2.record_count == 2


class TestGovernanceCaseServiceRestrictionGeneration:
    """Test restriction generation from cases."""

    @pytest.mark.asyncio
    async def test_single_block_triggers_work_ban(self, db_session):
        """Single block decision should generate work_ban restriction."""
        service = GovernanceCaseService(db_session)
        world = _build_world_with_agent()
        tick_no = 5
        agent_id = "alice"

        result = ActionResult(
            accepted=False,
            action_type="work",
            reason="governance_block",
            event_payload={"agent_id": agent_id},
            governance_execution=GovernanceExecutionResult(
                decision="block",
                reason="work_violation",
                enforcement_action="intercept",
            ),
        )

        restriction = await service.maybe_create_restriction(
            world=world,
            result=result,
            case=None,
            run_id="run-1",
            agent_id=agent_id,
            tick_no=tick_no,
        )

        assert restriction is not None
        assert restriction.restriction_type == "work_ban"
        assert restriction.status == "active"
        assert restriction.start_tick == tick_no

    @pytest.mark.asyncio
    async def test_sequential_warns_trigger_work_ban(self, db_session):
        """Sequential warns should trigger work_ban restriction."""
        from app.store.models import GovernanceCase

        # Create warned case with 2 record_count
        existing_case = GovernanceCase(
            id=str(uuid4()),
            run_id="run-1",
            agent_id="alice",
            status="warned",
            opened_tick=5,
            last_updated_tick=10,
            primary_reason="noise",
            record_count=2,
        )
        db_session.add(existing_case)
        await db_session.commit()

        service = GovernanceCaseService(db_session)
        world = _build_world_with_agent()
        tick_no = 15

        result = ActionResult(
            accepted=True,
            action_type="talk",
            reason="accepted",
            event_payload={"agent_id": "alice"},
            governance_execution=GovernanceExecutionResult(
                decision="warn",
                reason="noise",
                enforcement_action="warning",
            ),
        )

        restriction = await service.maybe_create_restriction(
            world=world,
            result=result,
            case=existing_case,
            run_id="run-1",
            agent_id="alice",
            tick_no=tick_no,
        )

        assert restriction is not None
        assert restriction.restriction_type == "work_ban"
        assert restriction.end_tick == tick_no + 20  # Default duration

    @pytest.mark.asyncio
    async def test_record_only_no_restriction(self, db_session):
        """record_only decision should not generate restriction."""
        service = GovernanceCaseService(db_session)
        world = _build_world_with_agent()

        result = ActionResult(
            accepted=True,
            action_type="talk",
            reason="accepted",
            event_payload={"agent_id": "alice"},
            governance_execution=GovernanceExecutionResult(
                decision="record_only",
                reason="soft_risk",
                enforcement_action="record",
            ),
        )

        restriction = await service.maybe_create_restriction(
            world=world,
            result=result,
            case=None,
            run_id="run-1",
            agent_id="alice",
            tick_no=5,
        )

        assert restriction is None

    @pytest.mark.asyncio
    async def test_warn_without_case_no_restriction(self, db_session):
        """Warn without case (first warn) should not generate restriction yet."""
        service = GovernanceCaseService(db_session)
        world = _build_world_with_agent()

        result = ActionResult(
            accepted=True,
            action_type="talk",
            reason="accepted",
            event_payload={"agent_id": "alice"},
            governance_execution=GovernanceExecutionResult(
                decision="warn",
                reason="soft_noise",
                enforcement_action="warning",
            ),
        )

        restriction = await service.maybe_create_restriction(
            world=world,
            result=result,
            case=None,  # No case yet
            run_id="run-1",
            agent_id="alice",
            tick_no=5,
        )

        # First warn should not trigger restriction
        assert restriction is None
