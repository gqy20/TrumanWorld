from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.agent.runtime import RuntimeContext
from app.sim import day_boundary as day_boundary_module
from app.sim.day_boundary import (
    _load_morning_inputs,
    run_evening_reflection,
    run_morning_planning,
)
from app.store.models import Agent, Base, Event, LlmCall, Location, Memory, SimulationRun


class FakeAgentRuntime:
    def __init__(self) -> None:
        self.planner_world_contexts: list[dict] = []

    async def run_planner(
        self,
        agent_id: str,
        agent_name: str,
        world_context: dict,
        recent_memories: list[dict] | None = None,
        runtime_ctx=None,
    ) -> dict | None:
        self.planner_world_contexts.append(dict(world_context))
        return {
            "morning": "commute",
            "daytime": "work",
            "evening": "rest",
            "intention": f"{agent_name} keeps the day on track",
        }

    async def run_reflector(
        self,
        agent_id: str,
        agent_name: str,
        world_context: dict,
        daily_events: list[dict] | None = None,
        runtime_ctx=None,
    ) -> dict | None:
        return {
            "reflection": f"{agent_name} felt the day was coherent",
            "mood": "satisfied",
            "tomorrow_intention": "stay steady tomorrow",
        }


class FakeTrackingAgentRuntime(FakeAgentRuntime):
    async def run_planner(
        self,
        agent_id: str,
        agent_name: str,
        world_context: dict,
        recent_memories: list[dict] | None = None,
        runtime_ctx: RuntimeContext | None = None,
    ) -> dict | None:
        if runtime_ctx and runtime_ctx.on_llm_call:
            runtime_ctx.on_llm_call(
                agent_id=agent_id,
                task_type="planner",
                usage={"input_tokens": 123, "output_tokens": 45},
                total_cost_usd=0.01,
                duration_ms=321,
            )
        return await super().run_planner(
            agent_id=agent_id,
            agent_name=agent_name,
            world_context=world_context,
            recent_memories=recent_memories,
            runtime_ctx=runtime_ctx,
        )

    async def run_reflector(
        self,
        agent_id: str,
        agent_name: str,
        world_context: dict,
        daily_events: list[dict] | None = None,
        runtime_ctx: RuntimeContext | None = None,
    ) -> dict | None:
        if runtime_ctx and runtime_ctx.on_llm_call:
            runtime_ctx.on_llm_call(
                agent_id=agent_id,
                task_type="reflector",
                usage={"input_tokens": 234, "output_tokens": 56},
                total_cost_usd=0.02,
                duration_ms=654,
            )
        return await super().run_reflector(
            agent_id=agent_id,
            agent_name=agent_name,
            world_context=world_context,
            daily_events=daily_events,
            runtime_ctx=runtime_ctx,
        )


@pytest.mark.asyncio
async def test_day_boundary_memories_populate_subjective_fields():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id="run-day-boundary-memory",
            name="boundary",
            status="running",
            current_tick=0,
            tick_minutes=5,
        )
        location = Location(
            id="loc-boundary-home",
            run_id=run.id,
            name="Home",
            location_type="home",
            capacity=2,
        )
        agent = Agent(
            id="agent-boundary",
            run_id=run.id,
            name="Alice",
            occupation="resident",
            home_location_id=location.id,
            current_location_id=location.id,
            personality={},
            profile={},
            status={},
            current_plan={},
        )
        session.add_all([run, location, agent])
        await session.commit()

    class FakeWorld:
        def __init__(self, current_time: datetime, tick_minutes: int) -> None:
            self.current_time = current_time
            self.tick_minutes = tick_minutes

        def _time_period(self) -> str:
            return "morning" if self.current_time.hour < 12 else "night"

        def _weekday_name(self, weekday: int) -> str:
            return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][
                weekday
            ]

    runtime = FakeAgentRuntime()
    plans = await run_morning_planning(
        run_id="run-day-boundary-memory",
        tick_no=0,
        world=FakeWorld(datetime(2026, 3, 2, 6, 0, tzinfo=UTC), 5),
        engine=engine,
        agent_runtime=runtime,
    )
    await run_evening_reflection(
        run_id="run-day-boundary-memory",
        tick_no=10,
        world=FakeWorld(datetime(2026, 3, 2, 21, 55, tzinfo=UTC), 5),
        engine=engine,
        agent_runtime=runtime,
    )

    async with AsyncSession(engine, expire_on_commit=False) as session:
        result = await session.execute(
            select(Memory)
            .where(Memory.run_id == "run-day-boundary-memory")
            .order_by(Memory.tick_no.asc())
        )
        memories = result.scalars().all()

    await engine.dispose()

    assert plans == {"agent-boundary": {"morning": "commute", "daytime": "work", "evening": "rest"}}
    assert [memory.memory_type for memory in memories] == ["daily_plan", "daily_reflection"]
    for memory in memories:
        assert memory.memory_category == "long_term"
        assert memory.importance > 0
        assert memory.event_importance == memory.importance
        assert memory.self_relevance == 1.0
        assert memory.belief_confidence == 1.0


