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
    agent_recent_events = await build_agent_recent_events(
        session=session,
        run_id=run_id,
        agents=agents,
        agent_states=agent_states,
        location_states=location_states,
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
            )
        )

    return agent_data
