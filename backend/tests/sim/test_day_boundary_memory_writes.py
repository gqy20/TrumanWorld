from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.sim.day_boundary import run_evening_reflection, run_morning_planning
from app.store.models import Agent, Base, Location, Memory, SimulationRun


class FakeAgentRuntime:
    async def run_planner(
        self,
        agent_id: str,
        agent_name: str,
        world_context: dict,
        recent_memories: list[dict] | None = None,
        runtime_ctx=None,
    ) -> dict | None:
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
    await run_morning_planning(
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

    assert [memory.memory_type for memory in memories] == ["daily_plan", "daily_reflection"]
    for memory in memories:
        assert memory.memory_category == "long_term"
        assert memory.importance > 0
        assert memory.event_importance == memory.importance
        assert memory.self_relevance == 1.0
        assert memory.belief_confidence == 1.0
