"""Day boundary tasks: morning planning and evening reflection.

Triggered once per day at the morning/night time-period transitions.
- morning (06:00): each agent runs the Planner to build today's plan
- night   (21:55): each agent runs the Reflector to write a day summary

Note: Reflector triggers at 21:55 instead of 22:00 to ensure it runs
before the sleep jump at 23:00 (see world.py advance_tick).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from app.infra.logging import get_logger
from app.sim.memory_constants import MemoryCategory, should_consolidate_memory
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


def should_run_planner(world: WorldState) -> bool:
    """Return True when the world just entered morning (06:00 hour)."""
    return world.current_time.hour == 6 and world.current_time.minute < world.tick_minutes


def should_run_reflector(world: WorldState) -> bool:
    """Return True right after the 21:55 reflection tick completes.

    Reflector is executed after a tick finishes, so the world clock has already
    advanced into the next slot. For the default 5-minute cadence, the "21:55"
    reflection tick is observed here as 22:00.
    """
    return world.current_time.hour == 22 and world.current_time.minute < world.tick_minutes


async def has_plan_for_today(
    session: AsyncSession,
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
    session: AsyncSession,
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


def _build_basic_world_context(world: WorldState) -> dict:
    """Build minimal world context dict for planner/reflector prompts."""
    weekday = world.current_time.weekday()
    return {
        "world_time": world.current_time.isoformat(),
        "time_period": world._time_period(),
        "weekday": world._weekday_name(weekday),
    }


async def _load_recent_memories(
    session: AsyncSession,
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


async def _load_yesterday_plan_execution(
    session: AsyncSession,
    run_id: str,
    agent_id: str,
    yesterday: date,
    current_tick: int,
    ticks_per_day: int,
) -> str:
    """Load yesterday's plan and actual execution, generate comparison summary.

    Returns a string describing:
    - Yesterday's plan (what was planned)
    - Yesterday's actual behavior (what actually happened)
    """

    # 1. Get yesterday's plan from daily_plan memory
    yesterday_str = yesterday.isoformat()
    result = await session.execute(
        select(Memory).where(
            Memory.run_id == run_id,
            Memory.agent_id == agent_id,
            Memory.memory_type == MEMORY_TYPE_DAILY_PLAN,
        )
    )
    plan_text = None
    for mem in result.scalars().all():
        meta = mem.metadata_json or {}
        if meta.get("day") == yesterday_str:
            # Extract plan from content like "今日计划：早晨=X，白天=Y，傍晚=Z。"
            plan_text = mem.content
            break

    if not plan_text:
        return ""  # No yesterday plan found

    # 2. Get yesterday's actual events relative to the current day boundary.
    yesterday_start_tick = max(0, current_tick - ticks_per_day)
    events_result = await session.execute(
        select(Event)
        .where(
            Event.run_id == run_id,
            Event.actor_agent_id == agent_id,
            Event.tick_no > yesterday_start_tick,
            Event.tick_no <= current_tick,
        )
        .order_by(Event.tick_no.asc())
    )
    yesterday_events = list(events_result.scalars().all())

    # 3. Analyze actual behavior
    action_counts: dict[str, int] = {}
    for evt in yesterday_events:
        action_type = evt.event_type
        if action_type in ("talk", "speech"):
            action_counts["socialize"] = action_counts.get("socialize", 0) + 1
        elif action_type == "work":
            action_counts["work"] = action_counts.get("work", 0) + 1
        elif action_type == "rest":
            action_counts["rest"] = action_counts.get("rest", 0) + 1
        elif action_type == "move":
            action_counts["move"] = action_counts.get("move", 0) + 1

    # 4. Generate comparison text
    if not yesterday_events:
        return f"昨日计划：{plan_text}\n昨日实际：未找到行为记录"

    actions_summary = "、".join([f"{k}{v}次" for k, v in action_counts.items()]) or "无"
    return f"昨日计划：{plan_text}\n昨日实际：{actions_summary}"


async def _load_today_events(
    session: AsyncSession,
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
    world: WorldState,
    engine: AsyncEngine,
    agent_runtime: AgentRuntime,
) -> None:
    """Run the Planner for all agents at morning boundary and persist results."""
    from datetime import timedelta

    from sqlalchemy.ext.asyncio import AsyncSession

    today = world.current_time.date()
    yesterday = today - timedelta(days=1)
    ticks_per_day = (24 * 60) // world.tick_minutes
    world_ctx = _build_basic_world_context(world)

    async with AsyncSession(engine, expire_on_commit=False) as read_session:
        agent_repo = AgentRepository(read_session)
        agents = list(await agent_repo.list_for_run(run_id))

        # 并行检查所有 agent 是否已有今日计划
        has_plan_results = await asyncio.gather(
            *[has_plan_for_today(read_session, run_id, a.id, today) for a in agents]
        )
        pending: list[Agent] = [
            a for a, already_planned in zip(agents, has_plan_results) if not already_planned
        ]

        # 并行预加载所有待处理 agent 的近期记忆
        memories_list = await asyncio.gather(
            *[_load_recent_memories(read_session, run_id, a.id) for a in pending]
        )
        memories_by_agent: dict[str, list[dict]] = {
            a.id: mems for a, mems in zip(pending, memories_list)
        }

        # 并行预加载昨日计划执行情况
        yesterday_execution_list = await asyncio.gather(
            *[
                _load_yesterday_plan_execution(
                    read_session,
                    run_id,
                    a.id,
                    yesterday,
                    tick_no,
                    ticks_per_day,
                )
                for a in pending
            ]
        )
        yesterday_execution_by_agent: dict[str, str] = {
            a.id: exec_text for a, exec_text in zip(pending, yesterday_execution_list)
        }

    if not pending:
        return

    logger.info(f"[day_boundary] Morning planning for {len(pending)} agents (run={run_id})")

    async def plan_one(agent: Agent) -> tuple[str, str, dict | None]:
        config_id = (agent.profile or {}).get("agent_config_id") or agent.id
        yesterday_execution = yesterday_execution_by_agent.get(agent.id, "")

        # 构建扩展的 world_context，包含昨日计划执行情况
        extended_ctx = {
            **world_ctx,
            "personality": agent.personality or {},
        }
        if yesterday_execution:
            extended_ctx["yesterday_plan_execution"] = yesterday_execution

        result = await agent_runtime.run_planner(
            agent_id=config_id,
            agent_name=agent.name,
            world_context=extended_ctx,
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
            content = f"今日计划：早晨={new_plan.get('morning', '?')}，白天={new_plan.get('daytime', '?')}，傍晚={new_plan.get('evening', '?')}。{intention}"
            memories_to_create.append(
                Memory(
                    id=str(uuid4()),
                    run_id=run_id,
                    agent_id=agent_id,
                    tick_no=tick_no,
                    memory_type=MEMORY_TYPE_DAILY_PLAN,
                    memory_category="long_term",
                    content=content,
                    summary=intention or f"今日计划已制定（{today.isoformat()}）",
                    importance=0.6,
                    event_importance=0.6,
                    self_relevance=1.0,
                    belief_confidence=1.0,
                    metadata_json={
                        "plan": new_plan,
                        "intention": intention,
                        "day": today.isoformat(),
                    },
                )
            )
            logger.info(f"[day_boundary] Plan for {agent_name}: {new_plan} | {intention}")

        if memories_to_create:
            await memory_repo.create_many(memories_to_create)
        await write_session.commit()


# ── Reflector 执行 ────────────────────────────────────────────────────────────


async def run_evening_reflection(
    *,
    run_id: str,
    tick_no: int,
    world: WorldState,
    engine: AsyncEngine,
    agent_runtime: AgentRuntime,
) -> None:
    """Run the Reflector for all agents at night boundary and persist results."""
    from sqlalchemy.ext.asyncio import AsyncSession

    today = world.current_time.date()
    ticks_per_day = (24 * 60) // world.tick_minutes
    world_ctx = _build_basic_world_context(world)

    async with AsyncSession(engine, expire_on_commit=False) as read_session:
        agent_repo = AgentRepository(read_session)
        agents = list(await agent_repo.list_for_run(run_id))

        # 并行检查所有 agent 是否已有今日反思
        has_reflection_results = await asyncio.gather(
            *[has_reflection_for_today(read_session, run_id, a.id, today) for a in agents]
        )
        pending: list[Agent] = [
            a
            for a, already_reflected in zip(agents, has_reflection_results)
            if not already_reflected
        ]

        # 并行预加载所有待处理 agent 的当日事件
        events_list = await asyncio.gather(
            *[
                _load_today_events(read_session, run_id, a.id, tick_no, ticks_per_day)
                for a in pending
            ]
        )
        events_by_agent: dict[str, list[dict]] = {
            a.id: evts for a, evts in zip(pending, events_list)
        }

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
            happy_event = reflection.get("happy_event", "")
            regret_event = reflection.get("regret_event", "")
            self_evaluation = reflection.get("self_evaluation", "")
            tomorrow = reflection.get("tomorrow_intention", "")

            # 构建更丰富的 content
            content_parts = [reflection_text]
            if happy_event:
                content_parts.append(f"\n最开心的事：{happy_event}")
            if regret_event:
                content_parts.append(f"\n最遗憾的事：{regret_event}")
            if self_evaluation:
                content_parts.append(f"\n自我评价：{self_evaluation}")
            content = "\n".join(content_parts) or f"今天已结束。（{today.isoformat()}）"

            summary = tomorrow or f"今日总结（{today.isoformat()}）"

            memories_to_create.append(
                Memory(
                    id=str(uuid4()),
                    run_id=run_id,
                    agent_id=agent_id,
                    tick_no=tick_no,
                    memory_type=MEMORY_TYPE_DAILY_REFLECTION,
                    memory_category="long_term",
                    content=content,
                    summary=summary,
                    importance=0.7,
                    event_importance=0.7,
                    self_relevance=1.0,
                    belief_confidence=1.0,
                    emotional_valence=_mood_to_valence(mood),
                    metadata_json={
                        "mood": mood,
                        "key_person": key_person,
                        "happy_event": happy_event,
                        "regret_event": regret_event,
                        "self_evaluation": self_evaluation,
                        "tomorrow_intention": tomorrow,
                        "day": today.isoformat(),
                    },
                )
            )
            logger.info(
                f"[day_boundary] Reflection for {agent_name}: mood={mood}, key={key_person}"
            )

        if memories_to_create:
            await memory_repo.create_many(memories_to_create)
        await _promote_memories_after_reflection(
            write_session,
            run_id=run_id,
            tick_no=tick_no,
            tick_minutes=world.tick_minutes,
        )
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


async def _promote_memories_after_reflection(
    session: AsyncSession,
    *,
    run_id: str,
    tick_no: int,
    tick_minutes: int,
) -> None:
    result = await session.execute(
        select(Memory).where(
            Memory.run_id == run_id,
            Memory.memory_type == "episodic_short",
            Memory.memory_category.in_([MemoryCategory.SHORT_TERM, MemoryCategory.MEDIUM_TERM]),
        )
    )
    memories = result.scalars().all()

    for memory in memories:
        current_category = memory.memory_category or MemoryCategory.SHORT_TERM
        if current_category == MemoryCategory.SHORT_TERM and (memory.streak_count or 1) >= 3:
            memory.memory_category = MemoryCategory.MEDIUM_TERM
            continue

        reference_tick = memory.last_tick_no or memory.tick_no or 0
        tick_age = max(0, tick_no - reference_tick)
        if should_consolidate_memory(
            current_category=current_category,
            importance=memory.importance or 0.0,
            access_count=memory.retrieval_count or 0,
            tick_age=tick_age,
            tick_minutes=tick_minutes,
        ):
            if current_category == MemoryCategory.SHORT_TERM:
                memory.memory_category = MemoryCategory.MEDIUM_TERM
            elif current_category == MemoryCategory.MEDIUM_TERM:
                memory.memory_category = MemoryCategory.LONG_TERM
                memory.consolidated_at = datetime.now(UTC)
