from __future__ import annotations

from typing import TYPE_CHECKING

from app.cognition.heuristic.agent_backend import HeuristicAgentBackend
from app.infra.logging import get_logger
from app.sim.day_boundary import (
    run_evening_reflection,
    run_morning_planning,
    should_run_planner,
    should_run_reflector,
)

if TYPE_CHECKING:
    from app.agent.runtime import AgentRuntime
    from app.sim.world import WorldState


logger = get_logger(__name__)


class DayBoundaryCoordinator:
    async def run_planner_if_needed(
        self,
        *,
        run_id: str,
        tick_no: int,
        world: WorldState,
        engine,
        agent_runtime: AgentRuntime,
    ) -> dict[str, dict[str, str]]:
        """在 agent 决策前运行 Planner（如果当前是清晨边界）。

        返回本轮已持久化的 agent 计划，供调用方直接更新决策上下文。
        """
        if engine is None or not world.agents or not should_run_planner(world):
            return {}
        try:
            return await run_morning_planning(
                run_id=run_id,
                tick_no=tick_no,
                world=world,
                engine=engine,
                agent_runtime=agent_runtime,
            )
        except Exception as exc:
            logger.warning(f"Day boundary planner failed: {exc}")
            if not isinstance(agent_runtime.backend, HeuristicAgentBackend):
                raise
            return {}

    async def run_reflector_if_needed(
        self,
        *,
        run_id: str,
        tick_no: int,
        world: WorldState,
        engine,
        agent_runtime: AgentRuntime,
    ) -> None:
        """在 tick 结束后运行 Reflector（如果当前是夜晚边界）。"""
        if engine is None or not should_run_reflector(world):
            return
        try:
            await run_evening_reflection(
                run_id=run_id,
                tick_no=tick_no,
                world=world,
                engine=engine,
                agent_runtime=agent_runtime,
            )
        except Exception as exc:
            logger.warning(f"Day boundary reflector failed: {exc}")
            if not isinstance(agent_runtime.backend, HeuristicAgentBackend):
                raise
