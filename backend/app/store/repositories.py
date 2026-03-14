from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Select, and_, case, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.store.models import (
    Agent,
    DirectorMemory,
    Event,
    LlmCall,
    Location,
    Memory,
    Relationship,
    SimulationRun,
)


@dataclass(slots=True)
class AgentNameRow:
    id: str
    name: str


@dataclass(slots=True)
class AgentWorldRow:
    id: str
    name: str
    occupation: str | None
    current_goal: str | None
    current_location_id: str | None
    profile: dict


@dataclass(slots=True)
class LocationNameRow:
    id: str
    name: str


@dataclass(slots=True)
class LocationWorldRow:
    id: str
    name: str
    location_type: str | None
    x: int
    y: int
    capacity: int


@dataclass(slots=True)
class EventApiRow:
    id: str
    tick_no: int
    world_time: datetime | None
    event_type: str
    actor_agent_id: str | None
    target_agent_id: str | None
    location_id: str | None
    importance: float
    visibility: str
    payload: dict
    created_at: datetime


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
        now = datetime.now(UTC)
        if status == "running":
            # 开始运行：记录本次启动时间（仅当之前未启动时才设置，避免恢复时重置）
            if run.started_at is None:
                run.started_at = now
        elif run.started_at is not None:
            # 暂停/停止：把本次运行时长累加到 elapsed_seconds
            delta = int((now - run.started_at).total_seconds())
            run.elapsed_seconds = (run.elapsed_seconds or 0) + max(0, delta)
            run.started_at = None
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

    async def delete_with_related(self, run: SimulationRun) -> None:
        run_id = run.id
        await self.session.execute(delete(Relationship).where(Relationship.run_id == run_id))
        await self.session.execute(delete(Memory).where(Memory.run_id == run_id))
        await self.session.execute(delete(DirectorMemory).where(DirectorMemory.run_id == run_id))
        await self.session.execute(delete(Event).where(Event.run_id == run_id))
        await self.session.execute(delete(LlmCall).where(LlmCall.run_id == run_id))
        await self.session.execute(delete(Agent).where(Agent.run_id == run_id))
        await self.session.execute(delete(Location).where(Location.run_id == run_id))
        await self.session.delete(run)
        await self.session.commit()

    async def reset_running_on_startup(self) -> list[SimulationRun]:
        """Reset all running runs to paused on startup.

        Sets was_running_before_restart=True for runs that were running,
        accumulates elapsed time from started_at to now, then sets status
        to 'paused'. Returns the list of affected runs.
        """
        from datetime import UTC, datetime

        from sqlalchemy import update

        now = datetime.now(UTC)

        # First, get all running runs
        stmt = select(SimulationRun).where(SimulationRun.status == "running")
        result = await self.session.execute(stmt)
        running_runs = list(result.scalars().all())

        if not running_runs:
            return []

        # Accumulate elapsed time for each run before pausing
        run_updates = []
        for run in running_runs:
            new_elapsed = run.elapsed_seconds or 0
            if run.started_at is not None:
                delta = int((now - run.started_at).total_seconds())
                new_elapsed += max(0, delta)
            run_updates.append(
                {
                    "id": run.id,
                    "elapsed_seconds": new_elapsed,
                }
            )

        # Update: set was_running_before_restart=True, status='paused',
        # elapsed_seconds=accumulated, started_at=None
        for upd in run_updates:
            await self.session.execute(
                update(SimulationRun)
                .where(SimulationRun.id == upd["id"])
                .values(
                    was_running_before_restart=True,
                    status="paused",
                    elapsed_seconds=upd["elapsed_seconds"],
                    started_at=None,
                )
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

    @staticmethod
    def _event_api_columns():
        return (
            Event.id,
            Event.tick_no,
            Event.world_time,
            Event.event_type,
            Event.actor_agent_id,
            Event.target_agent_id,
            Event.location_id,
            Event.importance,
            Event.visibility,
            Event.payload,
            Event.created_at,
        )

    @staticmethod
    def _to_event_api_rows(rows) -> list[EventApiRow]:
        return [
            EventApiRow(
                id=row.id,
                tick_no=row.tick_no,
                world_time=row.world_time,
                event_type=row.event_type,
                actor_agent_id=row.actor_agent_id,
                target_agent_id=row.target_agent_id,
                location_id=row.location_id,
                importance=row.importance,
                visibility=row.visibility,
                payload=row.payload or {},
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def list_for_run(
        self, run_id: str, limit: int = 50, since_tick: int | None = None
    ) -> Sequence[Event]:
        # Priority ordering mirrors list_recent_events: social/move surface before
        # work/rest noise so the world snapshot always contains meaningful events.
        event_priority = case(
            (
                Event.event_type.in_(
                    [
                        "talk",
                        "speech",
                        "listen",
                        "conversation_started",
                        "conversation_joined",
                        "move",
                    ]
                ),
                0,
            ),
            (Event.event_type.in_(["work", "rest"]), 2),
            else_=1,
        )
        stmt: Select[tuple[Event]] = (
            select(Event)
            .where(Event.run_id == run_id)
            .order_by(event_priority, Event.tick_no.desc(), Event.created_at.desc())
            .limit(limit)
        )
        # 增量查询：只获取指定 tick 之后的事件
        if since_tick is not None:
            stmt = stmt.where(Event.tick_no > since_tick)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_api_rows_for_run(
        self, run_id: str, limit: int = 50, since_tick: int | None = None
    ) -> Sequence[EventApiRow]:
        event_priority = case(
            (
                Event.event_type.in_(
                    [
                        "talk",
                        "speech",
                        "listen",
                        "conversation_started",
                        "conversation_joined",
                        "move",
                    ]
                ),
                0,
            ),
            (Event.event_type.in_(["work", "rest"]), 2),
            else_=1,
        )
        stmt = (
            select(*self._event_api_columns())
            .where(Event.run_id == run_id)
            .order_by(event_priority, Event.tick_no.desc(), Event.created_at.desc())
            .limit(limit)
        )
        if since_tick is not None:
            stmt = stmt.where(Event.tick_no > since_tick)
        result = await self.session.execute(stmt)
        return self._to_event_api_rows(result.all())

    async def list_timeline_events(
        self,
        run_id: str,
        tick_from: int | None = None,
        tick_to: int | None = None,
        event_type: str | None = None,
        actor_agent_id: str | None = None,
        target_agent_id: str | None = None,
        keyword: str | None = None,
        limit: int = 2000,
        offset: int = 0,
        order_desc: bool = False,
    ) -> tuple[Sequence[Event], int]:
        """专为时间线回放设计的全量查询，支持多维过滤和排序。

        Args:
            order_desc: 是否按 tick 倒序排列（最新事件在前），默认为 False（正序）

        Returns:
            (events, total_count) 元组，total_count 为过滤后的总条数（用于分页提示）。
        """
        from sqlalchemy import func as sql_func

        conditions = [Event.run_id == run_id]

        if tick_from is not None:
            conditions.append(Event.tick_no >= tick_from)
        if tick_to is not None:
            conditions.append(Event.tick_no <= tick_to)
        if event_type:
            # 支持逗号分隔的多类型过滤，如 "talk,move"
            types = [t.strip() for t in event_type.split(",") if t.strip()]
            if types:
                conditions.append(Event.event_type.in_(types))
        if actor_agent_id:
            conditions.append(
                or_(Event.actor_agent_id == actor_agent_id, Event.target_agent_id == actor_agent_id)
            )

        where_clause = and_(*conditions)

        # 统计总条数
        count_stmt = select(sql_func.count(Event.id)).where(where_clause)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one() or 0

        # 根据 order_desc 参数决定排序方向
        if order_desc:
            # 按 tick 倒序 + created_at 倒序（最新事件在前，方便复盘最近发生的事件）
            stmt: Select[tuple[Event]] = (
                select(Event)
                .where(where_clause)
                .order_by(Event.tick_no.desc(), Event.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        else:
            # 按 tick 正序 + created_at 正序（方便时间线从旧到新回放）
            stmt = (
                select(Event)
                .where(where_clause)
                .order_by(Event.tick_no.asc(), Event.created_at.asc())
                .limit(limit)
                .offset(offset)
            )
        result = await self.session.execute(stmt)
        return result.scalars().all(), total

    async def list_timeline_api_rows(
        self,
        run_id: str,
        tick_from: int | None = None,
        tick_to: int | None = None,
        event_type: str | None = None,
        actor_agent_id: str | None = None,
        target_agent_id: str | None = None,
        keyword: str | None = None,
        limit: int = 2000,
        offset: int = 0,
        order_desc: bool = False,
    ) -> tuple[Sequence[EventApiRow], int]:
        from sqlalchemy import func as sql_func

        conditions = [Event.run_id == run_id]

        if tick_from is not None:
            conditions.append(Event.tick_no >= tick_from)
        if tick_to is not None:
            conditions.append(Event.tick_no <= tick_to)
        if event_type:
            types = [t.strip() for t in event_type.split(",") if t.strip()]
            if types:
                conditions.append(Event.event_type.in_(types))
        if actor_agent_id:
            conditions.append(
                or_(Event.actor_agent_id == actor_agent_id, Event.target_agent_id == actor_agent_id)
            )

        where_clause = and_(*conditions)

        count_stmt = select(sql_func.count(Event.id)).where(where_clause)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one() or 0

        stmt = select(*self._event_api_columns()).where(where_clause)
        if order_desc:
            stmt = stmt.order_by(Event.tick_no.desc(), Event.created_at.desc())
        else:
            stmt = stmt.order_by(Event.tick_no.asc(), Event.created_at.asc())
        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return self._to_event_api_rows(result.all()), total

    async def count_events_by_type(
        self,
        run_id: str,
        tick_from: int | None = None,
        tick_to: int | None = None,
        event_types: list[str] | None = None,
    ) -> dict[str, int]:
        """统计指定 tick 范围内各类型事件的数量。

        Args:
            run_id: 运行 ID
            tick_from: 起始 tick（包含）
            tick_to: 结束 tick（包含）
            event_types: 要统计的事件类型列表，默认为常用类型

        Returns:
            事件类型到数量的映射字典
        """
        from sqlalchemy import func as sql_func

        if event_types is None:
            event_types = ["speech", "listen", "move", "move_rejected", "talk_rejected"]

        conditions = [Event.run_id == run_id]
        if tick_from is not None:
            conditions.append(Event.tick_no >= tick_from)
        if tick_to is not None:
            conditions.append(Event.tick_no <= tick_to)

        where_clause = and_(*conditions)

        # 按事件类型分组统计
        stmt = (
            select(Event.event_type, sql_func.count(Event.id))
            .where(where_clause)
            .where(Event.event_type.in_(event_types))
            .group_by(Event.event_type)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        return {row[0]: row[1] for row in rows}

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

    async def list_names_for_run(self, run_id: str) -> Sequence[AgentNameRow]:
        stmt = select(Agent.id, Agent.name).where(Agent.run_id == run_id).order_by(Agent.name.asc())
        result = await self.session.execute(stmt)
        return [AgentNameRow(id=row.id, name=row.name) for row in result.all()]

    async def list_world_rows_for_run(self, run_id: str) -> Sequence[AgentWorldRow]:
        stmt = (
            select(
                Agent.id,
                Agent.name,
                Agent.occupation,
                Agent.current_goal,
                Agent.current_location_id,
                Agent.profile,
            )
            .where(Agent.run_id == run_id)
            .order_by(Agent.name.asc())
        )
        result = await self.session.execute(stmt)
        return [
            AgentWorldRow(
                id=row.id,
                name=row.name,
                occupation=row.occupation,
                current_goal=row.current_goal,
                current_location_id=row.current_location_id,
                profile=row.profile or {},
            )
            for row in result.all()
        ]

    async def list_recent_memories(self, agent_id: str, limit: int = 10) -> Sequence[Memory]:
        stmt: Select[tuple[Memory]] = (
            select(Memory)
            .where(Memory.agent_id == agent_id)
            .order_by(Memory.tick_no.desc(), Memory.created_at.desc())
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
        current_location_id: str | None = None,
    ) -> Sequence[Event]:
        """List recent events for an agent.

        Includes:
        - Events where agent is actor or target
        - Events at agent's current location (for observer awareness)
        - Director system events (if enabled)

        Results are ordered by event priority first (social/move before work/rest),
        then by recency, so that meaningful interactions always surface within
        the limit window instead of being displaced by repetitive work/rest noise.
        """
        # Direct participation events
        agent_events = or_(Event.actor_agent_id == agent_id, Event.target_agent_id == agent_id)
        event_scope = agent_events

        # Location-based observer events (same location, not already included)
        if current_location_id:
            location_events = and_(
                Event.location_id == current_location_id,
                Event.actor_agent_id != agent_id,
                Event.target_agent_id != agent_id,
            )
            event_scope = or_(agent_events, location_events)

        if include_director_system_events:
            director_events = and_(
                Event.visibility == "system",
                Event.event_type.startswith("director_"),
            )
            event_scope = or_(event_scope, director_events)

        # Priority ordering: social and movement events surface before work/rest noise.
        # Within the same priority tier events are ordered by recency.
        event_priority = case(
            (
                Event.event_type.in_(
                    [
                        "talk",
                        "speech",
                        "listen",
                        "conversation_started",
                        "conversation_joined",
                        "move",
                    ]
                ),
                0,
            ),
            (Event.event_type.in_(["work", "rest"]), 2),
            else_=1,
        )

        stmt: Select[tuple[Event]] = (
            select(Event)
            .where(
                Event.run_id == run_id,
                event_scope,
            )
            .order_by(event_priority, Event.tick_no.desc(), Event.created_at.desc())
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

    async def find_recent_routine_memory(
        self,
        run_id: str,
        agent_id: str,
        summary: str,
        location_id: str | None,
        since_tick: int,
    ) -> Memory | None:
        stmt: Select[tuple[Memory]] = (
            select(Memory)
            .where(
                Memory.run_id == run_id,
                Memory.agent_id == agent_id,
                Memory.summary == summary,
                Memory.location_id.is_(location_id)
                if location_id is None
                else Memory.location_id == location_id,
                Memory.metadata_json["event_type"].as_string().in_(["work", "rest"]),
                Memory.tick_no >= since_tick,
            )
            .order_by(Memory.tick_no.desc(), Memory.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


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

        await self.session.flush()
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

    async def list_names_for_run(self, run_id: str) -> Sequence[LocationNameRow]:
        stmt = (
            select(Location.id, Location.name)
            .where(Location.run_id == run_id)
            .order_by(Location.name.asc())
        )
        result = await self.session.execute(stmt)
        return [LocationNameRow(id=row.id, name=row.name) for row in result.all()]

    async def list_world_rows_for_run(self, run_id: str) -> Sequence[LocationWorldRow]:
        stmt = (
            select(
                Location.id,
                Location.name,
                Location.location_type,
                Location.x,
                Location.y,
                Location.capacity,
            )
            .where(Location.run_id == run_id)
            .order_by(Location.name.asc())
        )
        result = await self.session.execute(stmt)
        return [
            LocationWorldRow(
                id=row.id,
                name=row.name,
                location_type=row.location_type,
                x=row.x,
                y=row.y,
                capacity=row.capacity,
            )
            for row in result.all()
        ]


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
        location_hint: str | None = None,
    ) -> DirectorMemory:
        """创建导演干预记忆"""
        # Build metadata dict for extra fields not in the model
        metadata_json: dict = {}
        if location_hint:
            metadata_json["location_hint"] = location_hint

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


class LlmCallRepository:
    """LLM 调用记录的持久化操作。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, record: LlmCall) -> None:
        self.session.add(record)
        await self.session.commit()

    async def get_token_totals(self, run_id: str) -> dict[str, int]:
        """查询指定 run 的全量 token 累计。

        Returns:
            包含 input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens 的字典
        """
        from sqlalchemy import func as sql_func

        stmt = select(
            sql_func.coalesce(sql_func.sum(LlmCall.input_tokens), 0).label("input_tokens"),
            sql_func.coalesce(sql_func.sum(LlmCall.output_tokens), 0).label("output_tokens"),
            sql_func.coalesce(sql_func.sum(LlmCall.cache_read_tokens), 0).label(
                "cache_read_tokens"
            ),
            sql_func.coalesce(sql_func.sum(LlmCall.cache_creation_tokens), 0).label(
                "cache_creation_tokens"
            ),
        ).where(LlmCall.run_id == run_id)
        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "cache_read_tokens": row.cache_read_tokens,
            "cache_creation_tokens": row.cache_creation_tokens,
        }
