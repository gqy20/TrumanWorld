from __future__ import annotations
# ruff: noqa: F403,F405

from app.store.repository_modules._common import *


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
                Agent.status,
                Agent.profile,
                Agent.movement,
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
                status=row.status or {},
                profile=row.profile or {},
                movement=row.movement or {},
            )
            for row in result.all()
        ]

    async def count_memories_for_run(self, run_id: str) -> dict[str, int]:
        stmt = (
            select(Agent.id, func.count(Memory.id).label("memory_count"))
            .outerjoin(
                Memory,
                and_(Memory.agent_id == Agent.id, Memory.run_id == run_id),
            )
            .where(Agent.run_id == run_id)
            .group_by(Agent.id)
            .order_by(Agent.id.asc())
        )
        result = await self.session.execute(stmt)
        return {row.id: int(row.memory_count) for row in result.all()}

    async def list_recent_memories(
        self,
        agent_id: str,
        limit: int = 10,
        memory_type: str | None = None,
        memory_category: str | None = None,
        min_importance: float | None = None,
        query: str | None = None,
        related_agent_id: str | None = None,
    ) -> Sequence[Memory]:
        filters = [Memory.agent_id == agent_id]
        if memory_type:
            filters.append(Memory.memory_type == memory_type)
        if memory_category:
            filters.append(Memory.memory_category == memory_category)
        if min_importance is not None:
            filters.append(Memory.importance >= min_importance)
        if related_agent_id:
            filters.append(Memory.related_agent_id == related_agent_id)
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(
                or_(
                    Memory.content.ilike(pattern),
                    Memory.summary.ilike(pattern),
                )
            )

        stmt: Select[tuple[Memory]] = (
            select(Memory)
            .where(*filters)
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
        event_type: str | None = None,
        query: str | None = None,
        include_routine_events: bool = True,
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

        filters = [Event.run_id == run_id, event_scope]
        if event_type:
            filters.append(Event.event_type == event_type)
        if not include_routine_events:
            filters.append(Event.event_type.not_in(["work", "rest"]))
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(
                or_(
                    Event.event_type.ilike(pattern),
                    cast(Event.payload, String).ilike(pattern),
                    cast(Event.location_id, String).ilike(pattern),
                )
            )

        stmt: Select[tuple[Event]] = (
            select(Event)
            .where(*filters)
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
