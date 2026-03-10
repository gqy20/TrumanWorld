"""Simulation service for running ticks and managing world state.

This module provides the main SimulationService class that orchestrates
simulation ticks, agent decisions, and persistence.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.providers import (
    build_default_talk_message,
)
from app.protocol.simulation import build_director_event_type
from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.director.manual_planner import ManualDirectorPlanner
from app.director.observer import DirectorAssessment
from app.infra.settings import get_settings
from app.scenario.base import Scenario
from app.scenario.open_world.scenario import OpenWorldScenario
from app.scenario.truman_world.scenario import TrumanWorldScenario
from app.scenario.types import (
    get_agent_config_id,
    get_world_role,
)
from app.scenario.truman_world.types import (
    DirectorGuidance,
    get_director_guidance,
)
from app.sim.action_resolver import ActionIntent
from app.sim.agent_snapshot_builder import build_agent_recent_events
from app.sim.context import ContextBuilder, get_run_world_time
from app.sim.event_utils import build_event
from app.sim.persistence import PersistenceManager
from app.sim.runtime_context_utils import (
    build_agent_world_context,
    extract_truman_suspicion_from_agent_data,
    inject_profile_fields_into_context,
)
from app.sim.runner import SimulationRunner, TickResult
from app.sim.types import AgentDecisionSnapshot
from app.sim.world import WorldState
from app.sim.world_loader import load_tick_data
from app.sim.world_queries import find_nearby_agent, get_agent
from app.store.repositories import (
    AgentRepository,
    DirectorMemoryRepository,
    EventRepository,
    LlmCallRepository,
    LocationRepository,
    RunRepository,
)
from app.store.models import Agent, SimulationRun
from app.store.models import LlmCall

if TYPE_CHECKING:
    from app.infra.db import async_engine


class SimulationService:
    """Loads persisted state, executes one tick, and persists results."""

    def __init__(
        self,
        session: AsyncSession,
        agent_runtime: AgentRuntime | None = None,
        agents_root: Path | None = None,
        scenario: Scenario | None = None,
    ) -> None:
        self.session = session
        self.run_repo = RunRepository(session)
        self.agent_repo = AgentRepository(session)
        self.location_repo = LocationRepository(session)
        self.event_repo = EventRepository(session)
        self.director_memory_repo = DirectorMemoryRepository(session)
        self._context_builder = ContextBuilder(session)
        self._persistence = PersistenceManager(session)
        # Track whether a scenario was explicitly injected (e.g. in tests).
        # When True, run_tick will NOT override _scenario based on run.scenario_type.
        self._injected_scenario: bool = scenario is not None
        self._scenario = (
            scenario.with_session(session)
            if scenario is not None
            else self.build_scenario("truman_world", session)
        )
        settings = get_settings()
        self.agent_runtime = agent_runtime or AgentRuntime(
            registry=AgentRegistry(agents_root or (settings.project_root / "agents"))
        )
        self._scenario.configure_runtime(self.agent_runtime)

    @staticmethod
    def build_scenario(
        scenario_type: str | None,
        session: AsyncSession | None = None,
    ) -> Scenario:
        if scenario_type == "open_world":
            return OpenWorldScenario(session)
        return TrumanWorldScenario(session)

    def _configure_scenario(self, scenario_type: str | None) -> Scenario:
        self._scenario = self.build_scenario(scenario_type, self.session)
        self._scenario.configure_runtime(self.agent_runtime)
        return self._scenario

    def _configure_scenario_for_run(self, run: SimulationRun) -> Scenario:
        # If a scenario was explicitly injected (e.g. in tests), honour it and
        # do not replace it with a freshly-built one based on run.scenario_type.
        if self._injected_scenario:
            return self._scenario
        return self._configure_scenario(run.scenario_type)

    @classmethod
    def create_for_scheduler(
        cls,
        agent_runtime: AgentRuntime,
        scenario: Scenario | None = None,
    ) -> "SimulationService":
        """Create a SimulationService instance for scheduler use.

        This factory method creates a service instance that is not bound
        to a specific database session. It should only be used with
        run_tick_isolated() method which manages its own sessions.
        """
        instance = cls.__new__(cls)
        instance.session = None  # type: ignore[assignment]
        instance.agent_runtime = agent_runtime
        instance._context_builder = None  # type: ignore[assignment]
        instance._persistence = None  # type: ignore[assignment]
        instance._scenario = (
            scenario.with_session(None)
            if scenario is not None
            else cls.build_scenario("truman_world")
        )
        instance._injected_scenario = scenario is not None
        instance._scenario.configure_runtime(agent_runtime)
        return instance

    async def run_tick(self, run_id: str, intents: list[ActionIntent] | None = None) -> TickResult:
        run = await self.run_repo.get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)
        self._configure_scenario_for_run(run)

        world = await self._load_world(run_id, tick_minutes=run.tick_minutes)
        if not intents:
            intents = await self.prepare_tick_intents(run_id, world)
        runner = SimulationRunner(world)
        runner.tick_no = run.current_tick
        result = runner.tick(intents)

        await self._persistence.persist_agent_locations(run_id, world)
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
            run = await read_session.get(SimulationRun, run_id)
            if run is None:
                msg = f"Run not found: {run_id}"
                raise ValueError(msg)
            scenario = self.build_scenario(run.scenario_type, read_session)
            scenario.configure_runtime(self.agent_runtime)
            loaded = await load_tick_data(
                session=read_session,
                run_id=run_id,
                scenario=scenario,
            )
            current_tick = loaded.run.current_tick
            world = loaded.world
            agent_data = loaded.agent_data
        self._scenario = self.build_scenario(run.scenario_type)
        self._scenario.configure_runtime(self.agent_runtime)

        # Phase 2: Prepare intents (SDK calls happen here, no active session)
        if not intents:
            intents, llm_records = await self._prepare_intents_from_data(world, agent_data, engine, run_id, current_tick)
        else:
            llm_records = []

        # Run simulation logic
        runner = SimulationRunner(world)
        runner.tick_no = current_tick
        result = runner.tick(intents)

        # Phase 3: Persist results with a fresh session
        async with AsyncSessionType(engine, expire_on_commit=False) as write_session:
            persistence = PersistenceManager(write_session)
            persisted_events = await persistence.persist_tick_results(
                run_id, result, world, current_tick + 1
            )
            await self._scenario.with_session(write_session).update_state_from_events(
                run_id, persisted_events
            )
            # Persist LLM call records (独立 session，失败不影响主流程)
        if llm_records and engine is not None:
            from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession
            from app.infra.logging import get_logger as _get_logger
            _logger = _get_logger(__name__)
            try:
                async with _AsyncSession(engine, expire_on_commit=False) as llm_session:
                    for record in llm_records:
                        llm_session.add(record)
                    await llm_session.commit()
            except Exception as exc:
                _logger.warning(f"Failed to persist llm_calls for run {run_id}: {exc}")

        return result

    async def _prepare_intents_from_data(
        self,
        world: WorldState,
        agent_data: list[AgentDecisionSnapshot],
        engine: "async_engine | None" = None,
        run_id: str | None = None,
        tick_no: int = 0,
    ) -> list[ActionIntent]:
        """Prepare intents from pre-loaded agent data.

        This method is called without an active database session,
        allowing SDK calls to use anyio without greenlet conflicts.

        Agent decisions are made in PARALLEL for performance.
        Memory tools are available via MCP if engine is provided.
        """
        from app.agent.runtime import RuntimeContext
        from uuid import uuid4

        # Collect LLM call records in a thread-safe list
        llm_records: list[LlmCall] = []

        async def decide_for_agent(agent_snapshot: AgentDecisionSnapshot) -> ActionIntent | None:
            agent_id = agent_snapshot.id
            state = get_agent(world, agent_id)
            if state is None:
                return None

            profile = agent_snapshot.profile
            runtime_agent_id = get_agent_config_id(profile) or agent_id
            truman_suspicion_score = extract_truman_suspicion_from_agent_data(agent_data, world)

            # Build runtime context with memory tools support
            runtime_ctx = None
            if run_id is not None:
                # 捕获真实 DB agent id（UUID），避免被回调参数遮蔽
                db_agent_id = agent_snapshot.id

                def on_llm_call(
                    agent_id: str,
                    task_type: str,
                    usage: dict | None,
                    total_cost_usd: float | None,
                    duration_ms: int,
                ) -> None:
                    record = LlmCall(
                        id=str(uuid4()),
                        run_id=run_id,
                        agent_id=db_agent_id,  # 使用真实 UUID，满足外键约束
                        task_type=task_type,
                        tick_no=tick_no,
                        input_tokens=int((usage or {}).get("input_tokens", 0)),
                        output_tokens=int((usage or {}).get("output_tokens", 0)),
                        cache_read_tokens=int((usage or {}).get("cache_read_input_tokens", 0)),
                        cache_creation_tokens=int((usage or {}).get("cache_creation_input_tokens", 0)),
                        total_cost_usd=total_cost_usd,
                        duration_ms=duration_ms or 0,
                    )
                    llm_records.append(record)

                # 使用预加载的 memory_cache（避免在 anyio task 中创建 DB session）
                from app.agent.memory_cache import MemoryCache

                memory_cache = (
                    MemoryCache(agent_snapshot.memory_cache)
                    if agent_snapshot.memory_cache
                    else None
                )

                runtime_ctx = RuntimeContext(
                    db_engine=engine,  # 保留 engine 用于其他用途
                    run_id=run_id,
                    enable_memory_tools=True,
                    on_llm_call=on_llm_call,
                    memory_cache=memory_cache,  # 优先使用缓存
                )

            # Extract workplace_location_id from profile
            workplace_location_id = None
            if isinstance(profile, dict):
                workplace_location_id = profile.get("workplace_location_id")

            return await self._decide_intent_for_agent(
                agent_id=agent_id,
                runtime_agent_id=runtime_agent_id,
                world=world,
                current_goal=agent_snapshot.current_goal,
                current_location_id=agent_snapshot.current_location_id,
                home_location_id=agent_snapshot.home_location_id,
                current_status=state.status,
                profile=profile if isinstance(profile, dict) else {},
                recent_events=agent_snapshot.recent_events,
                truman_suspicion_score=truman_suspicion_score,
                runtime_ctx=runtime_ctx,
                workplace_location_id=workplace_location_id,
                current_plan=agent_snapshot.current_plan,
            )

        # Execute all agent decisions in PARALLEL
        # Memory tools now use pre-loaded cache (no DB session creation in anyio tasks)
        results = await asyncio.gather(*[decide_for_agent(snapshot) for snapshot in agent_data])

        # Filter out None results (agents without valid state)
        intents = [r for r in results if r is not None]
        return intents, llm_records

    async def _persist_tick_events(self, run_id: str, result: TickResult) -> None:
        """Persist tick events and related data."""
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
            await self._persistence.persist_tick_memories(run_id, persisted)
            await self._persistence.persist_tick_relationships(run_id, persisted)
            await self._scenario.update_state_from_events(run_id, persisted)

    async def prepare_tick_intents(self, run_id: str, world: WorldState) -> list[ActionIntent]:
        agents = await self.agent_repo.list_for_run(run_id)
        intents: list[ActionIntent] = []
        truman_suspicion_score = self._context_builder.extract_truman_suspicion_from_agents(
            agents, world
        )
        plan = await self._scenario.build_director_plan(run_id, agents)
        agent_recent_events = await build_agent_recent_events(
            session=self.session,
            run_id=run_id,
            agents=list(agents),
            agent_states=world.agents,
            location_states=world.locations,
        )

        for agent in agents:
            state = get_agent(world, agent.id)
            if state is None:
                continue

            runtime_agent_id = self._resolve_runtime_agent_id(agent)
            profile = self._scenario.merge_agent_profile(agent, plan)
            intents.append(
                await self._decide_intent_for_agent(
                    agent_id=agent.id,
                    runtime_agent_id=runtime_agent_id,
                    world=world,
                    current_goal=agent.current_goal,
                    current_location_id=state.location_id,
                    home_location_id=agent.home_location_id,
                    current_status=state.status,
                    profile=profile,
                    recent_events=agent_recent_events.get(agent.id, []),
                    truman_suspicion_score=truman_suspicion_score,
                )
            )

        return intents

    async def _decide_intent_for_agent(
        self,
        *,
        agent_id: str,
        runtime_agent_id: str,
        world: WorldState,
        current_goal: str | None,
        current_location_id: str | None,
        home_location_id: str | None,
        current_status: dict | None,
        profile: dict,
        recent_events: list[dict],
        truman_suspicion_score: float,
        runtime_ctx=None,
        workplace_location_id: str | None = None,
        current_plan: dict | None = None,
    ) -> ActionIntent:
        nearby_agent_id = (
            find_nearby_agent(world, agent_id, current_location_id)
            if current_location_id is not None
            else None
        )
        director_guidance = get_director_guidance(profile)

        try:
            world_ctx = build_agent_world_context(
                world=world,
                current_goal=current_goal,
                current_location_id=current_location_id,
                home_location_id=home_location_id,
                nearby_agent_id=nearby_agent_id,
                current_status=current_status,
                truman_suspicion_score=truman_suspicion_score,
                world_role=get_world_role(profile),
                director_guidance=director_guidance,
                workplace_location_id=workplace_location_id,
                current_plan=current_plan,
            )
            inject_profile_fields_into_context(world_ctx, profile)
            intent = await self.agent_runtime.react(
                runtime_agent_id,
                world=world_ctx,
                memory={"recent": []},
                event={},
                recent_events=recent_events,
                runtime_ctx=runtime_ctx,
            )
            intent.agent_id = agent_id
            return intent
        except (RuntimeError, ValueError, asyncio.CancelledError):
            return self._fallback_intent(
                agent_id=agent_id,
                current_goal=current_goal,
                current_location_id=current_location_id or "",
                home_location_id=home_location_id,
                nearby_agent_id=nearby_agent_id,
                world_role=get_world_role(profile),
                current_status=current_status,
                truman_suspicion_score=truman_suspicion_score,
                director_guidance=director_guidance,
                workplace_location_id=workplace_location_id,
                world=world,
            )

    def _resolve_runtime_agent_id(self, agent: Agent) -> str:
        return get_agent_config_id(agent.profile) or agent.id

    async def inject_director_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict,
        location_id: str | None = None,
        importance: float = 0.5,
    ) -> None:
        """Inject a director event - unified flow via DirectorPlan.

        This method unifies manual injection with automatic intervention
        by converting the event into a DirectorPlan and saving it to
        DirectorMemory, ensuring consistent handling and execution tracking.
        """
        run = await self.run_repo.get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)

        # 1. Get all agents and find Truman
        agents = await self.agent_repo.list_for_run(run_id)
        truman = next(
            (a for a in agents if get_world_role(a.profile) == "truman"),
            None,
        )

        # 2. Build DirectorPlan from manual event (unified flow)
        manual_planner = ManualDirectorPlanner()
        plan = manual_planner.build_plan_from_manual_event(
            event_type=event_type,
            payload=payload,
            location_id=location_id,
            agents=agents,
            truman_agent_id=truman.id if truman else None,
        )

        if plan is None:
            msg = f"Unsupported director event type: {event_type}"
            raise ValueError(msg)

        # 3. Save to DirectorMemory (unified storage with automatic interventions)
        await self.director_memory_repo.create(
            run_id=run_id,
            tick_no=run.current_tick,
            scene_goal=plan.scene_goal,
            target_cast_ids=plan.target_cast_ids,
            priority=plan.priority,
            urgency=plan.urgency,
            message_hint=plan.message_hint,
            target_agent_id=plan.target_agent_id,
            reason=plan.reason,
            trigger_suspicion_score=0.0,  # Manual injection doesn't depend on suspicion
            trigger_continuity_risk="stable",
            cooldown_ticks=plan.cooldown_ticks,
            location_hint=plan.location_hint,
        )

        # 4. Also create Event for timeline display (optional but useful)
        event = build_event(
            run_id=run_id,
            tick_no=run.current_tick,
            world_time=get_run_world_time(run).isoformat(),
            action_type=build_director_event_type(event_type),
            payload=payload,
            accepted=True,
        )
        event.location_id = location_id
        event.importance = importance
        event.visibility = "system"
        await self.event_repo.create(event)

    async def observe_run(self, run_id: str, event_limit: int = 20) -> DirectorAssessment:
        run = await self.run_repo.get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)
        self._configure_scenario_for_run(run)
        return await self._scenario.observe_run(run_id, event_limit=event_limit)

    async def seed_demo_run(self, run_id: str) -> None:
        run = await self.run_repo.get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)
        self._configure_scenario_for_run(run)

        existing_agents = await self.agent_repo.list_for_run(run_id)
        if existing_agents:
            return
        await self._scenario.seed_demo_run(run)

    async def _load_world(self, run_id: str, tick_minutes: int) -> WorldState:
        run = await self.run_repo.get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)
        return await self._context_builder.load_world(run_id, run, tick_minutes)

    def _fallback_intent(
        self,
        agent_id: str,
        current_goal: str | None,
        current_location_id: str,
        home_location_id: str | None,
        nearby_agent_id: str | None,
        world_role: str | None = None,
        current_status: dict | None = None,
        truman_suspicion_score: float = 0.0,
        director_guidance: DirectorGuidance | None = None,
        workplace_location_id: str | None = None,
        world: WorldState | None = None,
    ) -> ActionIntent:
        # Build scenario_state and scenario_guidance from legacy params
        scenario_state: dict | None = None
        if truman_suspicion_score != 0.0:
            scenario_state = {"truman_suspicion_score": truman_suspicion_score}
        # Convert DirectorGuidance (director_*) to ScenarioGuidance (generic keys)
        scenario_guidance = None
        if director_guidance:
            from app.scenario.types import ScenarioGuidance
            scenario_guidance = ScenarioGuidance(
                scene_goal=director_guidance.get("director_scene_goal"),
                priority=director_guidance.get("director_priority"),
                message_hint=director_guidance.get("director_message_hint"),
                target_agent_id=director_guidance.get("director_target_agent_id"),
                location_hint=director_guidance.get("director_location_hint"),
                reason=director_guidance.get("director_reason"),
            )
        scenario_intent = self._scenario.fallback_intent(
            agent_id=agent_id,
            current_location_id=current_location_id,
            home_location_id=home_location_id,
            nearby_agent_id=nearby_agent_id,
            world_role=world_role,
            current_status=current_status,
            scenario_state=scenario_state,
            scenario_guidance=scenario_guidance,
        )
        if scenario_intent is not None:
            return scenario_intent

        if isinstance(current_goal, str) and current_goal.startswith("move:"):
            target_location_id = current_goal.split(":", 1)[1].strip()
            # 检查目标地点是否存在
            if world is not None and world.get_location(target_location_id) is None:
                return ActionIntent(agent_id=agent_id, action_type="rest")
            return ActionIntent(
                agent_id=agent_id,
                action_type="move",
                target_location_id=target_location_id,
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

        # 通勤逻辑：goal=work 但不在工作地点时，先生成 move 动作
        if current_goal == "work":
            if workplace_location_id and current_location_id != workplace_location_id:
                return ActionIntent(
                    agent_id=agent_id,
                    action_type="move",
                    target_location_id=workplace_location_id,
                )
            # 检查当前地点类型
            if world is not None:
                current_location = world.get_location(current_location_id) if current_location_id else None
                current_location_type = current_location.location_type if current_location else None
                if workplace_location_id or current_location_type in {"office", "hospital", "cafe", "shop"}:
                    return ActionIntent(agent_id=agent_id, action_type="work")
            elif workplace_location_id:
                return ActionIntent(agent_id=agent_id, action_type="work")
            return ActionIntent(agent_id=agent_id, action_type="rest")

        return ActionIntent(agent_id=agent_id, action_type="rest")
