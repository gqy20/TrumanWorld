from __future__ import annotations

import asyncio
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
    session: "AsyncSession",
    run_id: str,
    agents: list["Agent"],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """预加载所有 agent 的记忆数据到内存缓存。

    避免在 anyio task group 中创建 AsyncSession（greenlet 冲突问题）。
    每个 agent 的记忆缓存包含：
    - short_term: 短期记忆
    - medium_term: 中期记忆
    - long_term: 长期记忆
    - about_others: 关于其他 agent 的记忆
    """
    from collections import defaultdict

    from sqlalchemy import select
    from app.store.models import Memory, Agent

    # 加载所有 agent 的名称映射
    agents_result = await session.execute(
        select(Agent.id, Agent.name).where(Agent.run_id == run_id)
    )
    agent_names = {row.id: row.name for row in agents_result}

    async def _load_one_agent_memories(agent: "Agent") -> tuple[str, dict[str, Any]]:
        agent_id = agent.id
        result = await session.execute(
            select(Memory)
            .where(Memory.run_id == run_id, Memory.agent_id == agent_id)
            .order_by(Memory.created_at.desc())
            .limit(ALL_MEMORY_LIMIT)
        )
        memories = result.scalars().all()

        short_term: list[dict] = []
        medium_term: list[dict] = []
        long_term: list[dict] = []
        all_memories: list[dict] = []
        about_others: dict[str, list[dict]] = defaultdict(list)

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

        for mem in memories:
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
            if (
                mem.related_agent_id
                and (
                    len(about_others) < ABOUT_OTHER_AGENT_LIMIT
                    or mem.related_agent_id in about_others
                )
            ):
                if len(about_others[mem.related_agent_id]) >= ABOUT_OTHER_MEMORY_LIMIT:
                    continue
                about_others[mem.related_agent_id].append(mem_dict)

        return agent_id, {
            "short_term": short_term,
            "medium_term": medium_term,
            "long_term": long_term,
            "about_others": dict(about_others),
            "all": all_memories,
        }

    results = await asyncio.gather(*[_load_one_agent_memories(a) for a in agents])
    return dict(results)


async def build_agent_recent_events(
    *,
    session: "AsyncSession",
    run_id: str,
    agents: list["Agent"],
    agent_states: dict[str, "AgentState"],
    location_states: dict[str, "LocationState"],
) -> dict[str, list[dict[str, Any]]]:
    agent_repo = ContextBuilder(session).agent_repo
    context_builder = ContextBuilder(session)

    async def _load_one_agent_events(
        agent: "Agent",
    ) -> tuple[str, list[dict[str, Any]]]:
        include_director_system_events = get_world_role(agent.profile) == "cast"
        current_location_id = (
            agent_states[agent.id].location_id if agent.id in agent_states else None
        )
        recent_events = await agent_repo.list_recent_events(
            run_id,
            agent.id,
            limit=5,
            include_director_system_events=include_director_system_events,
            current_location_id=current_location_id,
        )
        return agent.id, [
            context_builder.format_event_for_context(evt, agent_states, location_states)
            for evt in recent_events
        ]

    results = await asyncio.gather(*[_load_one_agent_events(a) for a in agents])
    return dict(results)


async def build_agent_snapshots(
    *,
    session: "AsyncSession",
    run_id: str,
    run: "SimulationRun",
    agents: list["Agent"],
    scenario: "Scenario",
    location_states: dict[str, "LocationState"],
    agent_states: dict[str, "AgentState"],
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
