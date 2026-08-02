from __future__ import annotations

# ruff: noqa: F403,F405
from app.store.repository_modules._common import *

from app.director.directives import DirectorDirective as DirectiveDTO
from app.infra.metrics import observe_director_directive
from app.sim.action_resolver import ActionResult
from app.store.models import DirectorDirective


class DirectorDirectiveRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(self, directives: list[DirectiveDTO]) -> None:
        if directives:
            await self._cancel_superseded(directives)
        for directive in directives:
            await self.session.merge(
                DirectorDirective(
                    id=directive.id,
                    run_id=directive.run_id,
                    target_agent_id=directive.target_agent_id,
                    subject_agent_id=directive.subject_agent_id,
                    objective=directive.objective,
                    mode=directive.mode,
                    priority=directive.priority,
                    status="active",
                    issued_tick=directive.issued_tick,
                    expires_at_tick=directive.expires_at_tick,
                    location_id=directive.location_id,
                    message_hint=directive.message_hint,
                    constraints_json=directive.constraints,
                    completion_criteria_json=directive.completion_criteria,
                    source=directive.source,
                    source_memory_id=directive.source_memory_id,
                    attempt_count=directive.attempt_count,
                    last_attempt_tick=directive.last_attempt_tick,
                    last_progress_tick=directive.last_progress_tick,
                )
            )

    async def list_active(self, run_id: str, tick_no: int) -> Sequence[DirectorDirective]:
        stmt = (
            select(DirectorDirective)
            .where(
                DirectorDirective.run_id == run_id,
                DirectorDirective.status.in_(("pending", "active")),
                DirectorDirective.expires_at_tick >= tick_no,
            )
            .order_by(DirectorDirective.issued_tick.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> Sequence[DirectorDirective]:
        stmt = select(DirectorDirective).where(DirectorDirective.run_id == run_id)
        if status is not None:
            stmt = stmt.where(DirectorDirective.status == status)
        if agent_id is not None:
            stmt = stmt.where(DirectorDirective.target_agent_id == agent_id)
        result = await self.session.execute(
            stmt.order_by(
                DirectorDirective.issued_tick.desc(), DirectorDirective.created_at.desc()
            ).limit(limit)
        )
        return result.scalars().all()

    async def get_for_run(self, run_id: str, directive_id: str) -> DirectorDirective | None:
        stmt = select(DirectorDirective).where(
            DirectorDirective.run_id == run_id,
            DirectorDirective.id == directive_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def expire_stale(self, run_id: str, tick_no: int) -> None:
        stmt = select(DirectorDirective).where(
            DirectorDirective.run_id == run_id,
            DirectorDirective.status.in_(("pending", "active")),
            DirectorDirective.expires_at_tick < tick_no,
        )
        directives = (await self.session.execute(stmt)).scalars().all()
        for directive in directives:
            directive.status = "expired"
            directive.failure_reason = "deadline_exceeded"
            directive.effect_status = "evaluated"
            directive.effectiveness_score = 0.0
            directive.evaluated_tick = tick_no
            observe_director_directive(outcome="expired", mode=directive.mode)
        await self._refresh_memory_effectiveness(list(directives))

    async def apply_results(
        self, run_id: str, tick_no: int, results: Sequence[ActionResult]
    ) -> None:
        by_id = {
            result.event_payload.get("director_directive_id"): result
            for result in results
            if result.event_payload.get("director_directive_id")
        }
        if not by_id:
            return
        stmt = select(DirectorDirective).where(
            DirectorDirective.run_id == run_id,
            DirectorDirective.id.in_(by_id),
        )
        directives = (await self.session.execute(stmt)).scalars().all()
        for directive in directives:
            result = by_id[directive.id]
            first_response = directive.attempt_count == 0
            directive.attempt_count += 1
            directive.last_attempt_tick = tick_no
            directive.last_result_action_type = result.action_type
            directive.last_result_target_agent_id = result.event_payload.get("target_agent_id")
            directive.disposition = result.event_payload.get("director_disposition")
            if result.accepted and _matches_completion(directive, result):
                directive.status = "executed"
                directive.completed_tick = tick_no
                directive.last_progress_tick = tick_no
                directive.failure_reason = None
                directive.effect_status = "pending"
                await self._update_memory(directive)
                observe_director_directive(outcome="executed", mode=directive.mode)
            elif result.accepted:
                await self._update_memory(directive)
                if directive.attempt_count == 2 and directive.mode == "advisory":
                    directive.mode = "priority"
                    directive.priority = "high"
                    directive.constraints_json = {
                        **(directive.constraints_json or {}),
                        "mode": "priority",
                    }
                    directive.failure_reason = "progress_stalled_escalated"
                    observe_director_directive(outcome="escalated", mode="priority")
                elif directive.attempt_count >= 3:
                    directive.status = "failed"
                    directive.failure_reason = "target_drift"
                    observe_director_directive(outcome="target_drift", mode=directive.mode)
            elif not result.accepted:
                directive.status = "failed"
                directive.failure_reason = result.reason
                directive.effect_status = "evaluated"
                directive.effectiveness_score = 0.0
                directive.evaluated_tick = tick_no
                observe_director_directive(outcome="rejected", mode=directive.mode)
            if first_response:
                observe_director_directive(
                    outcome="acknowledged",
                    mode=directive.mode,
                    response_ticks=tick_no - directive.issued_tick,
                )
        await self._refresh_memory_effectiveness(list(directives))

    async def evaluate_effects(
        self,
        run_id: str,
        tick_no: int,
        agents: Sequence[Agent],
        *,
        alert_metric: str = "truman_suspicion_score",
    ) -> None:
        stmt = select(DirectorDirective).where(
            DirectorDirective.run_id == run_id,
            DirectorDirective.status == "executed",
            DirectorDirective.effect_status == "pending",
            DirectorDirective.completed_tick < tick_no,
        )
        directives = list((await self.session.execute(stmt)).scalars().all())
        if not directives:
            return
        agent_by_id = {agent.id: agent for agent in agents}
        for directive in directives:
            memory = (
                await self.session.get(DirectorMemory, directive.source_memory_id)
                if directive.source_memory_id
                else None
            )
            score = _evaluate_effect_score(
                directive, memory, agent_by_id, alert_metric=alert_metric
            )
            directive.effect_status = "evaluated"
            directive.effectiveness_score = score
            directive.evaluated_tick = tick_no
            directive.status = "succeeded" if score >= 0.5 else "failed"
            directive.failure_reason = None if score >= 0.5 else "effect_not_achieved"
            observe_director_directive(
                outcome="effect_achieved" if score >= 0.5 else "effect_missed",
                mode=directive.mode,
            )
        await self._refresh_memory_effectiveness(directives)

    async def _refresh_memory_effectiveness(self, directives: list[DirectorDirective]) -> None:
        memory_ids = {item.source_memory_id for item in directives if item.source_memory_id}
        for memory_id in memory_ids:
            stmt = select(
                DirectorDirective.effect_status,
                DirectorDirective.effectiveness_score,
            ).where(DirectorDirective.source_memory_id == memory_id)
            rows = list((await self.session.execute(stmt)).all())
            memory = await self.session.get(DirectorMemory, memory_id)
            if memory is None:
                continue
            if not rows or any(status != "evaluated" for status, _score in rows):
                memory.effectiveness_score = None
                continue
            scores = [score for _status, score in rows if score is not None]
            memory.effectiveness_score = sum(scores) / len(scores) if scores else None

    async def list_needing_replan(self, run_id: str) -> Sequence[DirectorDirective]:
        stmt = select(DirectorDirective).where(
            DirectorDirective.run_id == run_id,
            DirectorDirective.status == "failed",
            DirectorDirective.failure_reason == "target_drift",
            DirectorDirective.replaced_by_directive_id.is_(None),
        )
        result = await self.session.execute(
            stmt.order_by(DirectorDirective.last_attempt_tick.desc()).limit(10)
        )
        return result.scalars().all()

    async def mark_replanned(self, directive_ids: list[str], replacement_directive_id: str) -> None:
        if not directive_ids:
            return
        stmt = select(DirectorDirective).where(DirectorDirective.id.in_(directive_ids))
        directives = (await self.session.execute(stmt)).scalars().all()
        for directive in directives:
            directive.replaced_by_directive_id = replacement_directive_id
            directive.failure_reason = "replanned"
            observe_director_directive(outcome="replanned", mode=directive.mode)

    async def _update_memory(self, directive: DirectorDirective) -> None:
        if not directive.source_memory_id:
            return
        memory = await self.session.get(DirectorMemory, directive.source_memory_id)
        if memory is None:
            return
        memory.was_executed = True

    async def _cancel_superseded(self, directives: list[DirectiveDTO]) -> None:
        run_id = directives[0].run_id
        target_agent_ids = {directive.target_agent_id for directive in directives}
        incoming_ids = {directive.id for directive in directives}
        stmt = select(DirectorDirective).where(
            DirectorDirective.run_id == run_id,
            DirectorDirective.target_agent_id.in_(target_agent_ids),
            DirectorDirective.status.in_(("pending", "active")),
            DirectorDirective.id.not_in(incoming_ids),
        )
        existing = (await self.session.execute(stmt)).scalars().all()
        for directive in existing:
            directive.status = "cancelled"
            directive.failure_reason = "superseded"


def _matches_completion(directive: DirectorDirective, result: ActionResult) -> bool:
    criteria = directive.completion_criteria_json or {}
    if criteria.get("accepted_action"):
        return result.accepted
    if directive.objective in {"gather", "activity"} and not directive.location_id:
        return result.accepted
    action_type = criteria.get("action_type")
    if action_type and action_type != result.action_type:
        return False
    target_agent_id = criteria.get("target_agent_id")
    if target_agent_id and target_agent_id != result.event_payload.get("target_agent_id"):
        return False
    target_location_id = criteria.get("target_location_id")
    if target_location_id and target_location_id not in {
        result.event_payload.get("target_location_id"),
        result.event_payload.get("location_id"),
    }:
        return False
    return True


def _evaluate_effect_score(
    directive: DirectorDirective,
    memory: DirectorMemory | None,
    agent_by_id: dict[str, Agent],
    *,
    alert_metric: str,
) -> float:
    actor = agent_by_id.get(directive.target_agent_id)
    subject = agent_by_id.get(directive.subject_agent_id) if directive.subject_agent_id else None
    if directive.location_id and actor is not None:
        return 1.0 if actor.current_location_id == directive.location_id else 0.0
    if directive.objective in {"shutdown", "weather_change", "power_outage"}:
        return 1.0
    alert_objectives = {
        "soft_check_in",
        "preemptive_comfort",
        "break_isolation",
        "rejection_recovery",
        "keep_scene_natural",
    }
    if directive.objective not in alert_objectives:
        return 0.5
    if subject is None or memory is None:
        return 0.5
    status = subject.status or {}
    current_alert = float(status.get(alert_metric, 0.0) or 0.0)
    alert_delta = current_alert - float(memory.trigger_subject_alert_score or 0.0)
    if alert_delta <= -0.05:
        return 1.0
    if alert_delta <= 0:
        return 0.6
    if alert_delta < 0.1:
        return 0.25
    return 0.0