@pytest.mark.asyncio
async def test_morning_planning_persists_llm_calls():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id="run-day-boundary-planner-llm",
            name="planner-llm",
            status="running",
            current_tick=0,
            tick_minutes=5,
        )
        location = Location(
            id="loc-boundary-planner-home",
            run_id=run.id,
            name="Home",
            location_type="home",
            capacity=2,
        )
        agent = Agent(
            id="agent-boundary-planner",
            run_id=run.id,
            name="Alice",
            occupation="resident",
            home_location_id=location.id,
            current_location_id=location.id,
            personality={},
            profile={},
            status={},
            current_plan={},
        )
        session.add_all([run, location, agent])
        await session.commit()

    class FakeWorld:
        def __init__(self, current_time: datetime, tick_minutes: int) -> None:
            self.current_time = current_time
            self.tick_minutes = tick_minutes

        def _time_period(self) -> str:
            return "morning"

        def _weekday_name(self, weekday: int) -> str:
            return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][
                weekday
            ]

    await run_morning_planning(
        run_id="run-day-boundary-planner-llm",
        tick_no=0,
        world=FakeWorld(datetime(2026, 3, 2, 6, 0, tzinfo=UTC), 5),
        engine=engine,
        agent_runtime=FakeTrackingAgentRuntime(),
    )

    async with AsyncSession(engine, expire_on_commit=False) as session:
        result = await session.execute(
            select(LlmCall)
            .where(LlmCall.run_id == "run-day-boundary-planner-llm")
            .order_by(LlmCall.created_at.asc())
        )
        llm_calls = result.scalars().all()

    await engine.dispose()

    assert len(llm_calls) == 1
    assert llm_calls[0].task_type == "planner"
    assert llm_calls[0].input_tokens == 123
    assert llm_calls[0].output_tokens == 45
    assert llm_calls[0].duration_ms == 321


@pytest.mark.asyncio
async def test_morning_planning_rolls_back_current_plan_when_plan_memory_write_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id="run-day-boundary-plan-memory-fails",
            name="planner-memory-fails",
            status="running",
            current_tick=0,
            tick_minutes=5,
        )
        location = Location(
            id="loc-boundary-plan-memory-fails-home",
            run_id=run.id,
            name="Home",
            location_type="home",
            capacity=2,
        )
        agent = Agent(
            id="agent-boundary-plan-memory-fails",
            run_id=run.id,
            name="Alice",
            occupation="resident",
            home_location_id=location.id,
            current_location_id=location.id,
            personality={},
            profile={},
            status={},
            current_plan={},
        )
        session.add_all([run, location, agent])
        await session.commit()

    class FakeWorld:
        def __init__(self, current_time: datetime, tick_minutes: int) -> None:
            self.current_time = current_time
            self.tick_minutes = tick_minutes

        def _time_period(self) -> str:
            return "morning"

        def _weekday_name(self, weekday: int) -> str:
            return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][
                weekday
            ]

    async def fail_add_many(*_args, **_kwargs) -> None:
        raise RuntimeError("plan memory write failed")

    monkeypatch.setattr(day_boundary_module.MemoryRepository, "add_many", fail_add_many)

    with pytest.raises(RuntimeError, match="plan memory write failed"):
        await run_morning_planning(
            run_id="run-day-boundary-plan-memory-fails",
            tick_no=0,
            world=FakeWorld(datetime(2026, 3, 2, 6, 0, tzinfo=UTC), 5),
            engine=engine,
            agent_runtime=FakeAgentRuntime(),
        )

    async with AsyncSession(engine, expire_on_commit=False) as session:
        agent = await session.get(Agent, "agent-boundary-plan-memory-fails")
        result = await session.execute(
            select(Memory).where(Memory.run_id == "run-day-boundary-plan-memory-fails")
        )
        memories = result.scalars().all()

    await engine.dispose()

    assert agent is not None
    assert agent.current_plan == {}
    assert memories == []


