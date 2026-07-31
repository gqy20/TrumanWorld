"""Regression tests for batched queries and AsyncSession-safe loading."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.sim.agent_snapshot_builder import build_agent_memory_cache
from app.store.models import Agent, Event, Location, Memory, SimulationRun


def _make_run(run_id: str) -> SimulationRun:
    return SimulationRun(
        id=run_id,
        name="perf-test",
        status="running",
        current_tick=5,
        tick_minutes=5,
    )


def _make_location(loc_id: str, run_id: str) -> Location:
    return Location(
        id=loc_id,
        run_id=run_id,
        name="Test Square",
        location_type="plaza",
        capacity=10,
    )


def _make_agent(agent_id: str, run_id: str, loc_id: str, role: str = "cast") -> Agent:
    return Agent(
        id=agent_id,
        run_id=run_id,
        name=f"Agent-{agent_id}",
        occupation="resident",
        home_location_id=loc_id,
        current_location_id=loc_id,
        current_goal="rest",
        personality={},
        profile={"agent_config_id": role, "world_role": role},
        status={},
        current_plan={},
    )


@pytest.mark.asyncio
async def test_memory_cache_returns_expected_categories(db_session):
    run_id = "perf-memory-cache-structure"
    run = _make_run(run_id)
    loc = _make_location(f"{run_id}-loc", run_id)
    agent = _make_agent(f"{run_id}-agent-0", run_id, loc.id)
    memory = Memory(
        id=f"{run_id}-mem-1",
        run_id=run_id,
        agent_id=agent.id,
        tick_no=1,
        memory_type="event",
        memory_category="long_term",
        content="测试记忆内容",
        summary="测试摘要",
        importance=0.5,
    )
    db_session.add_all([run, loc, agent, memory])
    await db_session.commit()

    result = await build_agent_memory_cache(session=db_session, run_id=run_id, agents=[agent])

    assert set(result[agent.id]) == {
        "short_term",
        "medium_term",
        "long_term",
        "about_others",
        "all",
    }
    assert result[agent.id]["long_term"][0]["content"] == "测试记忆内容"


@pytest.mark.asyncio
async def test_director_auto_plan_queries_events_at_most_once(db_session):
    from app.scenario.bundle_world.coordinator import BundleWorldCoordinator
    from app.store.repositories import EventRepository

    run_id = "perf-director-events"
    run = _make_run(run_id)
    loc = _make_location(f"{run_id}-loc", run_id)
    cast = _make_agent(f"{run_id}-cast", run_id, loc.id, "cast")
    subject = _make_agent(f"{run_id}-subject", run_id, loc.id, "truman")
    db_session.add_all([run, loc, cast, subject])
    await db_session.commit()

    calls = 0
    original = EventRepository.list_for_run

    async def tracking_list_for_run(self, target_run_id, limit=None, **kwargs):
        nonlocal calls
        calls += 1
        return await original(self, target_run_id, limit=limit, **kwargs)

    coordinator = BundleWorldCoordinator(db_session)
    with (
        patch.object(EventRepository, "list_for_run", tracking_list_for_run),
        patch.object(coordinator.planner, "build_plan", AsyncMock(return_value=None)),
    ):
        await coordinator._build_auto_plan(run_id, [cast, subject])

    assert calls <= 1


@pytest.mark.asyncio
async def test_load_world_does_not_overlap_queries_on_one_session(db_session):
    from app.sim.context import ContextBuilder
    from app.store.repositories import AgentRepository, LocationRepository

    run_id = "session-safe-load-world"
    run = _make_run(run_id)
    loc = _make_location(f"{run_id}-loc", run_id)
    agent = _make_agent(f"{run_id}-agent", run_id, loc.id)
    db_session.add_all([run, loc, agent])
    await db_session.commit()

    in_flight = False
    original_agents = AgentRepository.list_for_run
    original_locations = LocationRepository.list_for_run

    async def guarded_agents(self, target_run_id):
        nonlocal in_flight
        assert not in_flight, "AsyncSession query overlap"
        in_flight = True
        try:
            await asyncio.sleep(0)
            return await original_agents(self, target_run_id)
        finally:
            in_flight = False

    async def guarded_locations(self, target_run_id):
        nonlocal in_flight
        assert not in_flight, "AsyncSession query overlap"
        in_flight = True
        try:
            await asyncio.sleep(0)
            return await original_locations(self, target_run_id)
        finally:
            in_flight = False

    with (
        patch.object(AgentRepository, "list_for_run", guarded_agents),
        patch.object(LocationRepository, "list_for_run", guarded_locations),
    ):
        world = await ContextBuilder(db_session).load_world(run_id, run, tick_minutes=5)

    assert set(world.agents) == {agent.id}
    assert set(world.locations) == {loc.id}


@pytest.mark.asyncio
async def test_persist_tick_memories_does_not_overlap_queries_on_one_session(db_session):
    from app.sim.persistence import PersistenceManager
    from app.store.repositories import AgentRepository, LocationRepository

    run_id = "session-safe-memory-persistence"
    run = _make_run(run_id)
    loc = _make_location(f"{run_id}-loc", run_id)
    agent = _make_agent(f"{run_id}-agent", run_id, loc.id)
    db_session.add_all([run, loc, agent])
    await db_session.commit()

    in_flight = False
    original_agents = AgentRepository.list_for_run
    original_locations = LocationRepository.list_for_run

    async def guarded_agents(self, target_run_id):
        nonlocal in_flight
        assert not in_flight, "AsyncSession query overlap"
        in_flight = True
        try:
            await asyncio.sleep(0)
            return await original_agents(self, target_run_id)
        finally:
            in_flight = False

    async def guarded_locations(self, target_run_id):
        nonlocal in_flight
        assert not in_flight, "AsyncSession query overlap"
        in_flight = True
        try:
            await asyncio.sleep(0)
            return await original_locations(self, target_run_id)
        finally:
            in_flight = False

    with (
        patch.object(AgentRepository, "list_for_run", guarded_agents),
        patch.object(LocationRepository, "list_for_run", guarded_locations),
    ):
        await PersistenceManager(db_session).persist_tick_memories(run_id, [])


@pytest.mark.asyncio
async def test_relationship_persistence_updates_both_directions(db_session):
    from app.sim.persistence import PersistenceManager
    from app.store.repositories import RelationshipRepository

    run_id = "perf-rel-correct"
    run = _make_run(run_id)
    loc = _make_location(f"{run_id}-loc", run_id)
    actor = _make_agent(f"{run_id}-actor", run_id, loc.id)
    target = _make_agent(f"{run_id}-target", run_id, loc.id)
    db_session.add_all([run, loc, actor, target])
    await db_session.commit()

    calls: list[tuple[str, str]] = []
    original = RelationshipRepository.upsert_interaction

    async def tracking_upsert(self, run_id, agent_id, other_agent_id, **kwargs):
        calls.append((agent_id, other_agent_id))
        return await original(self, run_id, agent_id, other_agent_id, **kwargs)

    event = Event(
        id=str(uuid4()),
        run_id=run_id,
        tick_no=1,
        event_type="talk",
        actor_agent_id=actor.id,
        target_agent_id=target.id,
        world_time=datetime.now(UTC),
        payload={},
    )

    with patch.object(RelationshipRepository, "upsert_interaction", tracking_upsert):
        await PersistenceManager(db_session).persist_tick_relationships(run_id, [event])

    assert calls == [(actor.id, target.id), (target.id, actor.id)]
