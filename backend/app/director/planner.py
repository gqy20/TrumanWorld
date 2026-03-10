from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.director.agent import DirectorAgent, DirectorContext
from app.director.observer import DirectorAssessment
from app.director.strategy_engine import StrategyExecutor
from app.director.types import DirectorPlan
from app.infra.logging import get_logger
from app.scenario.truman_world.director_config import load_director_config
from app.scenario.types import get_agent_config_id, get_world_role
from app.store.models import Agent

logger = get_logger(__name__)


class DirectorPlanner:
    """Hybrid planner that combines rule-based and LLM-based intervention decisions.

    支持的场景策略：
    - soft_check_in: 高怀疑度时的温和互动
    - preemptive_comfort: 怀疑度快速上升时的预防性干预
    - keep_scene_natural: 连续性风险时的场景维护
    - break_isolation: 打破 Truman 长时间独处
    - rejection_recovery: 处理连续被拒绝的场景

    实验性功能：当 director_agent_enabled=true 时，优先使用LLM智能决策
    
    性能优化：
    - 导演决策与 tick 执行并行（非阻塞）
    - 可配置决策间隔（默认 5 tick）
    """

    def __init__(self) -> None:
        self._agent = DirectorAgent()
        self._strategy_executor = StrategyExecutor()
        self._pending_decision: asyncio.Task[DirectorPlan | None] | None = None
        self._last_decision_tick: int = 0
        self._config = load_director_config()

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
    ) -> DirectorPlan | None:
        """构建导演干预计划

        支持两种模式：
        1. 同步模式：立即返回决策结果（使用规则决策）
        2. 异步模式：启动 LLM 决策任务，不阻塞 tick 执行

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
        cast_agents = [agent for agent in agents if get_world_role(agent.profile) == "cast"]
        if not cast_agents or assessment.truman_agent_id is None:
            return None

        # 检查最近已执行的干预，避免重复
        recent_goals = set(recent_intervention_goals or [])

        # 检查是否有待完成的 LLM 决策
        if self._pending_decision is not None:
            if self._pending_decision.done():
                # LLM 决策已完成，获取结果
                try:
                    plan = self._pending_decision.result()
                    self._pending_decision = None
                    if plan is not None:
                        logger.info(
                            f"DirectorAgent async decision completed at tick {current_tick}: "
                            f"{plan.scene_goal} targeting {plan.target_cast_ids}"
                        )
                        return plan
                except Exception as exc:
                    logger.warning(f"DirectorAgent async decision failed: {exc}")
                    self._pending_decision = None
            # 如果决策还在进行中，继续执行规则决策（不阻塞）

        # 实验性功能：启动 LLM 智能决策（异步，不阻塞）
        if self._agent.is_enabled() and self._agent.should_decide(current_tick):
            if self._pending_decision is None and current_tick > self._last_decision_tick:
                # 启动新的异步决策任务
                self._last_decision_tick = current_tick
                context = DirectorContext(
                    run_id=run_id,
                    current_tick=current_tick,
                    assessment=assessment,
                    agents=agents,
                    recent_events=recent_events or [],
                    recent_interventions=recent_interventions or [],
                    world_time=world_time,
                )
                self._pending_decision = asyncio.create_task(
                    self._agent.decide(context, recent_goals)
                )
                logger.debug(f"DirectorAgent started async decision at tick {current_tick}")

        # 回退到配置化规则决策（同步，立即返回）
        return self._build_config_based_plan(assessment, cast_agents, recent_goals)

    def _build_config_based_plan(
        self,
        assessment: DirectorAssessment,
        cast_agents: list[Agent],
        recent_goals: set[str],
    ) -> DirectorPlan | None:
        """基于配置的干预计划构建（回退方案）
        
        使用 director.yml 中的策略配置，通过 StrategyConditionEngine 评估条件。
        """
        primary_cast = self._pick_primary_cast(cast_agents)
        if primary_cast is None:
            return None
        
        # 使用策略执行器评估配置的策略
        triggered = self._strategy_executor.evaluate_strategies(
            strategies=self._config.strategies,
            assessment=assessment,
            recent_goals=recent_goals,
            truman_agent_id=assessment.truman_agent_id,
            primary_cast_id=primary_cast.id,
        )
        
        if triggered is None:
            return None
        
        # 构建 DirectorPlan
        plan_data = self._strategy_executor.build_plan_from_strategy(triggered)
        if plan_data is None:
            return None
        
        return DirectorPlan(
            scene_goal=plan_data["scene_goal"],
            target_cast_ids=plan_data["target_cast_ids"],
            priority=plan_data["priority"],
            urgency=plan_data["urgency"],
            message_hint=plan_data["message_hint"],
            target_agent_id=plan_data["target_agent_id"],
            reason=plan_data["reason"],
            cooldown_ticks=plan_data["cooldown_ticks"],
        )

    def _pick_primary_cast(self, cast_agents: list[Agent]) -> Agent | None:
        sorted_agents = sorted(
            cast_agents,
            key=lambda agent: (
                get_agent_config_id(agent.profile) not in {"spouse", "friend"},
                agent.name,
            ),
        )
        return sorted_agents[0] if sorted_agents else None
