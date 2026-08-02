from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.scenario.bundle_registry import resolve_sleep_config_for_scenario
from app.sim.agent_snapshot_builder import build_agent_relationship_contexts, build_agent_snapshots
from app.sim.context import get_run_world_effects, get_run_world_time, load_active_conversations
from app.sim.location_utils import resolve_agent_location_id
from app.sim.movement import AgentMovementState
from app.sim.activity import ActivityInstance
from app.sim.types import AgentDecisionSnapshot
from app.sim.world import AgentState, LocationState, WorldState
from app.sim.world_map import build_authoritative_world_map
from app.store.repositories import (
    AgentRepository,
    EventRepository,
    LocationRepository,
    RunRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.director.types import DirectorPlan
    from app.scenario.base import Scenario
    from app.store.models import Agent, SimulationRun


@dataclass
class LoadedTickData:
    run: SimulationRun
    world: WorldState
    agent_data: list[AgentDecisionSnapshot]
    agents: list[Agent]
    director_plan: DirectorPlan | None = field(default=None)


async def load_tick_data(
    *,
    session: AsyncSession,
    run_id: str,
    scenario: Scenario,
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
            location_type=loc.location_type,
            x=loc.x,
            y=loc.y,
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
        profile = agent.profile or {}
        workplace_id = profile.get("workplace_location_id")

        movement = AgentMovementState.from_dict(agent.movement)
        activity = ActivityInstance.from_dict(agent.activity)
        agent_states[agent.id] = AgentState(
            id=agent.id,
            name=agent.name,
            location_id=location_id,
            status=agent.status or {},
            occupation=agent.occupation,
            workplace_id=workplace_id if isinstance(workplace_id, str) else None,
            movement=movement,
            activity=activity,
        )
        if movement is None and location_id in location_states:
            location_states[location_id].occupants.add(agent.id)

    agent_data, director_plan = await build_agent_snapshots(
        session=session,
        run_id=run_id,
        run=run,
        agents=agents,
        scenario=scenario,
        location_states=location_states,
        agent_states=agent_states,
    )
    relationship_contexts = await build_agent_relationship_contexts(
        session=session,
        run_id=run_id,
        agents=agents,
    )
    active_conversations = await load_active_conversations(
        event_repo=EventRepository(session),
        run_id=run_id,
        current_tick=run.current_tick or 0,
    )

    world = WorldState(
        current_time=get_run_world_time(run),
        current_tick=run.current_tick,
        tick_minutes=run.tick_minutes,
        locations=location_states,
        agents=agent_states,
        world_effects=get_run_world_effects(run),
        relationship_contexts=relationship_contexts,
        active_conversations=active_conversations,
        topology=build_authoritative_world_map(
            locations,
            scenario_id=run.scenario_type,
            run_id=run_id,
        ),
        **resolve_sleep_config_for_scenario(run.scenario_type),
    )

    return LoadedTickData(
        run=run,
        world=world,
        agent_data=agent_data,
        agents=agents,
        director_plan=director_plan,
    )
