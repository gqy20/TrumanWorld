from __future__ import annotations

from typing import TYPE_CHECKING

from app.infra.logging import get_logger
from app.sim.day_boundary import (
    run_evening_reflection,
    run_morning_planning,
    should_run_planner,
    should_run_reflector,
)

if TYPE_CHECKING:
    from app.agent.runtime import AgentRuntime
    from app.sim.runner import TickResult
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
    ) -> bool:
        """在 agent 决策前运行 Planner（如果当前是清晨边界）。

        返回 True 表示 Planner 已执行，调用方的 agent_data 应重新加载以获取新计划。
        """
        if engine is None or not should_run_planner(world):
            return False
        try:
            await run_morning_planning(
                run_id=run_id,
                tick_no=tick_no,
                world=world,
                engine=engine,
                agent_runtime=agent_runtime,
            )
            return True
        except Exception as exc:
            logger.warning(f"Day boundary planner failed: {exc}")
            return False

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

    async def run(
        self,
        *,
        run_id: str,
        result: TickResult,
        world: WorldState,
        engine,
        agent_runtime: AgentRuntime,
    ) -> None:
        """向后兼容接口：在 tick 结束后仅处理 Reflector。

        Planner 已由 run_planner_if_needed() 在 agent 决策前提前执行。
        """
        await self.run_reflector_if_needed(
            run_id=run_id,
            tick_no=result.tick_no,
            world=world,
            engine=engine,
            agent_runtime=agent_runtime,
        )
