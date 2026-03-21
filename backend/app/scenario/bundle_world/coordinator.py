from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from app.director.observer import DirectorAssessment, DirectorObserver, DirectorObserverSemantics
from app.director.planner import DirectorPlanner, DirectorPlannerSemantics
from app.director.types import DirectorPlan
from app.infra.logging import get_logger
from app.infra.settings import get_settings
from app.scenario.bundle_world.heuristics import build_bundle_world_decision
from app.scenario.bundle_world.types import (
    BundleWorldGuidance,
    build_bundle_world_guidance,
    merge_bundle_world_agent_profile,
)
from app.scenario.runtime_config import build_scenario_runtime_config
from app.scenario.types import AgentProfile, get_world_role
from app.sim.action_resolver import ActionIntent
from app.sim.context import get_run_world_time
from app.sim.types import RuntimeWorldContext
from app.store.repositories import (
    AgentRepository,
    DirectorMemoryRepository,
    EventRepository,
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

        agents, events = await asyncio.gather(
            self.agent_repo.list_for_run(run_id),
            self.event_repo.list_for_run(run_id, limit=event_limit),
        )

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

        if self.director_memory_repo is not None:
            pending_manual = await self.director_memory_repo.get_pending_manual_interventions(
                run_id=run_id,
                current_tick=run.current_tick,
                max_age_ticks=5,
            )
            if pending_manual:
                memory = pending_manual[0]
                return self._convert_memory_to_plan(memory)

        if not self.settings.director_auto_intervention_enabled:
            return None
        return await self._build_auto_plan(run_id, agents)

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

        (
            previous_subject_alert_score,
            recent_goals,
            recent_interventions,
            raw_events,
        ) = await asyncio.gather(
            _load_subject_alert(),
            _load_goals(),
            _load_interventions(),
            _load_events(),
        )

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
            )
        except Exception as exc:
            logger.warning(f"Director planner failed: {exc}, falling back to rule-based")
            plan = self.planner._build_config_based_plan(
                assessment=assessment,
                support_agents=[
                    a
                    for a in agents
                    if get_world_role(a.profile) in set(self.observer._semantics.support_roles)
                ],
                recent_goals=set(recent_goals),
            )

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
            trigger_subject_alert_score=assessment.subject_alert_score if assessment else 0.0,
            trigger_continuity_risk=assessment.continuity_risk if assessment else "stable",
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

    def merge_agent_profile(self, agent: Agent, plan) -> AgentProfile:
        guidance = {}
        if plan and agent.id in plan.target_agent_ids:
            guidance = build_bundle_world_guidance(
                scene_goal=plan.scene_goal,
                priority=plan.priority,
                message_hint=plan.message_hint,
                target_agent_id=plan.target_agent_id,
                location_hint=plan.location_hint,
                reason=plan.reason,
            )
        return merge_bundle_world_agent_profile(agent.profile or {}, guidance)

    def configure_runtime(self, agent_runtime) -> None:
        agent_runtime.configure_fallback_decision_hook(self.build_runtime_decision)

    def build_runtime_decision(
        self,
        world: RuntimeWorldContext,
        nearby_agent_id: str | None,
        current_location_id: str | None,
        home_location_id: str | None,
        agent_id: str | None = None,
    ):
        return build_bundle_world_decision(
            world=world,
            nearby_agent_id=nearby_agent_id,
            current_location_id=current_location_id,
            home_location_id=home_location_id,
            agent_id=agent_id,
            semantics=self._runtime_role_semantics,
        )

    def fallback_intent(
        self,
        *,
        agent_id: str,
        current_location_id: str,
        home_location_id: str | None,
        nearby_agent_id: str | None,
        world_role: str | None = None,
        current_status: dict | None = None,
        scenario_state: dict | None = None,
        scenario_guidance=None,
    ) -> ActionIntent | None:
        subject_alert_score = float((scenario_state or {}).get("subject_alert_score") or 0.0)
        director_guidance: BundleWorldGuidance = {}
        if scenario_guidance:
            director_guidance = build_bundle_world_guidance(
                scene_goal=scenario_guidance.get("scene_goal")
                or scenario_guidance.get("director_scene_goal"),
                priority=scenario_guidance.get("priority")
                or scenario_guidance.get("director_priority"),
                message_hint=scenario_guidance.get("message_hint")
                or scenario_guidance.get("director_message_hint"),
                target_agent_id=scenario_guidance.get("target_agent_id")
                or scenario_guidance.get("director_target_agent_id"),
                location_hint=scenario_guidance.get("location_hint")
                or scenario_guidance.get("director_location_hint"),
                reason=scenario_guidance.get("reason") or scenario_guidance.get("director_reason"),
            )
        runtime_world: RuntimeWorldContext = {
            "world_role": world_role,
            "self_status": current_status or {},
            "subject_alert_score": subject_alert_score,
            **director_guidance,
        }
        decision = build_bundle_world_decision(
            world=runtime_world,
            nearby_agent_id=nearby_agent_id,
            current_location_id=current_location_id,
            home_location_id=home_location_id,
            semantics=self._runtime_role_semantics,
        )
        if decision is not None:
            payload = dict(decision.payload)
            if decision.message:
                payload["message"] = decision.message
            return ActionIntent(
                agent_id=agent_id,
                action_type=decision.action_type,
                target_location_id=decision.target_location_id,
                target_agent_id=decision.target_agent_id,
                payload=payload,
            )
        return None
