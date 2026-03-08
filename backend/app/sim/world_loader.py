from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.sim.context import ContextBuilder, get_run_world_time
from app.sim.world import AgentState, LocationState, WorldState
from app.store.repositories import AgentRepository, LocationRepository, RunRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.scenario.base import Scenario
    from app.store.models import Agent, SimulationRun


@dataclass
class LoadedTickData:
    run: "SimulationRun"
    world: WorldState
    agent_data: list[dict[str, Any]]
    agents: list["Agent"]


def resolve_agent_location_id(
    *,
    current_location_id: str | None,
    home_location_id: str | None,
    location_states: dict[str, LocationState],
) -> str:
    location_id = current_location_id or home_location_id
    if location_id is not None:
        return location_id
    return next(iter(location_states.keys()), "unknown")


async def load_tick_data(
    *,
    session: "AsyncSession",
    run_id: str,
    scenario: "Scenario",
) -> LoadedTickData:
    run_repo = RunRepository(session)
    run = await run_repo.get(run_id)
    if run is None:
        msg = f"Run not found: {run_id}"
        raise ValueError(msg)

    location_repo = LocationRepository(session)
    agent_repo = AgentRepository(session)
    locations = await location_repo.list_for_run(run_id)
    agents = list(await agent_repo.list_for_run(run_id))

    location_states = {
        loc.id: LocationState(
            id=loc.id,
            name=loc.name,
            capacity=loc.capacity,
            occupants=set(),
        )
        for loc in locations
    }

    agent_states: dict[str, AgentState] = {}
    for agent in agents:
        location_id = resolve_agent_location_id(
            current_location_id=agent.current_location_id,
            home_location_id=agent.home_location_id,
            location_states=location_states,
        )

        agent_states[agent.id] = AgentState(
            id=agent.id,
            name=agent.name,
            location_id=location_id,
            status=agent.status or {},
        )
        if location_id in location_states:
            location_states[location_id].occupants.add(agent.id)

    context_builder = ContextBuilder(session)
    agent_recent_events: dict[str, list[dict[str, Any]]] = {}
    for agent in agents:
        recent_events = await agent_repo.list_recent_events(run_id, agent.id, limit=5)
        agent_recent_events[agent.id] = [
            context_builder.format_event_for_context(evt, agent_states, location_states)
            for evt in recent_events
        ]

    scenario_with_session = scenario.with_session(session)
    scenario_with_session.assess(
        run_id=run_id,
        current_tick=run.current_tick,
        agents=agents,
        events=[],
    )
    plan = await scenario_with_session.build_director_plan(run_id, agents)

    agent_data = []
    for agent in agents:
        location_id = resolve_agent_location_id(
            current_location_id=agent.current_location_id,
            home_location_id=agent.home_location_id,
            location_states=location_states,
        )
        profile = scenario_with_session.merge_agent_profile(agent, plan)
        agent_data.append(
            {
                "id": agent.id,
                "current_goal": agent.current_goal,
                "current_location_id": location_id,
                "home_location_id": agent.home_location_id,
                "profile": profile,
                "recent_events": agent_recent_events.get(agent.id, []),
            }
        )

    world = WorldState(
        current_time=get_run_world_time(run),
        tick_minutes=run.tick_minutes,
        locations=location_states,
        agents=agent_states,
    )

    return LoadedTickData(run=run, world=world, agent_data=agent_data, agents=agents)
