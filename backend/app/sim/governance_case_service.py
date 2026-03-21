"""Governance case service - handles case creation, merging, and restriction generation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from app.scenario.runtime.world_design_models import GovernanceExecutionResult
from app.sim.action_resolver import ActionResult
from app.sim.world import WorldState
from app.store.models import GovernanceCase, GovernanceRestriction
from app.store.repositories import GovernanceCaseRepository, GovernanceRestrictionRepository

if TYPE_CHECKING:
    pass


# Default thresholds for restriction generation
DEFAULT_WARN_COUNT_THRESHOLD = 2  # Sequential warns to trigger work_ban
DEFAULT_WORK_BAN_DURATION_TICKS = 20


class GovernanceCaseService:
    """Service for managing governance cases and restrictions."""

    def __init__(self, session) -> None:
        self.session = session
        self.case_repo = GovernanceCaseRepository(session)
        self.restriction_repo = GovernanceRestrictionRepository(session)

    async def process_governance_record(
        self,
        world: WorldState,
        result: ActionResult,
        run_id: str,
        agent_id: str,
        tick_no: int,
    ) -> GovernanceCase | None:
        """Process a governance record and create/update a case if needed.

        Returns:
            The case that was created or updated, or None if no case action needed.
        """
        governance_execution = result.governance_execution
        if governance_execution is None:
            return None

        decision = governance_execution.decision

        # Only warn/block create or update cases
        if decision not in {"warn", "block"}:
            return None

        reason = governance_execution.reason or "unknown"
        case = await self.case_repo.find_mergeable_case(
            run_id=run_id,
            agent_id=agent_id,
            primary_reason=reason,
            current_tick=tick_no,
            merge_window_ticks=50,
        )

        if case is None:
            # Create new case
            case = await self._create_case(
                run_id=run_id,
                agent_id=agent_id,
                tick_no=tick_no,
                reason=reason,
                decision=decision,
            )
        else:
            # Update existing case
            case = await self._update_case(
                case=case,
                decision=decision,
                tick_no=tick_no,
            )

        return case

    async def _create_case(
        self,
        run_id: str,
        agent_id: str,
        tick_no: int,
        reason: str,
        decision: str,
    ) -> GovernanceCase:
        """Create a new governance case."""
        status = "warned" if decision == "warn" else "restricted"
        case = GovernanceCase(
            id=str(uuid4()),
            run_id=run_id,
            agent_id=agent_id,
            status=status,
            opened_tick=tick_no,
            last_updated_tick=tick_no,
            primary_reason=reason,
            severity="medium" if decision == "block" else "low",
            record_count=1,
            active_restriction_count=0,
        )
        return await self.case_repo.create(case)

    async def _update_case(
        self,
        case: GovernanceCase,
        decision: str,
        tick_no: int,
    ) -> GovernanceCase:
        """Update an existing governance case."""
        new_record_count = case.record_count + 1

        # Determine new status based on decision and record count
        if decision == "block":
            new_status = "restricted"
        elif new_record_count >= 2:
            new_status = "warned"
        else:
            new_status = case.status  # Keep current status

        return await self.case_repo.update_status(
            case_id=case.id,
            new_status=new_status,
            record_count=new_record_count,
            last_updated_tick=tick_no,
        )

    async def maybe_create_restriction(
        self,
        world: WorldState,
        result: ActionResult,
        case: GovernanceCase | None,
        run_id: str,
        agent_id: str,
        tick_no: int,
    ) -> GovernanceRestriction | None:
        """Maybe create a restriction based on governance decision and case state.

        Returns:
            The restriction if created, or None if no restriction warranted.
        """
        governance_execution = result.governance_execution
        if governance_execution is None:
            return None

        decision = governance_execution.decision

        # Single block can trigger immediate work_ban
        if decision == "block":
            return await self._create_work_ban(
                run_id=run_id,
                agent_id=agent_id,
                case_id=case.id if case else None,
                tick_no=tick_no,
                reason=governance_execution.reason or "block_violation",
            )

        # Multiple warns on same case can trigger work_ban
        if decision == "warn" and case is not None and case.record_count >= 2:
            return await self._create_work_ban(
                run_id=run_id,
                agent_id=agent_id,
                case_id=case.id,
                tick_no=tick_no,
                reason=f"repeated_warn:{case.primary_reason}",
            )

        return None

    async def _create_work_ban(
        self,
        run_id: str,
        agent_id: str,
        case_id: str | None,
        tick_no: int,
        reason: str,
    ) -> GovernanceRestriction:
        """Create a work_ban restriction."""
        restriction = GovernanceRestriction(
            id=str(uuid4()),
            run_id=run_id,
            agent_id=agent_id,
            case_id=case_id,
            restriction_type="work_ban",
            status="active",
            scope_type="action",
            scope_value="work",
            reason=reason,
            start_tick=tick_no,
            end_tick=tick_no + DEFAULT_WORK_BAN_DURATION_TICKS,
            severity="medium",
        )
        return await self.restriction_repo.create(restriction)
