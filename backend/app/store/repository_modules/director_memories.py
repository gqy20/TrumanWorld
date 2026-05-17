from __future__ import annotations
# ruff: noqa: F403,F405

from app.store.repository_modules._common import *


class DirectorMemoryRepository:
    """导演干预记忆持久化"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        run_id: str,
        tick_no: int,
        scene_goal: str,
        target_agent_ids: list[str] | None = None,
        priority: str = "advisory",
        urgency: str = "advisory",
        message_hint: str | None = None,
        target_agent_id: str | None = None,
        reason: str | None = None,
        trigger_subject_alert_score: float = 0.0,
        trigger_continuity_risk: str = "stable",
        cooldown_ticks: int = 3,
        location_hint: str | None = None,
    ) -> DirectorMemory:
        """创建导演干预记忆"""
        resolved_target_agent_ids = list(target_agent_ids or [])
        # Build metadata dict for extra fields not in the model
        metadata_json: dict = {}
        if location_hint:
            metadata_json["location_hint"] = location_hint

        memory = DirectorMemory(
            id=str(uuid4()),
            run_id=run_id,
            tick_no=tick_no,
            scene_goal=scene_goal,
            target_agent_ids=json.dumps(resolved_target_agent_ids),
            priority=priority,
            urgency=urgency,
            message_hint=message_hint,
            target_agent_id=target_agent_id,
            reason=reason,
            trigger_subject_alert_score=trigger_subject_alert_score,
            trigger_continuity_risk=trigger_continuity_risk,
            cooldown_ticks=cooldown_ticks,
            cooldown_until_tick=tick_no + cooldown_ticks,
            metadata_json=metadata_json,
        )
        self.session.add(memory)
        await self.session.commit()
        await self.session.refresh(memory)
        return memory

    async def list_for_run(
        self,
        run_id: str,
        limit: int = 20,
    ) -> Sequence[DirectorMemory]:
        """获取指定 run 的导演干预历史"""
        stmt: Select[tuple[DirectorMemory]] = (
            select(DirectorMemory)
            .where(DirectorMemory.run_id == run_id)
            .order_by(DirectorMemory.tick_no.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_for_run(self, run_id: str) -> int:
        from sqlalchemy import func as sql_func

        stmt = select(sql_func.count(DirectorMemory.id)).where(DirectorMemory.run_id == run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def count_executed_for_run(self, run_id: str) -> int:
        from sqlalchemy import func as sql_func

        stmt = select(sql_func.count(DirectorMemory.id)).where(
            DirectorMemory.run_id == run_id,
            DirectorMemory.was_executed == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def get_recent_goals(
        self,
        run_id: str,
        current_tick: int,
        lookback_ticks: int = 10,
    ) -> list[str]:
        """获取最近干预的场景目标列表（用于避免重复干预）"""
        stmt: Select[tuple[DirectorMemory]] = select(DirectorMemory).where(
            DirectorMemory.run_id == run_id,
            DirectorMemory.tick_no >= current_tick - lookback_ticks,
        )
        result = await self.session.execute(stmt)
        memories = result.scalars().all()
        return [m.scene_goal for m in memories]

    async def get_active_cooldowns(
        self,
        run_id: str,
        current_tick: int,
    ) -> list[str]:
        """获取当前仍在冷却期的场景目标"""
        stmt: Select[tuple[DirectorMemory]] = select(DirectorMemory).where(
            DirectorMemory.run_id == run_id,
            DirectorMemory.cooldown_until_tick > current_tick,
        )
        result = await self.session.execute(stmt)
        memories = result.scalars().all()
        return [m.scene_goal for m in memories]

    async def mark_executed(
        self,
        memory_id: str,
        effectiveness_score: float | None = None,
    ) -> DirectorMemory | None:
        """标记干预已执行"""
        memory = await self.session.get(DirectorMemory, memory_id)
        if memory is None:
            return None
        memory.was_executed = True
        memory.effectiveness_score = effectiveness_score
        await self.session.commit()
        await self.session.refresh(memory)
        return memory

    async def get_latest_subject_alert_score(self, run_id: str) -> float:
        """获取最近一次干预时记录的主体告警值"""
        stmt: Select[tuple[DirectorMemory]] = (
            select(DirectorMemory)
            .where(DirectorMemory.run_id == run_id)
            .order_by(DirectorMemory.tick_no.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        memory = result.scalar_one_or_none()
        return memory.trigger_subject_alert_score if memory else 0.0

    async def get_pending_manual_interventions(
        self,
        run_id: str,
        current_tick: int,
        max_age_ticks: int = 5,
    ) -> Sequence[DirectorMemory]:
        """获取未执行的手动注入干预计划。

        手动注入的计划（gather, activity, shutdown, weather_change）
        优先级高于自动生成的计划。

        Args:
            run_id: Run ID
            current_tick: 当前 tick
            max_age_ticks: 最大有效 tick 数（超过此值视为过期）

        Returns:
            未执行的手动干预计划列表，按 tick_no 降序排列
        """
        manual_goals = ("gather", "activity", "shutdown", "weather_change", "power_outage")
        stmt: Select[tuple[DirectorMemory]] = (
            select(DirectorMemory)
            .where(
                DirectorMemory.run_id == run_id,
                DirectorMemory.was_executed == False,  # noqa: E712
                DirectorMemory.scene_goal.in_(manual_goals),
                DirectorMemory.tick_no >= current_tick - max_age_ticks,
            )
            .order_by(DirectorMemory.tick_no.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_pending_interventions(
        self,
        run_id: str,
        current_tick: int,
        max_age_ticks: int = 10,
    ) -> Sequence[DirectorMemory]:
        """获取所有未执行的干预计划。

        Args:
            run_id: Run ID
            current_tick: 当前 tick
            max_age_ticks: 最大有效 tick 数

        Returns:
            未执行的干预计划列表
        """
        stmt: Select[tuple[DirectorMemory]] = (
            select(DirectorMemory)
            .where(
                DirectorMemory.run_id == run_id,
                DirectorMemory.was_executed == False,  # noqa: E712
                DirectorMemory.tick_no >= current_tick - max_age_ticks,
            )
            .order_by(DirectorMemory.tick_no.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
