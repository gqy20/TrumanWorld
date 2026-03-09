from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agent.providers import HeuristicDecisionProvider
from app.director.observer import DirectorAssessment, DirectorObserver
from app.director.planner import DirectorPlanner
from app.director.types import DirectorPlan
from app.infra.logging import get_logger
from app.scenario.truman_world.heuristics import build_truman_world_decision
from app.scenario.truman_world.types import (
    DirectorGuidance,
    ScenarioAgentProfile,
    build_director_guidance,
    merge_scenario_agent_profile,
)
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


class TrumanWorldCoordinator:
    """Coordinates Truman-world specific director and fallback behavior."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.run_repo = RunRepository(session) if session is not None else None
        self.agent_repo = AgentRepository(session) if session is not None else None
        self.event_repo = EventRepository(session) if session is not None else None
        self.director_memory_repo = (
            DirectorMemoryRepository(session) if session is not None else None
        )
        self.observer = DirectorObserver()
        self.planner = DirectorPlanner()

    async def observe_run(self, run_id: str, event_limit: int = 20) -> DirectorAssessment:
        if self.run_repo is None or self.agent_repo is None or self.event_repo is None:
            msg = "TrumanWorldCoordinator.observe_run requires a database session"
            raise RuntimeError(msg)
        run = await self.run_repo.get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)

        agents = await self.agent_repo.list_for_run(run_id)
        events = await self.event_repo.list_for_run(run_id, limit=event_limit)

        # 获取上一次的怀疑度用于趋势计算
        previous_suspicion_score = 0.0
        if self.director_memory_repo is not None:
            previous_suspicion_score = await self.director_memory_repo.get_latest_suspicion_score(
                run_id
            )

        return self.assess(
            run_id=run_id,
            current_tick=run.current_tick,
            agents=agents,
            events=events,
            previous_suspicion_score=previous_suspicion_score,
        )

    async def build_director_plan(self, run_id: str, agents: list[Agent]) -> DirectorPlan | None:
        """构建导演干预计划 - 优先使用手动注入，其次自动触发"""
        if self.run_repo is None:
            msg = "TrumanWorldCoordinator.build_director_plan requires a database session"
            raise RuntimeError(msg)

        run = await self.run_repo.get(run_id)
        if run is None:
            return None

        # 1. 优先检查是否有未执行的手动注入计划
        if self.director_memory_repo is not None:
            pending_manual = await self.director_memory_repo.get_pending_manual_interventions(
                run_id=run_id,
                current_tick=run.current_tick,
                max_age_ticks=5,
            )
            if pending_manual:
                # 将最新的手动计划转换为 DirectorPlan
                memory = pending_manual[0]
                await self.director_memory_repo.mark_executed(memory.id)
                return self._convert_memory_to_plan(memory)

        # 2. 没有手动计划时，走自动逻辑
        return await self._build_auto_plan(run_id, agents)

    async def _build_auto_plan(self, run_id: str, agents: list[Agent]) -> DirectorPlan | None:
        """构建自动导演干预计划"""
        run = await self.run_repo.get(run_id)
        if run is None:
            return None

        assessment = await self.observe_run(run_id)

        # 获取最近的干预目标，避免重复
        recent_goals: list[str] = []
        recent_interventions: list[dict[str, Any]] = []
        if self.director_memory_repo is not None:
            recent_goals = await self.director_memory_repo.get_recent_goals(
                run_id=run_id,
                current_tick=run.current_tick,
                lookback_ticks=10,
            )
            # 获取最近干预记录用于智能决策
            recent_memories = await self.director_memory_repo.list_for_run(run_id, limit=10)
            recent_interventions = [
                {
                    "tick_no": m.tick_no,
                    "scene_goal": m.scene_goal,
                    "reason": m.reason,
                    "was_executed": m.was_executed,
                }
                for m in recent_memories
            ]

        # 获取最近事件用于智能决策
        recent_events: list[dict[str, Any]] = []
        if self.event_repo is not None:
            events = await self.event_repo.list_for_run(run_id, limit=20)
            recent_events = [
                {
                    "tick_no": e.tick_no,
                    "event_type": e.event_type,
                    "description": str(e.payload)[:100] if e.payload else "N/A",
                }
                for e in events
            ]

        # 获取世界时间
        world_time = get_run_world_time(run).isoformat()

        # 构建自动计划（支持智能决策）
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
            # 如果智能决策失败，回退到纯规则决策
            plan = self.planner._build_config_based_plan(
                assessment=assessment,
                cast_agents=[a for a in agents if self._get_world_role(a) == "cast"],
                recent_goals=set(recent_goals),
            )

        # 保存新的自动干预计划到记忆
        if plan is not None and self.director_memory_repo is not None:
            await self.director_memory_repo.create(
                run_id=run_id,
                tick_no=run.current_tick,
                scene_goal=plan.scene_goal,
                target_cast_ids=plan.target_cast_ids,
                priority=plan.priority,
                urgency=plan.urgency,
                message_hint=plan.message_hint,
                target_agent_id=plan.target_agent_id,
                reason=plan.reason,
                trigger_suspicion_score=assessment.truman_suspicion_score,
                trigger_continuity_risk=assessment.continuity_risk,
                cooldown_ticks=plan.cooldown_ticks,
            )
            if plan.is_intelligent_decision:
                logger.info(
                    f"Saved intelligent director plan at tick {run.current_tick}: "
                    f"{plan.scene_goal} with strategy: {plan.strategy}"
                )

        return plan

    def _get_world_role(self, agent: Agent) -> str:
        """Get world role from agent profile."""
        from app.scenario.truman_world.types import get_world_role
        return get_world_role(agent.profile)

    def _convert_memory_to_plan(self, memory) -> DirectorPlan:
        """将 DirectorMemory 转换为 DirectorPlan"""
        import json

        target_cast_ids = json.loads(memory.target_cast_ids) if memory.target_cast_ids else []

        # location_hint 可能存储在 metadata_json 中（手动注入时）
        location_hint = None
        if hasattr(memory, "location_hint") and memory.location_hint:
            location_hint = memory.location_hint
        elif memory.metadata_json and "location_hint" in memory.metadata_json:
            location_hint = memory.metadata_json["location_hint"]

        return DirectorPlan(
            scene_goal=memory.scene_goal,
            target_cast_ids=target_cast_ids,
            priority=memory.priority,
            urgency=memory.urgency,
            message_hint=memory.message_hint,
            location_hint=location_hint,
            target_agent_id=memory.target_agent_id,
            reason=memory.reason,
            cooldown_ticks=memory.cooldown_ticks,
        )

    def assess(
        self,
        *,
        run_id: str,
        current_tick: int,
        agents: list[Agent],
        events: list[Event],
        previous_suspicion_score: float = 0.0,
    ) -> DirectorAssessment:
        return self.observer.assess(
            run_id=run_id,
            current_tick=current_tick,
            agents=list(agents),
            events=list(events),
            previous_suspicion_score=previous_suspicion_score,
        )

    def merge_agent_profile(self, agent: Agent, plan) -> ScenarioAgentProfile:
        guidance = {}
        if plan and agent.id in plan.target_cast_ids:
            guidance = build_director_guidance(
                scene_goal=plan.scene_goal,
                priority=plan.priority,
                message_hint=plan.message_hint,
                target_agent_id=plan.target_agent_id,
                location_hint=plan.location_hint,
                reason=plan.reason,
            )
        return merge_scenario_agent_profile(agent.profile or {}, guidance)

    def configure_runtime(self, agent_runtime) -> None:
        provider = getattr(agent_runtime, "decision_provider", None)
        if isinstance(provider, HeuristicDecisionProvider):
            provider.set_decision_hook(self.build_runtime_decision)

    def build_runtime_decision(
        self,
        world: RuntimeWorldContext,
        nearby_agent_id: str | None,
        current_location_id: str | None,
        home_location_id: str | None,
        agent_id: str | None = None,
    ):
        return build_truman_world_decision(
            world=world,
            nearby_agent_id=nearby_agent_id,
            current_location_id=current_location_id,
            home_location_id=home_location_id,
            agent_id=agent_id,
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
        truman_suspicion_score: float = 0.0,
        director_guidance: DirectorGuidance | None = None,
    ) -> ActionIntent | None:
        guidance = director_guidance or {}
        runtime_world: RuntimeWorldContext = {
            "world_role": world_role,
            "self_status": current_status or {},
            "truman_suspicion_score": truman_suspicion_score,
            **guidance,
        }
        decision = build_truman_world_decision(
            world=runtime_world,
            nearby_agent_id=nearby_agent_id,
            current_location_id=current_location_id,
            home_location_id=home_location_id,
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
