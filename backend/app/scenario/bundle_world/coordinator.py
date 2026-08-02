from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from app.cognition.types import BackendExecutionContext
from app.director.directives import DirectorDirective, compile_directives
from app.director.observer import DirectorAssessment, DirectorObserver, DirectorObserverSemantics
from app.director.planner import DirectorPlanner, DirectorPlannerSemantics
from app.director.types import DirectorPlan
from app.infra.logging import get_logger
from app.infra.settings import get_settings
from app.scenario.runtime_config import build_scenario_runtime_config
from app.scenario.types import get_world_role
from app.sim.context import get_run_world_time
from app.sim.llm_call_collector import LlmCallCollector
from app.sim.llm_call_writer import LlmCallWriter
from app.store.repositories import (
    AgentRepository,
    DirectorDirectiveRepository,
    DirectorMemoryRepository,
    EventRepository,
    LocationRepository,
    RunRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.store.models import Agent, Event

logger = get_logger(__name__)


class BundleWorldCoordinator:
    def __init__(
        self,
        session: AsyncSession | None = None,
        *,
        scenario_id: str = "narrative_world",
    ) -> None:
        self.session = session
        self.scenario_id = scenario_id
        self.run_repo = RunRepository(session) if session is not None else None
        self.agent_repo = AgentRepository(session) if session is not None else None
        self.event_repo = EventRepository(session) if session is not None else None
        self.director_memory_repo = (
            DirectorMemoryRepository(session) if session is not None else None
        )
        self.director_directive_repo = (
            DirectorDirectiveRepository(session) if session is not None else None
        )
        self.location_repo = LocationRepository(session) if session is not None else None
        self._runtime_role_semantics = build_scenario_runtime_config(scenario_id)
        self.observer = DirectorObserver(
            DirectorObserverSemantics(
                subject_role=self._runtime_role_semantics.subject_role,
                support_roles=self._runtime_role_semantics.support_roles,
                alert_metric=self._runtime_role_semantics.alert_metric,
                subject_alert_tracking=self._runtime_role_semantics.subject_alert_tracking,
            )
        )
        self.planner = DirectorPlanner(
            scenario_id=scenario_id,
            semantics=DirectorPlannerSemantics(
                subject_role=self._runtime_role_semantics.subject_role,
                support_roles=self._runtime_role_semantics.support_roles,
                alert_metric=self._runtime_role_semantics.alert_metric,
                subject_alert_tracking=self._runtime_role_semantics.subject_alert_tracking,
            ),
        )
        self.settings = get_settings()

    async def observe_run(self, run_id: str, event_limit: int = 20) -> DirectorAssessment:
        if self.run_repo is None or self.agent_repo is None or self.event_repo is None:
            msg = "BundleWorldCoordinator.observe_run requires a database session"
            raise RuntimeError(msg)
        run = await self.run_repo.get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)

        agents = await self.agent_repo.list_for_run(run_id)
        events = await self.event_repo.list_for_run(run_id, limit=event_limit)

        previous_subject_alert_score = 0.0
        if self.director_memory_repo is not None:
            previous_subject_alert_score = (
                await self.director_memory_repo.get_latest_subject_alert_score(run_id)
            )

        return self.assess(
            run_id=run_id,
            current_tick=run.current_tick,
            agents=agents,
            events=events,
            previous_subject_alert_score=previous_subject_alert_score,
        )

    async def build_director_plan(self, run_id: str, agents: list[Agent]) -> DirectorPlan | None:
        if self.run_repo is None:
            msg = "BundleWorldCoordinator.build_director_plan requires a database session"
            raise RuntimeError(msg)

        run = await self.run_repo.get(run_id)
        if run is None:
            return None

        active_directives = await self._load_active_directives(run_id, run.current_tick)

        if self.director_memory_repo is not None:
            pending_manual = await self.director_memory_repo.get_pending_manual_interventions(
                run_id=run_id,
                current_tick=run.current_tick,
                max_age_ticks=5,
            )
            if pending_manual:
                memory = pending_manual[0]
                return await self._attach_directives(
                    self._convert_memory_to_plan(memory), run_id, run.current_tick, agents
                )

        if not self.settings.director_auto_intervention_enabled:
            return self._plan_from_active(active_directives)
        plan = await self._build_auto_plan(run_id, agents)
        if plan is None:
            return self._plan_from_active(active_directives)
        return await self._attach_directives(plan, run_id, run.current_tick, agents)

    async def _attach_directives(
        self,
        plan: DirectorPlan,
        run_id: str,
        tick_no: int,
        agents: list[Agent],
    ) -> DirectorPlan:
        locations = await self.location_repo.list_for_run(run_id) if self.location_repo else []
        plan.directives = compile_directives(
            plan,
            run_id=run_id,
            issued_tick=tick_no,
            valid_agent_ids={agent.id for agent in agents},
            valid_location_ids={location.id for location in locations},
        )
        return plan

    async def _load_active_directives(self, run_id: str, tick_no: int) -> list[DirectorDirective]:
        if self.director_directive_repo is None:
            return []
        rows = await self.director_directive_repo.list_active(run_id, tick_no)
        return [
            DirectorDirective(
                id=row.id,
                run_id=row.run_id,
                target_agent_id=row.target_agent_id,
                subject_agent_id=row.subject_agent_id,
                objective=row.objective,
                mode=row.mode,
                priority=row.priority,
                issued_tick=row.issued_tick,
                expires_at_tick=row.expires_at_tick,
                location_id=row.location_id,
                message_hint=row.message_hint,
                constraints=dict(row.constraints_json or {}),
                completion_criteria=dict(row.completion_criteria_json or {}),
                source=row.source,
            )
            for row in rows
        ]

    @staticmethod
    def _plan_from_active(directives: list[DirectorDirective]) -> DirectorPlan | None:
        if not directives:
            return None
        primary = directives[0]
        return DirectorPlan(
            scene_goal=primary.objective,
            target_agent_ids=[directive.target_agent_id for directive in directives],
            priority=primary.priority,
            urgency="immediate" if primary.mode == "priority" else "advisory",
            message_hint=primary.message_hint,
            location_hint=primary.location_id,
            target_agent_id=primary.subject_agent_id,
            source_type="active",
            directives=directives,
        )

    async def _build_auto_plan(self, run_id: str, agents: list[Agent]) -> DirectorPlan | None:
        run = await self.run_repo.get(run_id)
        if run is None:
            return None

        async def _load_subject_alert() -> float:
            if self.director_memory_repo is not None:
                return await self.director_memory_repo.get_latest_subject_alert_score(run_id)
            return 0.0

        async def _load_goals() -> list[str]:
            if self.director_memory_repo is not None:
                return await self.director_memory_repo.get_recent_goals(
                    run_id=run_id,
                    current_tick=run.current_tick,
                    lookback_ticks=10,
                )
            return []

        async def _load_interventions() -> list[dict[str, Any]]:
            if self.director_memory_repo is not None:
                recent_memories = await self.director_memory_repo.list_for_run(run_id, limit=10)
                return [
                    {
                        "tick_no": m.tick_no,
                        "scene_goal": m.scene_goal,
                        "reason": m.reason,
                        "was_executed": m.was_executed,
                    }
                    for m in recent_memories
                ]
            return []

        async def _load_events() -> list[Any]:
            if self.event_repo is not None:
                return await self.event_repo.list_for_run(run_id, limit=20)
            return []

        previous_subject_alert_score = await _load_subject_alert()
        recent_goals = await _load_goals()
        recent_interventions = await _load_interventions()
        raw_events = await _load_events()

        assessment = self.observer.assess(
            run_id=run_id,
            current_tick=run.current_tick,
            agents=agents,
            events=list(raw_events),
            previous_subject_alert_score=previous_subject_alert_score,
        )

        recent_events: list[dict[str, Any]] = [
            {
                "tick_no": e.tick_no,
                "event_type": e.event_type,
                "description": str(e.payload)[:100] if e.payload else "N/A",
            }
            for e in raw_events
        ]

        world_time = get_run_world_time(run).isoformat()
        llm_collector = LlmCallCollector()
        director_model = self.settings.director_agent_model or self.settings.llm_model
        runtime_ctx = BackendExecutionContext(
            run_id=run_id,
            tick_no=run.current_tick,
            on_llm_call=llm_collector.build_callback(
                run_id=run_id,
                db_agent_id=None,
                tick_no=run.current_tick,
                provider=self.settings.llm_provider,
                model=director_model,
                backend=self.settings.director_backend,
            ),
        )

        try:
            plan = await self.planner.build_plan(
                assessment=assessment,
                agents=list(agents),
                recent_intervention_goals=recent_goals,
                current_tick=run.current_tick,
                recent_events=recent_events,
                recent_interventions=recent_interventions,
                world_time=world_time,
                run_id=run_id,
                runtime_ctx=runtime_ctx,
            )
        except Exception as exc:
            logger.warning(
                "Director planner failed; falling back to rule-based planning",
                extra={
                    "event": "director_planner_fallback",
                    "simulation_run_id": run_id,
                    "tick_no": run.current_tick,
                    "backend": self.settings.director_backend,
                    "exception_type": type(exc).__name__,
                    "fallback_to": "rule_based",
                },
            )
            plan = self.planner._build_config_based_plan(
                assessment=assessment,
                support_agents=[
                    a
                    for a in agents
                    if get_world_role(a.profile) in set(self.observer._semantics.support_roles)
                ],
                recent_goals=set(recent_goals),
            )
        finally:
            await LlmCallWriter().persist(
                run_id=run_id,
                llm_records=llm_collector.records,
                engine=self.session.bind if self.session is not None else None,
            )

        if plan is not None:
            plan.trigger_subject_alert_score = assessment.subject_alert_score
            plan.trigger_continuity_risk = assessment.continuity_risk
        return plan

    async def persist_director_plan(
        self,
        run_id: str,
        plan: DirectorPlan,
        assessment: DirectorAssessment | None = None,
    ) -> None:
        if self.director_memory_repo is None:
            return
        run = await self.run_repo.get(run_id) if self.run_repo is not None else None
        tick_no = run.current_tick if run is not None else 0
        if plan.source_type == "active":
            return
        if self.director_directive_repo is not None:
            await self.director_directive_repo.add_many(plan.directives)
        if plan.source_type == "manual" and plan.source_memory_id:
            await self.director_memory_repo.mark_executed(plan.source_memory_id)
            return
        await self.director_memory_repo.create(
            run_id=run_id,
            tick_no=tick_no,
            scene_goal=plan.scene_goal,
            target_agent_ids=plan.target_agent_ids,
            priority=plan.priority,
            urgency=plan.urgency,
            message_hint=plan.message_hint,
            target_agent_id=plan.target_agent_id,
            reason=plan.reason,
            trigger_subject_alert_score=(
                assessment.subject_alert_score if assessment else plan.trigger_subject_alert_score
            ),
            trigger_continuity_risk=(
                assessment.continuity_risk if assessment else plan.trigger_continuity_risk
            ),
            cooldown_ticks=plan.cooldown_ticks,
        )
        if plan.is_intelligent_decision:
            logger.info(
                f"Saved intelligent director plan at tick {tick_no}: "
                f"{plan.scene_goal} with strategy: {plan.strategy}"
            )

    def _convert_memory_to_plan(self, memory) -> DirectorPlan:
        target_agent_ids = json.loads(memory.target_agent_ids) if memory.target_agent_ids else []

        location_hint = None
        if hasattr(memory, "location_hint") and memory.location_hint:
            location_hint = memory.location_hint
        elif memory.metadata_json and "location_hint" in memory.metadata_json:
            location_hint = memory.metadata_json["location_hint"]

        return DirectorPlan(
            scene_goal=memory.scene_goal,
            target_agent_ids=target_agent_ids,
            priority=memory.priority,
            urgency=memory.urgency,
            message_hint=memory.message_hint,
            location_hint=location_hint,
            target_agent_id=memory.target_agent_id,
            reason=memory.reason,
            cooldown_ticks=memory.cooldown_ticks,
            source_type="manual",
            source_memory_id=memory.id,
        )

    def assess(
        self,
        *,
        run_id: str,
        current_tick: int,
        agents: list[Agent],
        events: list[Event],
        previous_subject_alert_score: float = 0.0,
    ) -> DirectorAssessment:
        return self.observer.assess(
            run_id=run_id,
            current_tick=current_tick,
            agents=list(agents),
            events=list(events),
            previous_subject_alert_score=previous_subject_alert_score,
        )
