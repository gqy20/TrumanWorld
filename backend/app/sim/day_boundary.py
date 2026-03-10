"""Day boundary tasks: morning planning and evening reflection.

Triggered once per day at the morning/night time-period transitions.
- morning (06:00): each agent runs the Planner to build today's plan
- night   (22:00): each agent runs the Reflector to write a day summary
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from app.infra.logging import get_logger
from app.store.models import Agent, Event, Memory
from app.store.repositories import AgentRepository, MemoryRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

    from app.agent.runtime import AgentRuntime
    from app.sim.world import WorldState

logger = get_logger(__name__)

# memory_type 常量
MEMORY_TYPE_DAILY_PLAN = "daily_plan"
MEMORY_TYPE_DAILY_REFLECTION = "daily_reflection"


# ── 触发检测 ─────────────────────────────────────────────────────────────────

def should_run_planner(world: "WorldState") -> bool:
    """Return True when the world just entered morning (06:00 hour)."""
    return world.current_time.hour == 6 and world.current_time.minute < world.tick_minutes


def should_run_reflector(world: "WorldState") -> bool:
    """Return True when the world just entered night (22:00 hour)."""
    return world.current_time.hour == 22 and world.current_time.minute < world.tick_minutes


async def has_plan_for_today(
    session: "AsyncSession",
    run_id: str,
    agent_id: str,
    today: date,
) -> bool:
    """Check whether a daily_plan memory already exists for this agent today."""
    result = await session.execute(
        select(Memory).where(
            Memory.run_id == run_id,
            Memory.agent_id == agent_id,
            Memory.memory_type == MEMORY_TYPE_DAILY_PLAN,
        )
    )
    for mem in result.scalars().all():
        meta = mem.metadata_json or {}
        if meta.get("day") == today.isoformat():
            return True
    return False


async def has_reflection_for_today(
    session: "AsyncSession",
    run_id: str,
    agent_id: str,
    today: date,
) -> bool:
    """Check whether a daily_reflection memory already exists for this agent today."""
    result = await session.execute(
        select(Memory).where(
            Memory.run_id == run_id,
            Memory.agent_id == agent_id,
            Memory.memory_type == MEMORY_TYPE_DAILY_REFLECTION,
        )
    )
    for mem in result.scalars().all():
        meta = mem.metadata_json or {}
        if meta.get("day") == today.isoformat():
            return True
    return False


# ── 上下文构建辅助 ────────────────────────────────────────────────────────────

def _build_basic_world_context(world: "WorldState") -> dict:
    """Build minimal world context dict for planner/reflector prompts."""
    weekday = world.current_time.weekday()
    return {
        "world_time": world.current_time.isoformat(),
        "time_period": world._time_period(),
        "weekday": world._weekday_name(weekday),
    }


async def _load_recent_memories(
    session: "AsyncSession",
    run_id: str,
    agent_id: str,
    limit: int = 5,
) -> list[dict]:
    """Load recent long_term memories for the agent as simple dicts."""
    result = await session.execute(
        select(Memory)
        .where(
            Memory.run_id == run_id,
            Memory.agent_id == agent_id,
            Memory.memory_category == "long_term",
        )
        .order_by(Memory.created_at.desc())
        .limit(limit)
    )
    return [
        {"content": m.content, "memory_type": m.memory_type, "tick_no": m.tick_no}
        for m in result.scalars().all()
    ]


async def _load_today_events(
    session: "AsyncSession",
    run_id: str,
    agent_id: str,
    tick_no: int,
    ticks_per_day: int,
) -> list[dict]:
    """Load events from today (last ticks_per_day ticks) for the agent."""
    from sqlalchemy import or_

    since_tick = max(0, tick_no - ticks_per_day)
    result = await session.execute(
        select(Event)
        .where(
            Event.run_id == run_id,
            Event.tick_no > since_tick,
            Event.tick_no <= tick_no,
            or_(
                Event.actor_agent_id == agent_id,
                Event.target_agent_id == agent_id,
            ),
        )
        .order_by(Event.tick_no.asc())
    )
    return [
        {
            "event_type": ev.event_type,
            "tick_no": ev.tick_no,
            "actor_agent_id": ev.actor_agent_id,
            "target_agent_id": ev.target_agent_id,
            "payload": ev.payload or {},
        }
        for ev in result.scalars().all()
    ]


# ── Planner 执行 ──────────────────────────────────────────────────────────────

async def run_morning_planning(
    *,
    run_id: str,
    tick_no: int,
    world: "WorldState",
    engine: "AsyncEngine",
    agent_runtime: "AgentRuntime",
) -> None:
    """Run the Planner for all agents at morning boundary and persist results."""
    from sqlalchemy.ext.asyncio import AsyncSession

    today = world.current_time.date()
    world_ctx = _build_basic_world_context(world)

    async with AsyncSession(engine, expire_on_commit=False) as read_session:
        agent_repo = AgentRepository(read_session)
        agents = list(await agent_repo.list_for_run(run_id))
        # Filter out agents that already have a plan today (idempotent)
        pending: list[Agent] = []
        for agent in agents:
            if not await has_plan_for_today(read_session, run_id, agent.id, today):
                pending.append(agent)
        # Pre-load recent memories outside of gather to avoid session conflicts
        memories_by_agent: dict[str, list[dict]] = {}
        for agent in pending:
            memories_by_agent[agent.id] = await _load_recent_memories(
                read_session, run_id, agent.id
            )

    if not pending:
        return

    logger.info(f"[day_boundary] Morning planning for {len(pending)} agents (run={run_id})")

    async def plan_one(agent: Agent) -> tuple[str, str, dict | None]:
        config_id = (agent.profile or {}).get("agent_config_id") or agent.id
        result = await agent_runtime.run_planner(
            agent_id=config_id,
            agent_name=agent.name,
            world_context={**world_ctx, "personality": agent.personality or {}},
            recent_memories=memories_by_agent.get(agent.id),
        )
        return agent.id, agent.name, result

    results = await asyncio.gather(*[plan_one(a) for a in pending], return_exceptions=True)

    async with AsyncSession(engine, expire_on_commit=False) as write_session:
        agent_repo = AgentRepository(write_session)
        memory_repo = MemoryRepository(write_session)
        memories_to_create: list[Memory] = []

        for res in results:
            if isinstance(res, Exception):
                logger.warning(f"[day_boundary] Planner error: {res}")
                continue
            agent_id, agent_name, plan = res
            if not plan:
                logger.debug(f"[day_boundary] Planner returned nothing for {agent_name}")
                continue

            # Extract intention text; keep rest of plan as current_plan
            intention = plan.pop("intention", "")
            new_plan = {k: v for k, v in plan.items() if k in ("morning", "daytime", "evening")}

            # Update agent.current_plan in DB
            agent_obj = await agent_repo.get(agent_id)
            if agent_obj is not None:
                agent_obj.current_plan = new_plan
                write_session.add(agent_obj)

            # Write a long_term memory recording the plan
            content = f"今日计划：早晨={new_plan.get('morning','?')}，白天={new_plan.get('daytime','?')}，傍晚={new_plan.get('evening','?')}。{intention}"
            memories_to_create.append(Memory(
                id=str(uuid4()),
                run_id=run_id,
                agent_id=agent_id,
                tick_no=tick_no,
                memory_type=MEMORY_TYPE_DAILY_PLAN,
                memory_category="long_term",
                content=content,
                summary=intention or f"今日计划已制定（{today.isoformat()}）",
                importance=0.6,
                metadata_json={"plan": new_plan, "intention": intention, "day": today.isoformat()},
            ))
            logger.info(f"[day_boundary] Plan for {agent_name}: {new_plan} | {intention}")

        if memories_to_create:
            await memory_repo.create_many(memories_to_create)
        await write_session.commit()


# ── Reflector 执行 ────────────────────────────────────────────────────────────

async def run_evening_reflection(
    *,
    run_id: str,
    tick_no: int,
    world: "WorldState",
    engine: "AsyncEngine",
    agent_runtime: "AgentRuntime",
) -> None:
    """Run the Reflector for all agents at night boundary and persist results."""
    from sqlalchemy.ext.asyncio import AsyncSession

    today = world.current_time.date()
    ticks_per_day = (24 * 60) // world.tick_minutes
    world_ctx = _build_basic_world_context(world)

    async with AsyncSession(engine, expire_on_commit=False) as read_session:
        agent_repo = AgentRepository(read_session)
        agents = list(await agent_repo.list_for_run(run_id))
        pending: list[Agent] = []
        for agent in agents:
            if not await has_reflection_for_today(read_session, run_id, agent.id, today):
                pending.append(agent)
        # Pre-load today's events per agent
        events_by_agent: dict[str, list[dict]] = {}
        for agent in pending:
            events_by_agent[agent.id] = await _load_today_events(
                read_session, run_id, agent.id, tick_no, ticks_per_day
            )

    if not pending:
        return

    logger.info(f"[day_boundary] Evening reflection for {len(pending)} agents (run={run_id})")

    async def reflect_one(agent: Agent) -> tuple[str, str, dict | None]:
        config_id = (agent.profile or {}).get("agent_config_id") or agent.id
        result = await agent_runtime.run_reflector(
            agent_id=config_id,
            agent_name=agent.name,
            world_context={**world_ctx, "personality": agent.personality or {}},
            daily_events=events_by_agent.get(agent.id),
        )
        return agent.id, agent.name, result

    results = await asyncio.gather(*[reflect_one(a) for a in pending], return_exceptions=True)

    async with AsyncSession(engine, expire_on_commit=False) as write_session:
        memory_repo = MemoryRepository(write_session)
        memories_to_create: list[Memory] = []

        for res in results:
            if isinstance(res, Exception):
                logger.warning(f"[day_boundary] Reflector error: {res}")
                continue
            agent_id, agent_name, reflection = res
            if not reflection:
                logger.debug(f"[day_boundary] Reflector returned nothing for {agent_name}")
                continue

            reflection_text = reflection.get("reflection", "")
            mood = reflection.get("mood", "neutral")
            key_person = reflection.get("key_person")
            tomorrow = reflection.get("tomorrow_intention", "")

            content = reflection_text or f"今天已结束。（{today.isoformat()}）"
            summary = tomorrow or f"今日总结（{today.isoformat()}）"

            memories_to_create.append(Memory(
                id=str(uuid4()),
                run_id=run_id,
                agent_id=agent_id,
                tick_no=tick_no,
                memory_type=MEMORY_TYPE_DAILY_REFLECTION,
                memory_category="long_term",
                content=content,
                summary=summary,
                importance=0.7,
                emotional_valence=_mood_to_valence(mood),
                metadata_json={
                    "mood": mood,
                    "key_person": key_person,
                    "tomorrow_intention": tomorrow,
                    "day": today.isoformat(),
                },
            ))
            logger.info(f"[day_boundary] Reflection for {agent_name}: mood={mood}, key={key_person}")

        if memories_to_create:
            await memory_repo.create_many(memories_to_create)
        await write_session.commit()


def _mood_to_valence(mood: str) -> float:
    """Map mood label to emotional_valence (-1 to 1)."""
    return {
        "happy": 0.8,
        "satisfied": 0.5,
        "neutral": 0.0,
        "tired": -0.2,
        "anxious": -0.5,
        "lonely": -0.6,
    }.get(mood, 0.0)
