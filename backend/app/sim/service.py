from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.providers import build_default_talk_message
from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.infra.settings import get_settings
from app.sim.action_resolver import ActionIntent
from app.sim.runner import SimulationRunner, TickResult
from app.sim.world import AgentState, LocationState, WorldState
from app.store.repositories import (
    AgentRepository,
    EventRepository,
    LocationRepository,
    MemoryRepository,
    RelationshipRepository,
    RunRepository,
    build_event,
)
from app.store.models import Agent, Event, Location, Memory

if TYPE_CHECKING:
    from app.infra.db import async_engine


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
        self.memory_repo = MemoryRepository(session)
        self.relationship_repo = RelationshipRepository(session)
        settings = get_settings()
        self.agent_runtime = agent_runtime or AgentRuntime(
            registry=AgentRegistry(agents_root or (settings.project_root / "agents"))
        )

    @classmethod
    def create_for_scheduler(cls, agent_runtime: AgentRuntime) -> "SimulationService":
        """Create a SimulationService instance for scheduler use.

        This factory method creates a service instance that is not bound
        to a specific database session. It should only be used with
        run_tick_isolated() method which manages its own sessions.
        """
        instance = cls.__new__(cls)
        instance.session = None  # type: ignore[assignment]
        instance.agent_runtime = agent_runtime
        return instance

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

    async def run_tick_isolated(
        self,
        run_id: str,
        engine: "async_engine",
        intents: list[ActionIntent] | None = None,
    ) -> TickResult:
        """Run a tick with isolated database sessions to avoid greenlet conflicts.

        This method separates database operations from SDK calls:
        1. Read phase: Load all needed data from database
        2. SDK phase: Call agent runtime (without active database session)
        3. Write phase: Persist results with a fresh database session

        This prevents conflicts between SQLAlchemy's greenlet mechanism and
        anyio's task groups used by claude_agent_sdk.
        """
        from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionType

        # Phase 1: Read all data needed for the tick
        async with AsyncSessionType(engine) as read_session:
            read_repo = RunRepository(read_session)
            run = await read_repo.get(run_id)
            if run is None:
                msg = f"Run not found: {run_id}"
                raise ValueError(msg)

            tick_minutes = run.tick_minutes
            current_tick = run.current_tick

            # Load locations and agents
            location_repo = LocationRepository(read_session)
            agent_repo = AgentRepository(read_session)
            locations = await location_repo.list_for_run(run_id)
            agents = await agent_repo.list_for_run(run_id)

            # Build world state (copy data before session closes)
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
            agent_data: list[dict] = []  # Store agent data for later use

            # First pass: build agent_states and location_states.occupants
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

            # Load recent events for all agents (after agent_states is built)
            agent_recent_events: dict[str, list[dict]] = {}
            for agent in agents:
                recent_events = await agent_repo.list_recent_events(run_id, agent.id, limit=5)
                agent_recent_events[agent.id] = [
                    self._format_event_for_context(evt, agent_states, location_states)
                    for evt in recent_events
                ]

            # Second pass: build agent_data
            for agent in agents:
                location_id = agent.current_location_id or agent.home_location_id
                if location_id is None:
                    location_id = next(iter(location_states.keys()), "unknown")

                agent_data.append(
                    {
                        "id": agent.id,
                        "current_goal": agent.current_goal,
                        "current_location_id": location_id,
                        "home_location_id": agent.home_location_id,
                        "profile": agent.profile or {},
                        "recent_events": agent_recent_events.get(agent.id, []),
                    }
                )

            world = WorldState(
                current_time=datetime.now(UTC),
                tick_minutes=tick_minutes,
                locations=location_states,
                agents=agent_states,
            )

        # Phase 2: Prepare intents (SDK calls happen here, no active session)
        if not intents:
            intents = await self._prepare_intents_from_data(world, agent_data, engine, run_id)

        # Run simulation logic
        runner = SimulationRunner(world)
        runner.tick_no = current_tick
        result = runner.tick(intents)

        # Phase 3: Persist results with a fresh session
        async with AsyncSessionType(engine, expire_on_commit=False) as write_session:
            await self._persist_results(write_session, run_id, result, world, current_tick + 1)

        return result

    async def _prepare_intents_from_data(
        self,
        world: WorldState,
        agent_data: list[dict],
        engine: "async_engine | None" = None,
        run_id: str | None = None,
    ) -> list[ActionIntent]:
        """Prepare intents from pre-loaded agent data.

        This method is called without an active database session,
        allowing SDK calls to use anyio without greenlet conflicts.

        Agent decisions are made in PARALLEL for performance.
        Memory tools are available via MCP if engine is provided.
        """
        import asyncio
        from app.agent.runtime import RuntimeContext

        async def decide_for_agent(agent_dict: dict) -> ActionIntent:
            """Make decision for a single agent."""
            agent_id = agent_dict["id"]
            state = world.get_agent(agent_id)
            if state is None:
                return None

            nearby_agent_id = self._find_nearby_agent(world, agent_id, state.location_id)
            profile = agent_dict.get("profile", {})
            runtime_agent_id = profile.get("agent_config_id") or agent_id

            # Build runtime context with memory tools support
            runtime_ctx = None
            if engine is not None and run_id is not None:
                runtime_ctx = RuntimeContext(
                    db_engine=engine,
                    run_id=run_id,
                    enable_memory_tools=True,
                )

            try:
                intent = await self.agent_runtime.react(
                    runtime_agent_id,
                    world={
                        "current_goal": agent_dict.get("current_goal"),
                        "current_location_id": agent_dict.get("current_location_id"),
                        "home_location_id": agent_dict.get("home_location_id"),
                        "nearby_agent_id": nearby_agent_id,
                    },
                    memory={"recent": []},  # Memory tools available via MCP
                    event={},
                    recent_events=agent_dict.get("recent_events", []),
                    runtime_ctx=runtime_ctx,
                )
                intent.agent_id = agent_id
                return intent
            except (RuntimeError, ValueError, asyncio.CancelledError):
                return self._fallback_intent(
                    agent_id=agent_id,
                    current_goal=agent_dict.get("current_goal"),
                    current_location_id=agent_dict.get("current_location_id"),
                    home_location_id=agent_dict.get("home_location_id"),
                    nearby_agent_id=nearby_agent_id,
                )

        # Execute all agent decisions in PARALLEL
        results = await asyncio.gather(*[decide_for_agent(a) for a in agent_data])

        # Filter out None results (agents without valid state)
        intents = [r for r in results if r is not None]
        return intents

    async def _persist_results(
        self,
        session: AsyncSession,
        run_id: str,
        result: TickResult,
        world: WorldState,
        new_tick: int,
    ) -> None:
        """Persist tick results using a fresh session."""
        run_repo = RunRepository(session)
        agent_repo = AgentRepository(session)

        # Update agent locations
        agents = await agent_repo.list_for_run(run_id)
        for agent in agents:
            state = world.get_agent(agent.id)
            if state is not None:
                agent.current_location_id = state.location_id
        await session.commit()

        # Update tick number
        run = await run_repo.get(run_id)
        if run:
            await run_repo.update_tick(run, new_tick)

        # Persist events
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
            event_repo = EventRepository(session)
            persisted = await event_repo.create_many(events)
            await self._persist_tick_memories_with_session(session, run_id, persisted)
            await self._persist_tick_relationships_with_session(session, run_id, persisted)

    async def _persist_tick_memories_with_session(
        self,
        session: AsyncSession,
        run_id: str,
        events: list[Event],
    ) -> None:
        """Persist memories using the provided session."""
        # Build agent name map for friendly memory content
        agent_repo = AgentRepository(session)
        agents = await agent_repo.list_for_run(run_id)
        agent_name_map = {a.id: a.name for a in agents}

        location_repo = LocationRepository(session)
        locations = await location_repo.list_for_run(run_id)
        location_name_map = {loc.id: loc.name for loc in locations}

        memories: list[Memory] = []
        for event in events:
            if event.event_type.endswith("_rejected") or event.actor_agent_id is None:
                continue

            for agent_id, content, summary, related_agent_id in self._build_memory_records(
                event, agent_name_map, location_name_map
            ):
                memories.append(
                    Memory(
                        id=str(uuid4()),
                        run_id=run_id,
                        agent_id=agent_id,
                        tick_no=event.tick_no,
                        memory_type="episodic_short",
                        memory_category="short_term",
                        content=content,
                        summary=summary,
                        importance=event.importance,
                        related_agent_id=related_agent_id,
                        location_id=event.location_id,
                        source_event_id=event.id,
                        metadata_json={"event_type": event.event_type},
                    )
                )

        if memories:
            memory_repo = MemoryRepository(session)
            await memory_repo.create_many(memories)

    async def _persist_tick_relationships_with_session(
        self,
        session: AsyncSession,
        run_id: str,
        events: list[Event],
    ) -> None:
        """Persist relationships using the provided session."""
        rel_repo = RelationshipRepository(session)
        for event in events:
            if event.event_type != "talk":
                continue
            if event.actor_agent_id is None or event.target_agent_id is None:
                continue

            await rel_repo.upsert_interaction(
                run_id=run_id,
                agent_id=event.actor_agent_id,
                other_agent_id=event.target_agent_id,
                familiarity_delta=0.1,
                trust_delta=0.05,
                affinity_delta=0.05,
            )
            await rel_repo.upsert_interaction(
                run_id=run_id,
                agent_id=event.target_agent_id,
                other_agent_id=event.actor_agent_id,
                familiarity_delta=0.1,
                trust_delta=0.05,
                affinity_delta=0.05,
            )

    async def prepare_tick_intents(self, run_id: str, world: WorldState) -> list[ActionIntent]:
        agents = await self.agent_repo.list_for_run(run_id)
        intents: list[ActionIntent] = []

        for agent in agents:
            state = world.get_agent(agent.id)
            if state is None:
                continue

            nearby_agent_id = self._find_nearby_agent(world, agent.id, state.location_id)
            runtime_agent_id = self._resolve_runtime_agent_id(agent)
            try:
                intent = await self.agent_runtime.react(
                    runtime_agent_id,
                    world={
                        "current_goal": agent.current_goal,
                        "current_location_id": state.location_id,
                        "home_location_id": agent.home_location_id,
                        "nearby_agent_id": nearby_agent_id,
                    },
                    memory={"recent": []},
                    event={},
                )
                intent.agent_id = agent.id
                intents.append(intent)
            except (RuntimeError, ValueError, asyncio.CancelledError):
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

    def _resolve_runtime_agent_id(self, agent: Agent) -> str:
        profile = agent.profile or {}
        configured_id = profile.get("agent_config_id")
        if isinstance(configured_id, str) and configured_id:
            return configured_id
        return agent.id

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

    async def seed_demo_run(self, run_id: str) -> None:
        run = await self.run_repo.get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)

        existing_agents = await self.agent_repo.list_for_run(run_id)
        if existing_agents:
            return

        plaza = Location(
            id=f"{run_id}-plaza",
            run_id=run_id,
            name="Town Plaza",
            location_type="plaza",
            capacity=8,
            x=0,
            y=0,
            attributes={"kind": "social"},
        )
        cafe = Location(
            id=f"{run_id}-cafe",
            run_id=run_id,
            name="Corner Cafe",
            location_type="cafe",
            capacity=6,
            x=1,
            y=0,
            attributes={"kind": "work"},
        )
        alice = Agent(
            id=f"{run_id}-alice",
            run_id=run_id,
            name="Alice",
            occupation="barista",
            home_location_id=f"{run_id}-cafe",
            current_location_id=f"{run_id}-cafe",
            current_goal="talk",
            personality={"openness": 0.7},
            profile={
                "bio": "Runs the cafe counter.",
                "agent_config_id": "alice",
            },
            status={"energy": 0.8},
            current_plan={"morning": "work"},
        )
        bob = Agent(
            id=f"{run_id}-bob",
            run_id=run_id,
            name="Bob",
            occupation="resident",
            home_location_id=f"{run_id}-plaza",
            current_location_id=f"{run_id}-cafe",
            current_goal="talk",
            personality={"agreeableness": 0.6},
            profile={
                "bio": "Stops by the cafe every morning.",
                "agent_config_id": "bob",
            },
            status={"energy": 0.7},
            current_plan={"morning": "socialize"},
        )

        self.session.add_all([plaza, cafe])
        await self.session.flush()
        self.session.add_all([alice, bob])
        await self.session.commit()

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
            persisted = await self.event_repo.create_many(events)
            await self._persist_tick_memories(run_id, persisted)
            await self._persist_tick_relationships(run_id, persisted)

    async def _persist_tick_memories(self, run_id: str, events: list[Event]) -> None:
        agent_name_map = {a.id: a.name for a in await self.agent_repo.list_for_run(run_id)}
        location_name_map = {
            loc.id: loc.name for loc in await self.location_repo.list_for_run(run_id)
        }
        memories: list[Memory] = []
        for event in events:
            if event.event_type.endswith("_rejected") or event.actor_agent_id is None:
                continue

            for agent_id, content, summary, related_agent_id in self._build_memory_records(
                event, agent_name_map, location_name_map
            ):
                memories.append(
                    Memory(
                        id=str(uuid4()),
                        run_id=run_id,
                        agent_id=agent_id,
                        tick_no=event.tick_no,
                        memory_type="episodic_short",
                        memory_category="short_term",
                        content=content,
                        summary=summary,
                        importance=event.importance,
                        related_agent_id=related_agent_id,
                        location_id=event.location_id,
                        source_event_id=event.id,
                        metadata_json={"event_type": event.event_type},
                    )
                )

        if memories:
            await self.memory_repo.create_many(memories)

    def _build_memory_records(
        self,
        event: Event,
        agent_name_map: dict[str, str] | None = None,
        location_name_map: dict[str, str] | None = None,
    ) -> list[tuple[str, str, str, str | None]]:
        payload = event.payload or {}
        _agents = agent_name_map or {}
        _locations = location_name_map or {}

        def agent_name(agent_id: str | None) -> str:
            if not agent_id:
                return "someone"
            return _agents.get(agent_id, agent_id)

        def location_name(loc_id: str | None) -> str:
            if not loc_id:
                return "unknown"
            return _locations.get(loc_id, loc_id)

        if event.event_type == "move":
            destination = location_name(str(payload.get("to_location_id", "")) or None)
            origin = location_name(str(payload.get("from_location_id", "")) or None)
            return [
                (
                    event.actor_agent_id,
                    f"Moved from {origin} to {destination}.",
                    f"Moved to {destination}",
                    None,
                )
            ]

        if event.event_type == "talk":
            target_id = str(payload.get("target_agent_id") or event.target_agent_id or "")
            loc_id = str(payload.get("location_id") or "")
            target = agent_name(target_id)
            actor = agent_name(event.actor_agent_id)
            loc = location_name(loc_id)
            message = payload.get("message", "")

            if message:
                actor_content = f'Talked with {target} at {loc}: "{message}"'
                actor_summary = (
                    f"Talked with {target}: {message[:30]}{'...' if len(message) > 30 else ''}"
                )
                target_content = f'{actor} said: "{message}"'
                target_summary = f"{actor} said: {message[:30]}{'...' if len(message) > 30 else ''}"
            else:
                actor_content = f"Talked with {target} at {loc}."
                actor_summary = f"Talked with {target}"
                target_content = f"Talked with {actor} at {loc}."
                target_summary = f"Talked with {actor}"

            records: list[tuple[str, str, str, str | None]] = [
                (event.actor_agent_id, actor_content, actor_summary, event.target_agent_id)
            ]
            if event.target_agent_id:
                records.append(
                    (event.target_agent_id, target_content, target_summary, event.actor_agent_id)
                )
            return records

        if event.event_type == "work":
            return [(event.actor_agent_id, "Worked during this tick.", "Worked", None)]

        if event.event_type == "rest":
            return [(event.actor_agent_id, "Rested during this tick.", "Rested", None)]

        return [
            (
                event.actor_agent_id,
                f"Experienced event {event.event_type}.",
                f"Event: {event.event_type}",
                event.target_agent_id,
            )
        ]

    async def _persist_tick_relationships(self, run_id: str, events: list[Event]) -> None:
        for event in events:
            if event.event_type != "talk":
                continue
            if event.actor_agent_id is None or event.target_agent_id is None:
                continue

            await self.relationship_repo.upsert_interaction(
                run_id=run_id,
                agent_id=event.actor_agent_id,
                other_agent_id=event.target_agent_id,
                familiarity_delta=0.1,
                trust_delta=0.05,
                affinity_delta=0.05,
            )
            await self.relationship_repo.upsert_interaction(
                run_id=run_id,
                agent_id=event.target_agent_id,
                other_agent_id=event.actor_agent_id,
                familiarity_delta=0.1,
                trust_delta=0.05,
                affinity_delta=0.05,
            )

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
                payload={"message": build_default_talk_message()},
            )

        if (
            current_goal == "go_home"
            and home_location_id
            and current_location_id != home_location_id
        ):
            return ActionIntent(
                agent_id=agent_id,
                action_type="move",
                target_location_id=home_location_id,
            )

        if current_goal == "work":
            return ActionIntent(agent_id=agent_id, action_type="work")

        return ActionIntent(agent_id=agent_id, action_type="rest")

    def _format_event_for_context(
        self,
        evt: Event,
        agent_states: dict[str, AgentState],
        location_states: dict[str, LocationState],
    ) -> dict:
        """Format an Event object for context injection."""
        result = {
            "event_type": evt.event_type,
            "tick_no": evt.tick_no,
        }

        # Add actor name
        if evt.actor_agent_id and evt.actor_agent_id in agent_states:
            result["actor_name"] = agent_states[evt.actor_agent_id].name
        else:
            result["actor_name"] = "某人"

        # Add target name for talk events
        if evt.target_agent_id and evt.target_agent_id in agent_states:
            result["target_name"] = agent_states[evt.target_agent_id].name

        # Add location name
        if evt.location_id and evt.location_id in location_states:
            result["location_name"] = location_states[evt.location_id].name

        # Add message for talk events
        payload = evt.payload or {}
        if "message" in payload:
            result["message"] = payload["message"]

        return result
