from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.sim.action_resolver import ActionIntent
from app.sim.runner import SimulationRunner, TickResult
from app.sim.world import AgentState, LocationState, WorldState
from app.store.repositories import (
    AgentRepository,
    EventRepository,
    LocationRepository,
    RunRepository,
    build_event,
)


class SimulationService:
    """Loads persisted state, executes one tick, and persists results."""

    def __init__(
        self,
        session: AsyncSession,
        agent_runtime: AgentRuntime | None = None,
        agents_root: Path | None = None,
    ) -> None:
        self.session = session
        self.run_repo = RunRepository(session)
        self.agent_repo = AgentRepository(session)
        self.location_repo = LocationRepository(session)
        self.event_repo = EventRepository(session)
        self.agent_runtime = agent_runtime or AgentRuntime(
            registry=AgentRegistry(agents_root or Path("../agents"))
        )

    async def run_tick(self, run_id: str, intents: list[ActionIntent] | None = None) -> TickResult:
        run = await self.run_repo.get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)

        world = await self._load_world(run_id, tick_minutes=run.tick_minutes)
        if not intents:
            intents = await self.prepare_tick_intents(run_id, world)
        runner = SimulationRunner(world)
        runner.tick_no = run.current_tick
        result = runner.tick(intents)

        await self._persist_agent_locations(run_id, world)
        await self.run_repo.update_tick(run, result.tick_no)
        await self._persist_tick_events(run_id, result)
        return result

    async def prepare_tick_intents(self, run_id: str, world: WorldState) -> list[ActionIntent]:
        agents = await self.agent_repo.list_for_run(run_id)
        intents: list[ActionIntent] = []

        for agent in agents:
            state = world.get_agent(agent.id)
            if state is None:
                continue

            nearby_agent_id = self._find_nearby_agent(world, agent.id, state.location_id)
            try:
                invocation = self.agent_runtime.prepare_reactor(
                    agent.id,
                    world={
                        "current_goal": agent.current_goal,
                        "current_location_id": state.location_id,
                        "home_location_id": agent.home_location_id,
                        "nearby_agent_id": nearby_agent_id,
                    },
                    memory={"recent": []},
                    event={},
                )
                intents.append(self.agent_runtime.derive_intent(invocation))
            except ValueError:
                intents.append(
                    self._fallback_intent(
                        agent_id=agent.id,
                        current_goal=agent.current_goal,
                        current_location_id=state.location_id,
                        home_location_id=agent.home_location_id,
                        nearby_agent_id=nearby_agent_id,
                    )
                )

        return intents

    async def inject_director_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict,
        location_id: str | None = None,
        importance: float = 0.5,
    ) -> None:
        run = await self.run_repo.get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)

        event = build_event(
            run_id=run_id,
            tick_no=run.current_tick,
            world_time=datetime.now(UTC).isoformat(),
            action_type=f"director_{event_type}",
            payload=payload,
            accepted=True,
        )
        event.location_id = location_id
        event.importance = importance
        event.visibility = "system"
        await self.event_repo.create(event)

    async def _load_world(self, run_id: str, tick_minutes: int) -> WorldState:
        locations = await self.location_repo.list_for_run(run_id)
        agents = await self.agent_repo.list_for_run(run_id)

        location_states = {
            location.id: LocationState(
                id=location.id,
                name=location.name,
                capacity=location.capacity,
                occupants=set(),
            )
            for location in locations
        }

        agent_states: dict[str, AgentState] = {}
        for agent in agents:
            location_id = agent.current_location_id or agent.home_location_id
            if location_id is None:
                location_id = next(iter(location_states.keys()), "unknown")

            agent_states[agent.id] = AgentState(
                id=agent.id,
                name=agent.name,
                location_id=location_id,
                status=agent.status or {},
            )
            if location_id in location_states:
                location_states[location_id].occupants.add(agent.id)

        return WorldState(
            current_time=datetime.now(UTC),
            tick_minutes=tick_minutes,
            locations=location_states,
            agents=agent_states,
        )

    async def _persist_agent_locations(self, run_id: str, world: WorldState) -> None:
        agents = await self.agent_repo.list_for_run(run_id)
        for agent in agents:
            state = world.get_agent(agent.id)
            if state is not None:
                agent.current_location_id = state.location_id
        await self.session.commit()

    async def _persist_tick_events(self, run_id: str, result: TickResult) -> None:
        events = [
            build_event(
                run_id=run_id,
                tick_no=result.tick_no,
                world_time=result.world_time,
                action_type=item.action_type,
                payload=item.event_payload,
                accepted=True,
            )
            for item in result.accepted
        ]
        events.extend(
            build_event(
                run_id=run_id,
                tick_no=result.tick_no,
                world_time=result.world_time,
                action_type=item.action_type,
                payload={"reason": item.reason, **item.event_payload},
                accepted=False,
            )
            for item in result.rejected
        )
        if events:
            await self.event_repo.create_many(events)

    def _find_nearby_agent(self, world: WorldState, agent_id: str, location_id: str) -> str | None:
        location = world.get_location(location_id)
        if location is None:
            return None

        for occupant_id in sorted(location.occupants):
            if occupant_id != agent_id:
                return occupant_id
        return None

    def _fallback_intent(
        self,
        agent_id: str,
        current_goal: str | None,
        current_location_id: str,
        home_location_id: str | None,
        nearby_agent_id: str | None,
    ) -> ActionIntent:
        if isinstance(current_goal, str) and current_goal.startswith("move:"):
            return ActionIntent(
                agent_id=agent_id,
                action_type="move",
                target_location_id=current_goal.split(":", 1)[1].strip(),
            )

        if current_goal == "talk" and nearby_agent_id:
            return ActionIntent(
                agent_id=agent_id,
                action_type="talk",
                target_agent_id=nearby_agent_id,
            )

        if current_goal == "go_home" and home_location_id and current_location_id != home_location_id:
            return ActionIntent(
                agent_id=agent_id,
                action_type="move",
                target_location_id=home_location_id,
            )

        if current_goal == "work":
            return ActionIntent(agent_id=agent_id, action_type="work")

        return ActionIntent(agent_id=agent_id, action_type="rest")
