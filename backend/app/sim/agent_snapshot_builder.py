from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.scenario.truman_world.types import get_world_role
from app.sim.context import ContextBuilder
from app.sim.location_utils import resolve_agent_location_id
from app.sim.types import AgentDecisionSnapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.scenario.base import Scenario
    from app.store.models import Agent, SimulationRun

from app.sim.world import AgentState, LocationState


async def build_agent_memory_cache(
    *,
    session: "AsyncSession",
    run_id: str,
    agents: list["Agent"],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """预加载所有 agent 的记忆数据到内存缓存。

    避免在 anyio task group 中创建 AsyncSession（greenlet 冲突问题）。
    每个 agent 的记忆缓存包含：
    - short_term: 短期记忆（最近事件）
    - long_term: 长期记忆（重要事件）
    - about_others: 关于其他 agent 的记忆
    """
    from sqlalchemy import select
    from app.store.models import Memory, Agent

    # 加载所有 agent 的名称映射
    agents_result = await session.execute(select(Agent.id, Agent.name).where(Agent.run_id == run_id))
    agent_names = {row.id: row.name for row in agents_result}

    agent_memory_cache: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for agent in agents:
        agent_id = agent.id

        # 查询该 agent 的所有记忆
        result = await session.execute(
            select(Memory)
            .where(Memory.run_id == run_id, Memory.agent_id == agent_id)
            .order_by(Memory.created_at.desc())
        )
        memories = result.scalars().all()

        # 分类整理记忆
        short_term = []
        long_term = []
        about_others: dict[str, list[dict]] = {}  # key: other_agent_id

        for mem in memories:
            mem_dict = {
                "id": mem.id,
                "content": mem.content,
                "summary": mem.summary,
                "tick_no": mem.tick_no,
                "memory_type": mem.memory_type,
                "memory_category": mem.memory_category,
                "importance": mem.importance,
                "related_agent_id": mem.related_agent_id,
                "related_agent_name": agent_names.get(mem.related_agent_id),
                "location_id": mem.location_id,
            }

            if mem.memory_category == "short_term":
                short_term.append(mem_dict)
            else:
                long_term.append(mem_dict)

            # 按相关 agent 分类
            if mem.related_agent_id:
                if mem.related_agent_id not in about_others:
                    about_others[mem.related_agent_id] = []
                about_others[mem.related_agent_id].append(mem_dict)

        agent_memory_cache[agent_id] = {
            "short_term": short_term[:10],  # 限制数量，避免过大
            "long_term": long_term[:20],
            "about_others": about_others,
            "all": short_term[:10] + long_term[:20],  # 综合列表
        }

    return agent_memory_cache


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
    agent_recent_events: dict[str, list[dict[str, Any]]] = {}

    for agent in agents:
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
        agent_recent_events[agent.id] = [
            context_builder.format_event_for_context(evt, agent_states, location_states)
            for evt in recent_events
        ]

    return agent_recent_events


async def build_agent_snapshots(
    *,
    session: "AsyncSession",
    run_id: str,
    run: "SimulationRun",
    agents: list["Agent"],
    scenario: "Scenario",
    location_states: dict[str, "LocationState"],
    agent_states: dict[str, "AgentState"],
) -> list[AgentDecisionSnapshot]:
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
            )
        )

    return agent_data
