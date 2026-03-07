from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.store.models import Agent, Event, Location, Memory, Relationship, SimulationRun


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
        stmt: Select[tuple[Agent]] = select(Agent).where(Agent.run_id == run_id).order_by(Agent.name.asc())
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

    async def list_recent_events(self, run_id: str, agent_id: str, limit: int = 10) -> Sequence[Event]:
        stmt: Select[tuple[Event]] = (
            select(Event)
            .where(
                Event.run_id == run_id,
                (Event.actor_agent_id == agent_id) | (Event.target_agent_id == agent_id),
            )
            .order_by(Event.tick_no.desc(), Event.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_relationships(self, run_id: str, agent_id: str, limit: int = 20) -> Sequence[Relationship]:
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

    async def get_pair(self, run_id: str, agent_id: str, other_agent_id: str) -> Relationship | None:
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
        stmt: Select[tuple[Location]] = select(Location).where(Location.run_id == run_id).order_by(Location.name.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


def build_event(
    run_id: str,
    tick_no: int,
    world_time: str,
    action_type: str,
    payload: dict,
    accepted: bool,
) -> Event:
    visibility = "public" if accepted else "system"
    event_type = action_type if accepted else f"{action_type}_rejected"
    return Event(
        id=str(uuid4()),
        run_id=run_id,
        tick_no=tick_no,
        event_type=event_type,
        actor_agent_id=payload.get("agent_id"),
        target_agent_id=payload.get("target_agent_id"),
        location_id=payload.get("location_id") or payload.get("to_location_id"),
        visibility=visibility,
        payload=payload,
    )
