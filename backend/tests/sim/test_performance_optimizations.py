"""Regression tests for batched queries and AsyncSession-safe loading."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.sim.agent_snapshot_builder import build_agent_memory_cache
from app.store.models import Agent, DirectorMemory, Event, LlmCall, Location, Memory, SimulationRun


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
async def test_relationship_persistence_batches_queries_and_flushes(db_session):
    from app.sim.persistence import PersistenceManager
    from app.store.repositories import AgentRepository

    run_id = "batched-relationship-persistence"
    run = _make_run(run_id)
    loc = _make_location(f"{run_id}-loc", run_id)
    actor = _make_agent(f"{run_id}-actor", run_id, loc.id)
    target = _make_agent(f"{run_id}-target", run_id, loc.id)
    db_session.add_all([run, loc, actor, target])
    await db_session.commit()
    events = [
        Event(
            id=f"{run_id}-event-{index}",
            run_id=run_id,
            tick_no=index,
            event_type="speech",
            actor_agent_id=actor.id,
            target_agent_id=target.id,
            location_id=loc.id,
            world_time=datetime.now(UTC),
            payload={},
        )
        for index in range(3)
    ]

    execute_count = 0
    flush_count = 0
    original_execute = db_session.execute
    original_flush = db_session.flush

    async def tracking_execute(*args, **kwargs):
        nonlocal execute_count
        execute_count += 1
        return await original_execute(*args, **kwargs)

    async def tracking_flush(*args, **kwargs):
        nonlocal flush_count
        flush_count += 1
        return await original_flush(*args, **kwargs)

    with (
        patch.object(db_session, "execute", tracking_execute),
        patch.object(db_session, "flush", tracking_flush),
    ):
        await PersistenceManager(db_session).persist_tick_relationships(run_id, events)

    actor_relationship = (await AgentRepository(db_session).list_relationships(run_id, actor.id))[0]
    target_relationship = (await AgentRepository(db_session).list_relationships(run_id, target.id))[
        0
    ]
    assert actor_relationship.familiarity == pytest.approx(0.3)
    assert target_relationship.familiarity == pytest.approx(0.3)
    assert execute_count <= 4
    assert flush_count == 1


@pytest.mark.asyncio
async def test_morning_inputs_use_fixed_query_count_for_multiple_agents(db_session):
    from app.sim.day_boundary import _load_morning_inputs

    run_id = "batched-morning-inputs"
    today = datetime(2026, 3, 3, tzinfo=UTC).date()
    run = _make_run(run_id)
    loc = _make_location(f"{run_id}-loc", run_id)
    agents = [_make_agent(f"{run_id}-agent-{index}", run_id, loc.id) for index in range(3)]
    memories = [
        Memory(
            id=f"{run_id}-today-plan",
            run_id=run_id,
            agent_id=agents[0].id,
            tick_no=288,
            memory_type="daily_plan",
            memory_category="long_term",
            content="今天已有计划",
            metadata_json={"day": today.isoformat()},
        ),
        Memory(
            id=f"{run_id}-yesterday-plan",
            run_id=run_id,
            agent_id=agents[1].id,
            tick_no=1,
            memory_type="daily_plan",
            memory_category="long_term",
            content="昨日工作计划",
            metadata_json={"day": "2026-03-02"},
        ),
        Memory(
            id=f"{run_id}-context",
            run_id=run_id,
            agent_id=agents[2].id,
            tick_no=100,
            memory_type="event",
            memory_category="long_term",
            content="长期记忆",
            metadata_json={},
        ),
    ]
    event = Event(
        id=f"{run_id}-work",
        run_id=run_id,
        tick_no=200,
        event_type="work",
        actor_agent_id=agents[1].id,
        payload={},
    )
    db_session.add_all([run, loc, *agents, *memories, event])
    await db_session.commit()

    query_count = 0
    original_execute = db_session.execute

    async def tracking_execute(*args, **kwargs):
        nonlocal query_count
        query_count += 1
        return await original_execute(*args, **kwargs)

    with patch.object(db_session, "execute", tracking_execute):
        pending, memories_by_agent, yesterday_by_agent = await _load_morning_inputs(
            db_session,
            run_id=run_id,
            agents=agents,
            today=today,
            current_tick=288,
            ticks_per_day=288,
        )

    assert [agent.id for agent in pending] == [agents[1].id, agents[2].id]
    assert memories_by_agent[agents[2].id][0]["content"] == "长期记忆"
    assert yesterday_by_agent[agents[1].id].endswith("昨日实际：work1次")
    assert query_count == 3


@pytest.mark.asyncio
async def test_evening_inputs_use_fixed_query_count_for_multiple_agents(db_session):
    from app.sim.day_boundary import _load_evening_inputs

    run_id = "batched-evening-inputs"
    today = datetime(2026, 3, 3, tzinfo=UTC).date()
    run = _make_run(run_id)
    loc = _make_location(f"{run_id}-loc", run_id)
    agents = [_make_agent(f"{run_id}-agent-{index}", run_id, loc.id) for index in range(3)]
    reflection = Memory(
        id=f"{run_id}-reflection",
        run_id=run_id,
        agent_id=agents[0].id,
        tick_no=288,
        memory_type="daily_reflection",
        memory_category="long_term",
        content="今天已有反思",
        metadata_json={"day": today.isoformat()},
    )
    event = Event(
        id=f"{run_id}-talk",
        run_id=run_id,
        tick_no=200,
        event_type="talk",
        actor_agent_id=agents[1].id,
        target_agent_id=agents[2].id,
        payload={"message": "晚上好"},
    )
    db_session.add_all([run, loc, *agents, reflection, event])
    await db_session.commit()

    query_count = 0
    original_execute = db_session.execute

    async def tracking_execute(*args, **kwargs):
        nonlocal query_count
        query_count += 1
        return await original_execute(*args, **kwargs)

    with patch.object(db_session, "execute", tracking_execute):
        pending, events_by_agent = await _load_evening_inputs(
            db_session,
            run_id=run_id,
            agents=agents,
            today=today,
            tick_no=288,
            ticks_per_day=288,
        )

    assert [agent.id for agent in pending] == [agents[1].id, agents[2].id]
    assert events_by_agent[agents[1].id][0]["event_type"] == "talk"
    assert events_by_agent[agents[2].id][0]["event_type"] == "talk"
    assert query_count == 2


@pytest.mark.asyncio
async def test_world_stats_are_loaded_in_one_query(db_session):
    from app.store.repositories import WorldStatsRepository

    run_id = "batched-world-stats"
    run = _make_run(run_id)
    db_session.add_all(
        [
            run,
            Event(
                id=f"{run_id}-speech",
                run_id=run_id,
                tick_no=1,
                event_type="speech",
                payload={},
            ),
            Event(
                id=f"{run_id}-move-rejected",
                run_id=run_id,
                tick_no=2,
                event_type="move_rejected",
                payload={},
            ),
            DirectorMemory(
                id=f"{run_id}-director-1",
                run_id=run_id,
                tick_no=1,
                scene_goal="activity",
                target_agent_ids="[]",
                was_executed=True,
                metadata_json={},
            ),
            DirectorMemory(
                id=f"{run_id}-director-2",
                run_id=run_id,
                tick_no=2,
                scene_goal="gather",
                target_agent_ids="[]",
                was_executed=False,
                metadata_json={},
            ),
            LlmCall(
                id=f"{run_id}-llm-1",
                run_id=run_id,
                task_type="reactor",
                provider="openai",
                model="MiniMax-M3",
                tick_no=1,
                input_tokens=10,
                output_tokens=20,
                reasoning_tokens=3,
                cache_read_tokens=4,
                cache_creation_tokens=5,
                duration_ms=100,
            ),
        ]
    )
    await db_session.commit()

    query_count = 0
    original_execute = db_session.execute

    async def tracking_execute(*args, **kwargs):
        nonlocal query_count
        query_count += 1
        return await original_execute(*args, **kwargs)

    with patch.object(db_session, "execute", tracking_execute):
        stats = await WorldStatsRepository(db_session).get_for_run(run_id)

    assert stats.event_counts["speech"] == 1
    assert stats.event_counts["move_rejected"] == 1
    assert stats.director_total == 2
    assert stats.director_executed == 1
    assert stats.token_totals == {
        "input_tokens": 10,
        "output_tokens": 20,
        "reasoning_tokens": 3,
        "cache_read_tokens": 4,
        "cache_creation_tokens": 5,
        "provider": "openai",
        "model": "MiniMax-M3",
    }
    assert query_count == 1
