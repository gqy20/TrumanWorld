"""Day boundary tasks: morning planning and evening reflection.

Triggered once per day at the morning/night time-period transitions.
- morning (06:00): each agent runs the Planner to build today's plan
- night   (21:55): each agent runs the Reflector to write a day summary

Note: Reflector triggers at 21:55 instead of 22:00 to ensure it runs
before the sleep jump at 23:00 (see world.py advance_tick).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import func, or_, select

from app.agent.runtime import RuntimeContext
from app.cognition.heuristic.agent_backend import HeuristicAgentBackend
from app.infra.logging import get_logger
from app.infra.settings import get_settings
from app.sim.llm_call_collector import LlmCallCollector
from app.sim.llm_call_writer import LlmCallWriter
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


def _allows_day_boundary_failure_fallback(agent_runtime: AgentRuntime) -> bool:
    backend = getattr(agent_runtime, "backend", None)
    if backend is None:
        return True
    return isinstance(backend, HeuristicAgentBackend)


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


# ── 上下文构建辅助 ────────────────────────────────────────────────────────────


def _build_basic_world_context(world: WorldState) -> dict:
    """Build minimal world context dict for planner/reflector prompts."""
    weekday = world.current_time.weekday()
    return {
        "world_time": world.current_time.isoformat(),
        "time_period": world._time_period(),
        "weekday": world._weekday_name(weekday),
    }


async def _load_daily_memory_index(
    session: AsyncSession,
    *,
    run_id: str,
    agent_ids: list[str],
    memory_type: str,
    day_keys: set[str],
) -> dict[str, dict[str, Memory]]:
    if not agent_ids or not day_keys:
        return {}
    memory_day = Memory.metadata_json["day"].as_string()
    ranked_memories = (
        select(
            Memory.id.label("memory_id"),
            func.row_number()
            .over(
                partition_by=(Memory.agent_id, memory_day),
                order_by=(Memory.created_at.desc(), Memory.id.desc()),
            )
            .label("row_num"),
        )
        .where(
            Memory.run_id == run_id,
            Memory.agent_id.in_(agent_ids),
            Memory.memory_type == memory_type,
            memory_day.in_(sorted(day_keys)),
        )
        .subquery()
    )
    result = await session.execute(
        select(Memory)
        .join(ranked_memories, Memory.id == ranked_memories.c.memory_id)
        .where(ranked_memories.c.row_num == 1)
        .order_by(Memory.agent_id.asc(), Memory.created_at.desc())
    )
    index: dict[str, dict[str, Memory]] = {agent_id: {} for agent_id in agent_ids}
    for memory in result.scalars():
        day = (memory.metadata_json or {}).get("day")
        if isinstance(day, str):
            index[memory.agent_id].setdefault(day, memory)
    return index


async def _load_recent_memories_for_agents(
    session: AsyncSession,
    *,
    run_id: str,
    agent_ids: list[str],
    limit: int = 5,
) -> dict[str, list[dict]]:
    memories_by_agent: dict[str, list[dict]] = {agent_id: [] for agent_id in agent_ids}
    if not agent_ids:
        return memories_by_agent
    ranked_memories = (
        select(
            Memory.id.label("memory_id"),
            func.row_number()
            .over(partition_by=Memory.agent_id, order_by=Memory.created_at.desc())
            .label("row_num"),
        )
        .where(
            Memory.run_id == run_id,
            Memory.agent_id.in_(agent_ids),
            Memory.memory_category == "long_term",
        )
        .subquery()
    )
    result = await session.execute(
        select(Memory)
        .join(ranked_memories, Memory.id == ranked_memories.c.memory_id)
        .where(ranked_memories.c.row_num <= limit)
        .order_by(Memory.agent_id.asc(), Memory.created_at.desc())
    )
    for memory in result.scalars():
        memories_by_agent[memory.agent_id].append(
            {
                "content": memory.content,
                "memory_type": memory.memory_type,
                "tick_no": memory.tick_no,
            }
        )
    return memories_by_agent


async def _load_events_for_agents(
    session: AsyncSession,
    *,
    run_id: str,
    agent_ids: list[str],
    tick_from: int,
    tick_to: int,
    include_targets: bool,
) -> dict[str, list[Event]]:
    events_by_agent: dict[str, list[Event]] = {agent_id: [] for agent_id in agent_ids}
    if not agent_ids:
        return events_by_agent
    event_scope = Event.actor_agent_id.in_(agent_ids)
    if include_targets:
        event_scope = or_(event_scope, Event.target_agent_id.in_(agent_ids))
    result = await session.execute(
        select(Event)
        .where(
            Event.run_id == run_id,
            Event.tick_no > tick_from,
            Event.tick_no <= tick_to,
            event_scope,
        )
        .order_by(Event.tick_no.asc())
    )
    agent_id_set = set(agent_ids)
    for event in result.scalars():
        if event.actor_agent_id in agent_id_set:
            events_by_agent[event.actor_agent_id].append(event)
        if (
            include_targets
            and event.target_agent_id in agent_id_set
            and event.target_agent_id != event.actor_agent_id
        ):
            events_by_agent[event.target_agent_id].append(event)
    return events_by_agent


def _summarize_yesterday_execution(plan_text: str, events: list[Event]) -> str:
    if not events:
        return f"昨日计划：{plan_text}\n昨日实际：未找到行为记录"
    action_counts: dict[str, int] = {}
    for event in events:
        action_type = event.event_type
        if action_type in ("talk", "speech"):
            action_type = "socialize"
        if action_type in {"socialize", "work", "rest", "move"}:
            action_counts[action_type] = action_counts.get(action_type, 0) + 1
    actions_summary = (
        "、".join(f"{action}{count}次" for action, count in action_counts.items()) or "无"
    )
    return f"昨日计划：{plan_text}\n昨日实际：{actions_summary}"


def _serialize_reflection_event(event: Event) -> dict:
    return {
        "event_type": event.event_type,
        "tick_no": event.tick_no,
        "actor_agent_id": event.actor_agent_id,
        "target_agent_id": event.target_agent_id,
        "payload": event.payload or {},
    }


async def _load_morning_inputs(
    session: AsyncSession,
    *,
    run_id: str,
    agents: list[Agent],
    today: date,
    current_tick: int,
    ticks_per_day: int,
) -> tuple[list[Agent], dict[str, list[dict]], dict[str, str]]:
    agent_ids = [agent.id for agent in agents]
    today_key = today.isoformat()
    yesterday_key = (today - timedelta(days=1)).isoformat()
    plan_index = await _load_daily_memory_index(
        session,
        run_id=run_id,
        agent_ids=agent_ids,
        memory_type=MEMORY_TYPE_DAILY_PLAN,
        day_keys={today_key, yesterday_key},
    )
    pending = [agent for agent in agents if today_key not in plan_index.get(agent.id, {})]
    pending_ids = [agent.id for agent in pending]
    memories_by_agent = await _load_recent_memories_for_agents(
        session,
        run_id=run_id,
        agent_ids=pending_ids,
    )

    yesterday_plans = {
        agent_id: plan_index[agent_id][yesterday_key].content
        for agent_id in pending_ids
        if yesterday_key in plan_index.get(agent_id, {})
    }
    events_by_agent = await _load_events_for_agents(
        session,
        run_id=run_id,
        agent_ids=list(yesterday_plans),
        tick_from=max(0, current_tick - ticks_per_day),
        tick_to=current_tick,
        include_targets=False,
    )
    yesterday_execution_by_agent = {
        agent_id: _summarize_yesterday_execution(plan_text, events_by_agent[agent_id])
        for agent_id, plan_text in yesterday_plans.items()
    }
    return pending, memories_by_agent, yesterday_execution_by_agent


async def _load_evening_inputs(
    session: AsyncSession,
    *,
    run_id: str,
    agents: list[Agent],
    today: date,
    tick_no: int,
    ticks_per_day: int,
) -> tuple[list[Agent], dict[str, list[dict]]]:
    agent_ids = [agent.id for agent in agents]
    today_key = today.isoformat()
    reflection_index = await _load_daily_memory_index(
        session,
        run_id=run_id,
        agent_ids=agent_ids,
        memory_type=MEMORY_TYPE_DAILY_REFLECTION,
        day_keys={today_key},
    )
    pending = [agent for agent in agents if today_key not in reflection_index.get(agent.id, {})]
    pending_ids = [agent.id for agent in pending]
    events = await _load_events_for_agents(
        session,
        run_id=run_id,
        agent_ids=pending_ids,
        tick_from=max(0, tick_no - ticks_per_day),
        tick_to=tick_no,
        include_targets=True,
    )
    return pending, {
        agent_id: [_serialize_reflection_event(event) for event in agent_events]
        for agent_id, agent_events in events.items()
    }


# ── Planner 执行 ──────────────────────────────────────────────────────────────


async def run_morning_planning(
    *,
    run_id: str,
    tick_no: int,
    world: WorldState,
    engine: AsyncEngine,
    agent_runtime: AgentRuntime,
) -> dict[str, dict[str, str]]:
    """Run morning planning, persist it, and return plans for the current tick."""
    from sqlalchemy.ext.asyncio import AsyncSession

    today = world.current_time.date()
    ticks_per_day = (24 * 60) // world.tick_minutes
    world_ctx = _build_basic_world_context(world)

    async with AsyncSession(engine, expire_on_commit=False) as read_session:
        agent_repo = AgentRepository(read_session)
        agents = list(await agent_repo.list_for_run(run_id))
        pending, memories_by_agent, yesterday_execution_by_agent = await _load_morning_inputs(
            read_session,
            run_id=run_id,
            agents=agents,
            today=today,
            current_tick=tick_no,
            ticks_per_day=ticks_per_day,
        )

    if not pending:
        return {}

    logger.info(f"[day_boundary] Morning planning for {len(pending)} agents (run={run_id})")
    collector = LlmCallCollector()
    llm_call_writer = LlmCallWriter()
    settings = get_settings()

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
            runtime_ctx=RuntimeContext(
                db_engine=engine,
                run_id=run_id,
                enable_memory_tools=True,
                on_llm_call=collector.build_callback(
                    run_id=run_id,
                    db_agent_id=agent.id,
                    tick_no=tick_no,
                    provider=settings.llm_provider,
                    model=settings.llm_model,
                ),
            ),
        )
        return agent.id, agent.name, result

    results = await asyncio.gather(*[plan_one(a) for a in pending], return_exceptions=True)
    if not _allows_day_boundary_failure_fallback(agent_runtime):
        for res in results:
            if isinstance(res, Exception):
                raise res

    async with AsyncSession(engine, expire_on_commit=False) as write_session:
        agent_repo = AgentRepository(write_session)
        memory_repo = MemoryRepository(write_session)
        memories_to_create: list[Memory] = []
        plans_by_agent: dict[str, dict[str, str]] = {}
        agents_by_id = (
            {agent.id: agent for agent in await agent_repo.list_for_run(run_id)}
            if any(not isinstance(res, Exception) and res[2] for res in results)
            else {}
        )

        for res in results:
            if isinstance(res, Exception):
                logger.warning(f"[day_boundary] Planner error: {res}")
                continue
            agent_id, agent_name, plan = res
            if not plan:
                logger.debug(f"[day_boundary] Planner returned nothing for {agent_name}")
                continue

            # Extract intention text; keep rest of plan as current_plan
            intention = plan.get("intention", "")
            new_plan = {k: v for k, v in plan.items() if k in ("morning", "daytime", "evening")}

            # Update agent.current_plan in DB
            agent_obj = agents_by_id.get(agent_id)
            if agent_obj is not None:
                agent_obj.current_plan = new_plan
                write_session.add(agent_obj)
                plans_by_agent[agent_id] = new_plan

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
            await memory_repo.add_many(memories_to_create)
        await write_session.commit()

    await llm_call_writer.persist(
        run_id=run_id,
        llm_records=collector.records,
        engine=engine,
    )
    return plans_by_agent


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
        pending, events_by_agent = await _load_evening_inputs(
            read_session,
            run_id=run_id,
            agents=agents,
            today=today,
            tick_no=tick_no,
            ticks_per_day=ticks_per_day,
        )

    if not pending:
        return

    logger.info(f"[day_boundary] Evening reflection for {len(pending)} agents (run={run_id})")
    collector = LlmCallCollector()
    llm_call_writer = LlmCallWriter()
    settings = get_settings()

    async def reflect_one(agent: Agent) -> tuple[str, str, dict | None]:
        config_id = (agent.profile or {}).get("agent_config_id") or agent.id
        result = await agent_runtime.run_reflector(
            agent_id=config_id,
            agent_name=agent.name,
            world_context={**world_ctx, "personality": agent.personality or {}},
            daily_events=events_by_agent.get(agent.id),
            runtime_ctx=RuntimeContext(
                db_engine=engine,
                run_id=run_id,
                enable_memory_tools=True,
                on_llm_call=collector.build_callback(
                    run_id=run_id,
                    db_agent_id=agent.id,
                    tick_no=tick_no,
                    provider=settings.llm_provider,
                    model=settings.llm_model,
                ),
            ),
        )
        return agent.id, agent.name, result

    results = await asyncio.gather(*[reflect_one(a) for a in pending], return_exceptions=True)
    if not _allows_day_boundary_failure_fallback(agent_runtime):
        for res in results:
            if isinstance(res, Exception):
                raise res

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
            await memory_repo.add_many(memories_to_create)
        await _promote_memories_after_reflection(
            write_session,
            run_id=run_id,
            tick_no=tick_no,
            tick_minutes=world.tick_minutes,
        )
        await write_session.commit()

    await llm_call_writer.persist(
        run_id=run_id,
        llm_records=collector.records,
        engine=engine,
    )


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
