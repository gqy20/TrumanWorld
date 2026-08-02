from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.cognition.claude.director_agent import DirectorContext
from app.cognition.heuristic.director_backend import HeuristicDirectorBackend
from app.cognition.interfaces import DirectorCognitionBackend
from app.cognition.registry import get_cognition_registry
from app.cognition.types import BackendExecutionContext, DirectorDecisionInvocation
from app.director.observer import DirectorAssessment
from app.director.types import DirectorActorCandidate, DirectorPlan
from app.director.strategy_engine import StrategyExecutor
from app.infra.logging import get_logger
from app.scenario.bundle_registry import resolve_default_scenario_id
from app.scenario.runtime.director_config import load_director_config
from app.scenario.runtime_config import ScenarioRuntimeConfig
from app.scenario.types import get_agent_config_id, get_world_role

if TYPE_CHECKING:
    from app.store.models import Agent

logger = get_logger(__name__)


DirectorPlannerSemantics = ScenarioRuntimeConfig


class DirectorPlanner:
    """Hybrid planner that combines rule-based and LLM-based intervention decisions.

    支持的场景策略：
    - soft_check_in: 高怀疑度时的温和互动
    - preemptive_comfort: 怀疑度快速上升时的预防性干预
    - keep_scene_natural: 连续性风险时的场景维护
    - break_isolation: 打破主体长时间独处
    - rejection_recovery: 处理连续被拒绝的场景

    实验性功能：当 director_backend != heuristic 时，优先使用 LLM 智能决策

    导演决策按配置间隔执行，并在当前 tick 内返回可持久化结果。
    """

    def __init__(
        self,
        backend: DirectorCognitionBackend | None = None,
        *,
        scenario_id: str | None = None,
        semantics: DirectorPlannerSemantics | None = None,
    ) -> None:
        resolved_scenario_id = scenario_id or resolve_default_scenario_id()
        self._scenario_id = resolved_scenario_id
        self._semantics = semantics or DirectorPlannerSemantics()
        self._backend = backend or get_cognition_registry().build_director_backend()
        self._strategy_executor = StrategyExecutor()
        self._config = load_director_config(scenario_id=resolved_scenario_id)

    async def build_plan(
        self,
        *,
        assessment: DirectorAssessment,
        agents: list[Agent],
        recent_intervention_goals: list[str] | None = None,
        current_tick: int = 0,
        recent_events: list[dict[str, Any]] | None = None,
        recent_interventions: list[dict[str, Any]] | None = None,
        world_time: str = "",
        run_id: str = "",
        runtime_ctx: BackendExecutionContext | None = None,
        actor_candidates: dict[str, DirectorActorCandidate] | None = None,
        force_decision: bool = False,
    ) -> DirectorPlan | None:
        """构建导演干预计划

        规则后端立即返回；LLM 后端在当前 tick 内等待一次决策结果，避免结果随临时
        Scenario 实例销毁而丢失。

        Args:
            assessment: 世界状态评估
            agents: 所有 agent 列表
            recent_intervention_goals: 最近已执行的场景目标列表（用于避免重复）
            current_tick: 当前 tick 编号
            recent_events: 最近事件列表（用于智能决策）
            recent_interventions: 最近干预记录（用于智能决策）
            world_time: 世界时间字符串
            run_id: 运行ID

        Returns:
            DirectorPlan 或 None（无需干预时）
        """
        support_agents = [
            agent
            for agent in agents
            if get_world_role(agent.profile) in self._semantics.support_role_set()
        ]
        if not support_agents or assessment.subject_agent_id is None:
            return None

        # 检查最近已执行的干预，避免重复
        recent_goals = set(recent_intervention_goals or [])

        if self._backend.is_enabled() and (
            force_decision or self._backend.should_decide(current_tick)
        ):
            agent_snapshots: list[dict[str, Any]] = [
                (
                    actor_candidates[agent.id].as_prompt_context()
                    if actor_candidates and agent.id in actor_candidates
                    else {
                        "id": agent.id,
                        "name": agent.name,
                        "profile": dict(agent.profile or {}),
                        "current_location_id": agent.current_location_id,
                        "current_goal": agent.current_goal,
                        "availability": "available",
                        "eligible": True,
                        "conversation_participant_ids": [],
                        "same_location_as_subject": False,
                    }
                )
                for agent in agents
            ]
            context = DirectorContext(
                run_id=run_id,
                current_tick=current_tick,
                assessment=assessment,
                agents=agent_snapshots,
                support_roles=list(self._semantics.support_roles),
                recent_events=recent_events or [],
                recent_interventions=recent_interventions or [],
                world_time=world_time,
            )
            plan = await self._backend.propose_intervention(
                DirectorDecisionInvocation(
                    prompt="",
                    context=context,
                    recent_goals=recent_goals,
                    runtime_ctx=runtime_ctx,
                )
            )
            if plan is not None:
                logger.info(
                    "DirectorAgent decision completed at tick %s: %s targeting %s",
                    current_tick,
                    plan.scene_goal,
                    plan.target_agent_ids,
                )
                return plan

        if not self._allows_config_fallback():
            return None

        # 回退到配置化规则决策（同步，立即返回）
        # _build_config_based_plan 仍使用原始 ORM 对象（同步访问，无 greenlet 问题）
        return self._build_config_based_plan(assessment, support_agents, recent_goals)

    def _allows_config_fallback(self) -> bool:
        return isinstance(self._backend, HeuristicDirectorBackend)

    def _build_config_based_plan(
        self,
        assessment: DirectorAssessment,
        support_agents: list[Agent],
        recent_goals: set[str],
    ) -> DirectorPlan | None:
        """基于配置的干预计划构建（回退方案）

        使用 director.yml 中的策略配置，通过 StrategyConditionEngine 评估条件。
        """
        primary_support = self._pick_primary_support(support_agents)
        if primary_support is None:
            return None

        # 使用策略执行器评估配置的策略
        triggered = self._strategy_executor.evaluate_strategies(
            strategies=self._config.strategies,
            assessment=assessment,
            recent_goals=recent_goals,
            subject_agent_id=assessment.subject_agent_id,
            primary_cast_id=primary_support.id,
        )

        if triggered is None:
            return None

        # 构建 DirectorPlan
        plan_data = self._strategy_executor.build_plan_from_strategy(triggered)
        if plan_data is None:
            return None

        return DirectorPlan(
            scene_goal=plan_data["scene_goal"],
            target_agent_ids=plan_data["target_agent_ids"],
            priority=plan_data["priority"],
            urgency=plan_data["urgency"],
            message_hint=plan_data["message_hint"],
            target_agent_id=plan_data["target_agent_id"],
            reason=plan_data["reason"],
            cooldown_ticks=plan_data["cooldown_ticks"],
        )

    def _pick_primary_support(self, support_agents: list[Agent]) -> Agent | None:
        sorted_agents = sorted(
            support_agents,
            key=lambda agent: (
                get_agent_config_id(agent.profile) not in {"spouse", "friend"},
                agent.name,
            ),
        )
        return sorted_agents[0] if sorted_agents else None