@pytest.mark.asyncio
async def test_evening_reflection_persists_llm_calls():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id="run-day-boundary-reflector-llm",
            name="reflector-llm",
            status="running",
            current_tick=0,
            tick_minutes=5,
        )
        location = Location(
            id="loc-boundary-reflector-home",
            run_id=run.id,
            name="Home",
            location_type="home",
            capacity=2,
        )
        agent = Agent(
            id="agent-boundary-reflector",
            run_id=run.id,
            name="Alice",
            occupation="resident",
            home_location_id=location.id,
            current_location_id=location.id,
            personality={},
            profile={},
            status={},
            current_plan={},
        )
        session.add_all([run, location, agent])
        await session.commit()

    class FakeWorld:
        def __init__(self, current_time: datetime, tick_minutes: int) -> None:
            self.current_time = current_time
            self.tick_minutes = tick_minutes

        def _time_period(self) -> str:
            return "night"

        def _weekday_name(self, weekday: int) -> str:
            return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][
                weekday
            ]

    await run_evening_reflection(
        run_id="run-day-boundary-reflector-llm",
        tick_no=10,
        world=FakeWorld(datetime(2026, 3, 2, 21, 55, tzinfo=UTC), 5),
        engine=engine,
        agent_runtime=FakeTrackingAgentRuntime(),
    )

    async with AsyncSession(engine, expire_on_commit=False) as session:
        result = await session.execute(
            select(LlmCall)
            .where(LlmCall.run_id == "run-day-boundary-reflector-llm")
            .order_by(LlmCall.created_at.asc())
        )
        llm_calls = result.scalars().all()

    await engine.dispose()

    assert len(llm_calls) == 1
    assert llm_calls[0].task_type == "reflector"
    assert llm_calls[0].input_tokens == 234
    assert llm_calls[0].output_tokens == 56
    assert llm_calls[0].duration_ms == 654


@pytest.mark.asyncio
async def test_evening_reflection_promotes_eligible_memories():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id="run-day-boundary-promote",
            name="boundary",
            status="running",
            current_tick=0,
            tick_minutes=5,
        )
        location = Location(
            id="loc-boundary-promote-home",
            run_id=run.id,
            name="Home",
            location_type="home",
            capacity=2,
        )
        agent = Agent(
            id="agent-promote",
            run_id=run.id,
            name="Alice",
            occupation="resident",
            home_location_id=location.id,
            current_location_id=location.id,
            personality={},
            profile={},
            status={},
            current_plan={},
        )
        short_routine = Memory(
            id="mem-short-routine",
            run_id=run.id,
            agent_id=agent.id,
            tick_no=6,
            last_tick_no=6,
            memory_type="episodic_short",
            memory_category="short_term",
            content="Worked during 3 consecutive ticks.",
            summary="Worked",
            importance=0.37,
            event_importance=0.2,
            self_relevance=0.8,
            streak_count=3,
            location_id=location.id,
            metadata_json={"event_type": "work"},
        )
        medium_memory = Memory(
            id="mem-medium",
            run_id=run.id,
            agent_id=agent.id,
            tick_no=8,
            last_tick_no=8,
            memory_type="episodic_short",
            memory_category="medium_term",
            content="Talked with Bob about the missing file.",
            summary="Talked with Bob: missing file",
            importance=0.78,
            event_importance=0.67,
            self_relevance=0.8,
            streak_count=1,
            retrieval_count=3,
            location_id=location.id,
            metadata_json={"event_type": "talk"},
        )
        session.add_all([run, location, agent, short_routine, medium_memory])
        await session.commit()

    class FakeWorld:
        def __init__(self, current_time: datetime, tick_minutes: int) -> None:
            self.current_time = current_time
            self.tick_minutes = tick_minutes

        def _time_period(self) -> str:
            return "night"

        def _weekday_name(self, weekday: int) -> str:
            return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][
                weekday
            ]

    runtime = FakeAgentRuntime()
    await run_evening_reflection(
        run_id="run-day-boundary-promote",
        tick_no=20,
        world=FakeWorld(datetime(2026, 3, 2, 21, 55, tzinfo=UTC), 5),
        engine=engine,
        agent_runtime=runtime,
    )

    async with AsyncSession(engine, expire_on_commit=False) as session:
        result = await session.execute(
            select(Memory)
            .where(Memory.run_id == "run-day-boundary-promote")
            .order_by(Memory.id.asc())
        )
        memories = {memory.id: memory for memory in result.scalars().all()}

    await engine.dispose()

    assert memories["mem-short-routine"].memory_category == "medium_term"
    assert memories["mem-medium"].memory_category == "long_term"
    assert memories["mem-medium"].consolidated_at is not None


