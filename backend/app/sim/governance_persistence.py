from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.sim.governance_case_service import GovernanceCaseService
from app.sim.runner import TickResult
from app.sim.world import RestrictionState, WorldState
from app.store.models import Event, GovernanceRecord
from app.store.repositories import GovernanceRecordRepository


class GovernancePersistence:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.governance_record_repo = GovernanceRecordRepository(session)

    async def persist_tick_governance_records(
        self,
        run_id: str,
        events: list[Event],
    ) -> None:
        records: list[GovernanceRecord] = []
        for event in events:
            payload = event.payload or {}
            governance_execution = payload.get("governance_execution")
            if not isinstance(governance_execution, dict):
                continue
            decision = governance_execution.get("decision")
            if decision not in {"record_only", "warn", "block"}:
                continue

            agent_id = payload.get("agent_id") or event.actor_agent_id
            if not isinstance(agent_id, str) or not agent_id:
                continue

            reason = governance_execution.get("reason")
            observation_score = governance_execution.get("observation_score")
            intervention_score = governance_execution.get("intervention_score")
            observed = governance_execution.get("observed")
            matched_signals = governance_execution.get("matched_signals")

            records.append(
                GovernanceRecord(
                    id=str(uuid4()),
                    run_id=run_id,
                    agent_id=agent_id,
                    tick_no=event.tick_no,
                    source_event_id=event.id,
                    location_id=event.location_id,
                    action_type=event.event_type,
                    decision=decision,
                    reason=reason if isinstance(reason, str) else None,
                    observed=bool(observed),
                    observation_score=(
                        float(observation_score)
                        if isinstance(observation_score, (int, float))
                        else 0.0
                    ),
                    intervention_score=(
                        float(intervention_score)
                        if isinstance(intervention_score, (int, float))
                        else 0.0
                    ),
                    metadata_json={
                        "enforcement_action": governance_execution.get("enforcement_action"),
                        "matched_signals": matched_signals
                        if isinstance(matched_signals, list)
                        else [],
                    },
                )
            )

        if records:
            await self.governance_record_repo.add_many(records)

    async def persist_tick_governance_cases(
        self,
        run_id: str,
        result: TickResult,
        world: WorldState,
    ) -> None:
        """Persist governance cases and restrictions from tick results."""
        service = GovernanceCaseService(self.session, commit_changes=False)

        for item in [*result.accepted, *result.rejected]:
            governance_execution = item.governance_execution
            if governance_execution is None:
                continue

            decision = governance_execution.decision
            if decision not in {"warn", "block"}:
                continue

            agent_id = item.event_payload.get("agent_id")
            if not isinstance(agent_id, str) or not agent_id:
                continue

            case = await service.process_governance_record(
                world=world,
                result=item,
                run_id=run_id,
                agent_id=agent_id,
                tick_no=result.tick_no,
            )

            restriction = await service.maybe_create_restriction(
                world=world,
                result=item,
                case=case,
                run_id=run_id,
                agent_id=agent_id,
                tick_no=result.tick_no,
            )

            if restriction is not None:
                world.add_restriction(
                    agent_id,
                    RestrictionState(
                        id=restriction.id,
                        restriction_type=restriction.restriction_type,
                        scope_type=restriction.scope_type,
                        scope_value=restriction.scope_value,
                        start_tick=restriction.start_tick,
                        end_tick=restriction.end_tick,
                        reason=restriction.reason,
                    ),
                )
