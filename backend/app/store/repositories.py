from __future__ import annotations

import json
from collections.abc import Sequence
from uuid import uuid4

from datetime import UTC, datetime

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.store.models import (
    Agent,
    DirectorMemory,
    Event,
    Location,
    Memory,
    Relationship,
    SimulationRun,
)


class RunRepository:
    """Persistence facade for simulation runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, run: SimulationRun) -> SimulationRun:
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get(self, run_id: str) -> SimulationRun | None:
        return await self.session.get(SimulationRun, run_id)

    async def list(self, limit: int = 20) -> Sequence[SimulationRun]:
        stmt: Select[tuple[SimulationRun]] = (
            select(SimulationRun)
            .order_by(SimulationRun.updated_at.desc(), SimulationRun.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_status(self, run: SimulationRun, status: str) -> SimulationRun:
        run.status = status
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def update_tick(self, run: SimulationRun, tick_no: int) -> SimulationRun:
        run.current_tick = tick_no
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def delete(self, run: SimulationRun) -> None:
        await self.session.delete(run)
        await self.session.commit()

    async def reset_running_on_startup(self) -> list[SimulationRun]:
        """Reset all running runs to paused on startup.

        Sets was_running_before_restart=True for runs that were running,
        then sets their status to 'paused'. Returns the list of affected runs.
        """
        from sqlalchemy import update

        # First, get all running runs
        stmt = select(SimulationRun).where(SimulationRun.status == "running")
        result = await self.session.execute(stmt)
        running_runs = list(result.scalars().all())

        if not running_runs:
            return []

        # Update: set was_running_before_restart=True, status='paused'
        run_ids = [run.id for run in running_runs]
        await self.session.execute(
            update(SimulationRun)
            .where(SimulationRun.id.in_(run_ids))
            .values(was_running_before_restart=True, status="paused")
        )
        await self.session.commit()

        # Refresh and return
        for run in running_runs:
            await self.session.refresh(run)
        return running_runs

    async def list_runs_to_restore(self) -> Sequence[SimulationRun]:
        """Get all runs that were running before restart and can be restored."""
        stmt = select(SimulationRun).where(
            SimulationRun.was_running_before_restart.is_(True),
            SimulationRun.status == "paused",
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def clear_was_running_flag(self, run: SimulationRun) -> SimulationRun:
        """Clear the was_running_before_restart flag after successful restore."""
        run.was_running_before_restart = False
        await self.session.commit()
        await self.session.refresh(run)
        return run


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_run(self, run_id: str, limit: int = 50) -> Sequence[Event]:
        stmt: Select[tuple[Event]] = (
            select(Event)
            .where(Event.run_id == run_id)
            .order_by(Event.tick_no.desc(), Event.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, event: Event) -> Event:
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def create_many(self, events: Sequence[Event]) -> Sequence[Event]:
        self.session.add_all(list(events))
        await self.session.commit()
        for event in events:
            await self.session.refresh(event)
        return events


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, agent_id: str) -> Agent | None:
        return await self.session.get(Agent, agent_id)

    async def list_for_run(self, run_id: str) -> Sequence[Agent]:
        stmt: Select[tuple[Agent]] = (
            select(Agent).where(Agent.run_id == run_id).order_by(Agent.name.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_recent_memories(self, agent_id: str, limit: int = 10) -> Sequence[Memory]:
        stmt: Select[tuple[Memory]] = (
            select(Memory)
            .where(Memory.agent_id == agent_id)
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_recent_events(
        self,
        run_id: str,
        agent_id: str,
        limit: int = 10,
        include_director_system_events: bool = False,
    ) -> Sequence[Event]:
        agent_events = or_(Event.actor_agent_id == agent_id, Event.target_agent_id == agent_id)
        event_scope = agent_events
        if include_director_system_events:
            director_events = and_(
                Event.visibility == "system",
                Event.event_type.startswith("director_"),
            )
            event_scope = or_(agent_events, director_events)

        stmt: Select[tuple[Event]] = (
            select(Event)
            .where(
                Event.run_id == run_id,
                event_scope,
            )
            .order_by(Event.tick_no.desc(), Event.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_relationships(
        self, run_id: str, agent_id: str, limit: int = 20
    ) -> Sequence[Relationship]:
        stmt: Select[tuple[Relationship]] = (
            select(Relationship)
            .where(Relationship.run_id == run_id, Relationship.agent_id == agent_id)
            .order_by(Relationship.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_many(self, memories: Sequence[Memory]) -> Sequence[Memory]:
        self.session.add_all(list(memories))
        await self.session.commit()
        for memory in memories:
            await self.session.refresh(memory)
        return memories


class RelationshipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_pair(
        self, run_id: str, agent_id: str, other_agent_id: str
    ) -> Relationship | None:
        stmt: Select[tuple[Relationship]] = select(Relationship).where(
            Relationship.run_id == run_id,
            Relationship.agent_id == agent_id,
            Relationship.other_agent_id == other_agent_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_interaction(
        self,
        run_id: str,
        agent_id: str,
        other_agent_id: str,
        *,
        familiarity_delta: float,
        trust_delta: float,
        affinity_delta: float,
        relation_type: str = "acquaintance",
    ) -> Relationship:
        relation = await self.get_pair(run_id, agent_id, other_agent_id)
        now = datetime.now(UTC)

        if relation is None:
            relation = Relationship(
                id=str(uuid4()),
                run_id=run_id,
                agent_id=agent_id,
                other_agent_id=other_agent_id,
                familiarity=0.0,
                trust=0.0,
                affinity=0.0,
                relation_type=relation_type,
                last_interaction_at=now,
            )
            self.session.add(relation)

        relation.familiarity = min(1.0, max(0.0, relation.familiarity + familiarity_delta))
        relation.trust = min(1.0, max(-1.0, relation.trust + trust_delta))
        relation.affinity = min(1.0, max(-1.0, relation.affinity + affinity_delta))
        relation.relation_type = relation_type
        relation.last_interaction_at = now

        await self.session.commit()
        await self.session.refresh(relation)
        return relation


class LocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_run(self, run_id: str) -> Sequence[Location]:
        stmt: Select[tuple[Location]] = (
            select(Location).where(Location.run_id == run_id).order_by(Location.name.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class DirectorMemoryRepository:
    """导演干预记忆持久化"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        run_id: str,
        tick_no: int,
        scene_goal: str,
        target_cast_ids: list[str],
        priority: str = "advisory",
        urgency: str = "advisory",
        message_hint: str | None = None,
        target_agent_id: str | None = None,
        reason: str | None = None,
        trigger_suspicion_score: float = 0.0,
        trigger_continuity_risk: str = "stable",
        cooldown_ticks: int = 3,
    ) -> DirectorMemory:
        """创建导演干预记忆"""
        memory = DirectorMemory(
            id=str(uuid4()),
            run_id=run_id,
            tick_no=tick_no,
            scene_goal=scene_goal,
            target_cast_ids=json.dumps(target_cast_ids),
            priority=priority,
            urgency=urgency,
            message_hint=message_hint,
            target_agent_id=target_agent_id,
            reason=reason,
            trigger_suspicion_score=trigger_suspicion_score,
            trigger_continuity_risk=trigger_continuity_risk,
            cooldown_ticks=cooldown_ticks,
            cooldown_until_tick=tick_no + cooldown_ticks,
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

    async def get_latest_suspicion_score(self, run_id: str) -> float:
        """获取最近一次干预时记录的怀疑度"""
        stmt: Select[tuple[DirectorMemory]] = (
            select(DirectorMemory)
            .where(DirectorMemory.run_id == run_id)
            .order_by(DirectorMemory.tick_no.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        memory = result.scalar_one_or_none()
        return memory.trigger_suspicion_score if memory else 0.0