@pytest.mark.asyncio
async def test_evening_reflection_rolls_back_reflection_memory_when_promotion_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id="run-day-boundary-promotion-fails",
            name="boundary",
            status="running",
            current_tick=0,
            tick_minutes=5,
        )
        location = Location(
            id="loc-boundary-promotion-fails-home",
            run_id=run.id,
            name="Home",
            location_type="home",
            capacity=2,
        )
        agent = Agent(
            id="agent-promotion-fails",
            run_id=run.id,
            name="Alice",
            occupation="resident",
            home_location_id=location.id,
            current_location_id=location.id,
            personality={},
            profile={},
            status={},
            current_plan={},
        )
        session.add_all([run, location, agent])
        await session.commit()

    class FakeWorld:
        def __init__(self, current_time: datetime, tick_minutes: int) -> None:
            self.current_time = current_time
            self.tick_minutes = tick_minutes

        def _time_period(self) -> str:
            return "night"

        def _weekday_name(self, weekday: int) -> str:
            return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][
                weekday
            ]

    async def fail_promotion(*_args, **_kwargs) -> None:
        raise RuntimeError("promotion failed")

    monkeypatch.setattr(
        day_boundary_module,
        "_promote_memories_after_reflection",
        fail_promotion,
    )

    with pytest.raises(RuntimeError, match="promotion failed"):
        await run_evening_reflection(
            run_id="run-day-boundary-promotion-fails",
            tick_no=20,
            world=FakeWorld(datetime(2026, 3, 2, 21, 55, tzinfo=UTC), 5),
            engine=engine,
            agent_runtime=FakeAgentRuntime(),
        )

    async with AsyncSession(engine, expire_on_commit=False) as session:
        result = await session.execute(
            select(Memory).where(Memory.run_id == "run-day-boundary-promotion-fails")
        )
        memories = result.scalars().all()

    await engine.dispose()

    assert memories == []


@pytest.mark.asyncio
async def test_load_morning_inputs_uses_previous_day_tick_window():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ticks_per_day = 288
    current_tick = ticks_per_day * 3

    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id="run-yesterday-window",
            name="boundary",
            status="running",
            current_tick=current_tick,
            tick_minutes=5,
        )
        agent = Agent(
            id="agent-window",
            run_id=run.id,
            name="Alice",
            occupation="resident",
            home_location_id="loc-home",
            current_location_id="loc-home",
            personality={},
            profile={},
            status={},
            current_plan={},
        )
        plan_memory = Memory(
            id="mem-plan-window",
            run_id=run.id,
            agent_id=agent.id,
            tick_no=current_tick - 1,
            memory_type="daily_plan",
            memory_category="long_term",
            content="今日计划：早晨=工作，白天=散步，傍晚=休息。",
            summary="昨日计划",
            importance=0.6,
            event_importance=0.6,
            self_relevance=1.0,
            belief_confidence=1.0,
            metadata_json={"day": "2026-03-03"},
        )
        session.add_all(
            [
                run,
                agent,
                plan_memory,
                Event(
                    id="ev-old-window",
                    run_id=run.id,
                    tick_no=ticks_per_day + 12,
                    event_type="speech",
                    actor_agent_id=agent.id,
                    payload={},
                ),
                Event(
                    id="ev-yesterday-1",
                    run_id=run.id,
                    tick_no=(ticks_per_day * 2) + 12,
                    event_type="speech",
                    actor_agent_id=agent.id,
                    payload={},
                ),
                Event(
                    id="ev-yesterday-2",
                    run_id=run.id,
                    tick_no=(ticks_per_day * 2) + 24,
                    event_type="move",
                    actor_agent_id=agent.id,
                    payload={},
                ),
            ]
        )
        await session.commit()

        _pending, _memories, yesterday_by_agent = await _load_morning_inputs(
            session,
            run_id=run.id,
            agents=[agent],
            today=datetime(2026, 3, 4, tzinfo=UTC).date(),
            current_tick=current_tick,
            ticks_per_day=ticks_per_day,
        )
        summary = yesterday_by_agent[agent.id]

    await engine.dispose()

    assert "socialize1次" in summary
    assert "move1次" in summary
    assert "socialize2次" not in summary
