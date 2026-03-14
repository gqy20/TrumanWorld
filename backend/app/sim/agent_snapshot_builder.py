from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from app.scenario.types import get_world_role
from app.sim.context import ContextBuilder
from app.sim.location_utils import resolve_agent_location_id
from app.sim.types import AgentDecisionSnapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.scenario.base import Scenario
    from app.store.models import Agent, SimulationRun

from app.sim.world import AgentState, LocationState

SHORT_TERM_LIMIT = 8
MEDIUM_TERM_LIMIT = 10
LONG_TERM_LIMIT = 12
ALL_MEMORY_LIMIT = 24
ABOUT_OTHER_AGENT_LIMIT = 4
ABOUT_OTHER_MEMORY_LIMIT = 3
MEMORY_CONTENT_PREVIEW_LIMIT = 160


async def build_agent_memory_cache(
    *,
    session: AsyncSession,
    run_id: str,
    agents: list[Agent],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """预加载所有 agent 的记忆数据到内存缓存。

    避免在 anyio task group 中创建 AsyncSession（greenlet 冲突问题）。
    每个 agent 的记忆缓存包含：
    - short_term: 短期记忆
    - medium_term: 中期记忆
    - long_term: 长期记忆
    - about_others: 关于其他 agent 的记忆
    """
    from sqlalchemy import func, select

    from app.store.models import Memory

    agent_ids = [agent.id for agent in agents]
    if not agent_ids:
        return {}

    agent_names = {agent.id: agent.name for agent in agents}
    ranked_memories = (
        select(
            Memory.id.label("memory_id"),
            func.row_number()
            .over(partition_by=Memory.agent_id, order_by=Memory.created_at.desc())
            .label("row_num"),
        )
        .where(Memory.run_id == run_id, Memory.agent_id.in_(agent_ids))
        .subquery()
    )
    result = await session.execute(
        select(Memory)
        .join(ranked_memories, Memory.id == ranked_memories.c.memory_id)
        .where(ranked_memories.c.row_num <= ALL_MEMORY_LIMIT)
        .order_by(Memory.agent_id.asc(), Memory.created_at.desc())
    )
    memories_by_agent: dict[str, list[Memory]] = {agent_id: [] for agent_id in agent_ids}
    for memory in result.scalars():
        memories_by_agent.setdefault(memory.agent_id, []).append(memory)

    def _serialize_memory(mem: Memory) -> dict[str, Any]:
        content = mem.content or ""
        if len(content) > MEMORY_CONTENT_PREVIEW_LIMIT:
            content = f"{content[:MEMORY_CONTENT_PREVIEW_LIMIT]}..."
        return {
            "id": mem.id,
            "content": content,
            "summary": mem.summary,
            "tick_no": mem.tick_no,
            "memory_type": mem.memory_type,
            "memory_category": mem.memory_category,
            "importance": mem.importance,
            "event_importance": mem.event_importance,
            "self_relevance": mem.self_relevance,
            "related_agent_id": mem.related_agent_id,
            "related_agent_name": agent_names.get(mem.related_agent_id),
            "location_id": mem.location_id,
        }

    cache: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for agent_id in agent_ids:
        short_term: list[dict[str, Any]] = []
        medium_term: list[dict[str, Any]] = []
        long_term: list[dict[str, Any]] = []
        all_memories: list[dict[str, Any]] = []
        about_others: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for mem in memories_by_agent.get(agent_id, []):
            mem_dict = _serialize_memory(mem)
            all_memories.append(mem_dict)
            if mem.memory_category == "short_term":
                if len(short_term) < SHORT_TERM_LIMIT:
                    short_term.append(mem_dict)
            elif mem.memory_category == "medium_term":
                if len(medium_term) < MEDIUM_TERM_LIMIT:
                    medium_term.append(mem_dict)
            elif len(long_term) < LONG_TERM_LIMIT:
                long_term.append(mem_dict)
            if mem.related_agent_id and (
                len(about_others) < ABOUT_OTHER_AGENT_LIMIT or mem.related_agent_id in about_others
            ):
                if len(about_others[mem.related_agent_id]) >= ABOUT_OTHER_MEMORY_LIMIT:
                    continue
                about_others[mem.related_agent_id].append(mem_dict)

        cache[agent_id] = {
            "short_term": short_term,
            "medium_term": medium_term,
            "long_term": long_term,
            "about_others": dict(about_others),
            "all": all_memories,
        }

    return cache


async def build_agent_recent_events(
    *,
    session: AsyncSession,
    run_id: str,
    agents: list[Agent],
    agent_states: dict[str, AgentState],
    location_states: dict[str, LocationState],
) -> dict[str, list[dict[str, Any]]]:
    context_builder = ContextBuilder(session)
    from collections import defaultdict

    from sqlalchemy import and_, case, func, literal, or_, select, union_all

    from app.store.models import Event

    if not agents:
        return {}

    agent_rows = []
    for agent in agents:
        include_director_system_events = get_world_role(agent.profile) == "cast"
        current_location_id = (
            agent_states[agent.id].location_id if agent.id in agent_states else None
        )
        agent_rows.append(
            select(
                literal(agent.id).label("agent_id"),
                literal(current_location_id).label("current_location_id"),
                literal(include_director_system_events).label("include_director_system_events"),
            )
        )

    agent_inputs = union_all(*agent_rows).cte("agent_inputs")
    event_priority = case(
        (
            Event.event_type.in_(
                ["talk", "speech", "listen", "conversation_started", "conversation_joined", "move"]
            ),
            0,
        ),
        (Event.event_type.in_(["work", "rest"]), 2),
        else_=1,
    )
    ranked_events = (
        select(
            agent_inputs.c.agent_id.label("for_agent_id"),
            Event.id.label("event_id"),
            func.row_number()
            .over(
                partition_by=agent_inputs.c.agent_id,
                order_by=(event_priority, Event.tick_no.desc(), Event.created_at.desc()),
            )
            .label("row_num"),
        )
        .select_from(Event)
        .join(
            agent_inputs,
            and_(
                Event.run_id == run_id,
                or_(
                    Event.actor_agent_id == agent_inputs.c.agent_id,
                    Event.target_agent_id == agent_inputs.c.agent_id,
                    and_(
                        agent_inputs.c.current_location_id.is_not(None),
                        Event.location_id == agent_inputs.c.current_location_id,
                        Event.actor_agent_id != agent_inputs.c.agent_id,
                        Event.target_agent_id != agent_inputs.c.agent_id,
                    ),
                    and_(
                        agent_inputs.c.include_director_system_events.is_(True),
                        Event.visibility == "system",
                        Event.event_type.startswith("director_"),
                    ),
                ),
            ),
        )
        .subquery()
    )

    result = await session.execute(
        select(ranked_events.c.for_agent_id, Event)
        .join(Event, Event.id == ranked_events.c.event_id)
        .where(ranked_events.c.row_num <= 5)
        .order_by(ranked_events.c.for_agent_id.asc(), ranked_events.c.row_num.asc())
    )

    grouped_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for for_agent_id, event in result.all():
        grouped_events[for_agent_id].append(
            context_builder.format_event_for_context(event, agent_states, location_states)
        )

    return {agent.id: grouped_events.get(agent.id, []) for agent in agents}


async def build_agent_snapshots(
    *,
    session: AsyncSession,
    run_id: str,
    run: SimulationRun,
    agents: list[Agent],
    scenario: Scenario,
    location_states: dict[str, LocationState],
    agent_states: dict[str, AgentState],
) -> tuple[list[AgentDecisionSnapshot], Any]:
    """Build per-agent decision snapshots.

    Returns a tuple of (agent_data, director_plan).
    director_plan is the plan returned by scenario.build_director_plan(),
    which must NOT be persisted here (read_session context).
    Persistence is the caller's responsibility in the write_session phase.
    """
    # Phase 1: 预加载所有需要的数据（在 read_session 中完成）
    agent_recent_events = await build_agent_recent_events(
        session=session,
        run_id=run_id,
        agents=agents,
        agent_states=agent_states,
        location_states=location_states,
    )

    # 预加载记忆数据到内存缓存（避免在 anyio task 中创建 DB session）
    agent_memory_cache = await build_agent_memory_cache(
        session=session,
        run_id=run_id,
        agents=agents,
    )

    scenario_with_session = scenario.with_session(session)
    scenario_with_session.assess(
        run_id=run_id,
        current_tick=run.current_tick,
        agents=agents,
        events=[],
    )
    plan = await scenario_with_session.build_director_plan(run_id, agents)

    agent_data: list[AgentDecisionSnapshot] = []
    for agent in agents:
        location_id = resolve_agent_location_id(
            current_location_id=agent.current_location_id,
            home_location_id=agent.home_location_id,
            location_states=location_states,
        )
        profile = scenario_with_session.merge_agent_profile(agent, plan)
        agent_data.append(
            AgentDecisionSnapshot(
                id=agent.id,
                current_goal=agent.current_goal,
                current_location_id=location_id,
                home_location_id=agent.home_location_id,
                profile=profile,
                recent_events=agent_recent_events.get(agent.id, []),
                memory_cache=agent_memory_cache.get(agent.id),
                current_plan=agent.current_plan or None,
            )
        )

    return agent_data, plan
