from __future__ import annotations

import asyncio
from time import perf_counter
from typing import TYPE_CHECKING

from app.agent.runtime import RuntimeContext
from app.infra.logging import get_logger
from app.scenario.base import Scenario
from app.scenario.types import get_agent_config_id, get_scenario_guidance, get_world_role
from app.sim.agent_snapshot_builder import build_agent_recent_events
from app.sim.llm_call_collector import LlmCallCollector
from app.sim.runner import SimulationRunner, TickResult
from app.sim.runtime_context_utils import (
    build_agent_world_context,
    extract_truman_suspicion_from_agent_data,
    inject_profile_fields_into_context,
)
from app.sim.world import WorldState
from app.sim.world_queries import find_nearby_agent, get_agent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.agent.runtime import AgentRuntime
    from app.sim.action_resolver import ActionIntent
    from app.sim.context import ContextBuilder
    from app.sim.types import AgentDecisionSnapshot
    from app.store.models import Agent, LlmCall
    from app.store.repositories import AgentRepository


logger = get_logger(__name__)


class TickOrchestrator:
    def __init__(
        self,
        *,
        agent_runtime: AgentRuntime,
        scenario: Scenario,
        session: AsyncSession | None = None,
        context_builder: ContextBuilder | None = None,
        agent_repo: AgentRepository | None = None,
    ) -> None:
        self.agent_runtime = agent_runtime
        self.scenario = scenario
        self.session = session
        self.context_builder = context_builder
        self.agent_repo = agent_repo

    async def prepare_tick_intents(self, run_id: str, world: WorldState) -> list[ActionIntent]:
        if self.session is None or self.context_builder is None or self.agent_repo is None:
            msg = "TickOrchestrator.prepare_tick_intents requires a bound session context"
            raise RuntimeError(msg)

        started_at = perf_counter()
        agents = await self.agent_repo.list_for_run(run_id)
        intents: list[ActionIntent] = []
        truman_suspicion_score = self.context_builder.extract_truman_suspicion_from_agents(
            agents, world
        )
        plan = await self.scenario.build_director_plan(run_id, agents)
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

            runtime_agent_id = self.resolve_runtime_agent_id(agent)
            profile = self.scenario.merge_agent_profile(agent, plan)
            intents.append(
                await self.decide_intent_for_agent(
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

        logger.debug(
            "tick_phase_completed run_id=%s tick_no=%s phase=prepare_tick_intents "
            "duration_ms=%s agent_count=%s intent_count=%s",
            run_id,
            world.current_tick,
            int((perf_counter() - started_at) * 1000),
            len(agents),
            len(intents),
        )
        return intents

    async def prepare_intents_from_data(
        self,
        world: WorldState,
        agent_data: list[AgentDecisionSnapshot],
        engine=None,
        run_id: str | None = None,
        tick_no: int = 0,
    ) -> tuple[list[ActionIntent], list[LlmCall]]:
        phase_started_at = perf_counter()
        collector = LlmCallCollector()
        concurrency_limit = self.agent_runtime.decision_concurrency_limit()
        semaphore = (
            asyncio.Semaphore(concurrency_limit)
            if isinstance(concurrency_limit, int) and concurrency_limit > 0
            else None
        )

        async def decide_for_agent(agent_snapshot: AgentDecisionSnapshot) -> ActionIntent | None:
            enqueued_at = perf_counter()
            if semaphore is None:
                return await _decide_for_agent_inner(agent_snapshot, enqueued_at=enqueued_at)
            async with semaphore:
                return await _decide_for_agent_inner(agent_snapshot, enqueued_at=enqueued_at)

        async def _decide_for_agent_inner(
            agent_snapshot: AgentDecisionSnapshot,
            *,
            enqueued_at: float,
        ) -> ActionIntent | None:
            agent_id = agent_snapshot.id
            state = get_agent(world, agent_id)
            if state is None:
                return None

            profile = agent_snapshot.profile
            runtime_agent_id = get_agent_config_id(profile) or agent_id
            truman_suspicion_score = extract_truman_suspicion_from_agent_data(agent_data, world)

            runtime_ctx = None
            if run_id is not None:
                db_agent_id = agent_snapshot.id

                from app.agent.memory_cache import MemoryCache

                memory_cache = (
                    MemoryCache(agent_snapshot.memory_cache)
                    if agent_snapshot.memory_cache
                    else None
                )

                runtime_ctx = RuntimeContext(
                    db_engine=engine,
                    run_id=run_id,
                    enable_memory_tools=True,
                    on_llm_call=collector.build_callback(
                        run_id=run_id,
                        db_agent_id=db_agent_id,
                        tick_no=tick_no,
                    ),
                    memory_cache=memory_cache,
                )

            workplace_location_id = None
            if isinstance(profile, dict):
                workplace_location_id = profile.get("workplace_location_id")

            started_at = perf_counter()
            queue_delay_ms = int((started_at - enqueued_at) * 1000)
            logger.debug(
                "agent_decision_started run_id=%s tick_no=%s agent_id=%s runtime_agent_id=%s "
                "queue_delay_ms=%s current_location_id=%s",
                run_id,
                tick_no,
                agent_id,
                runtime_agent_id,
                queue_delay_ms,
                agent_snapshot.current_location_id,
            )

            try:
                intent = await self.decide_intent_for_agent(
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
            except Exception:
                logger.exception(
                    "agent_decision_failed run_id=%s tick_no=%s agent_id=%s runtime_agent_id=%s "
                    "queue_delay_ms=%s",
                    run_id,
                    tick_no,
                    agent_id,
                    runtime_agent_id,
                    queue_delay_ms,
                )
                raise

            logger.debug(
                "agent_decision_completed run_id=%s tick_no=%s agent_id=%s runtime_agent_id=%s "
                "queue_delay_ms=%s duration_ms=%s action_type=%s target_agent_id=%s "
                "target_location_id=%s",
                run_id,
                tick_no,
                agent_id,
                runtime_agent_id,
                queue_delay_ms,
                int((perf_counter() - started_at) * 1000),
                intent.action_type,
                intent.target_agent_id,
                intent.target_location_id,
            )
            return intent

        results = await asyncio.gather(*[decide_for_agent(snapshot) for snapshot in agent_data])
        intents = [result for result in results if result is not None]
        logger.debug(
            "tick_phase_completed run_id=%s tick_no=%s phase=decide_intents duration_ms=%s "
            "agent_count=%s intent_count=%s llm_call_count=%s concurrency_limit=%s",
            run_id,
            tick_no,
            int((perf_counter() - phase_started_at) * 1000),
            len(agent_data),
            len(intents),
            len(collector.records),
            concurrency_limit,
        )
        return intents, collector.records

    async def decide_intent_for_agent(
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
        director_guidance = get_scenario_guidance(profile)

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

    def execute_tick(
        self,
        *,
        run_id: str | None,
        world: WorldState,
        current_tick: int,
        intents: list[ActionIntent],
    ) -> TickResult:
        started_at = perf_counter()
        runner = SimulationRunner(world)
        runner.tick_no = current_tick
        result = runner.tick(intents)
        logger.debug(
            "tick_phase_completed run_id=%s tick_no=%s phase=execute_tick duration_ms=%s "
            "accepted_count=%s rejected_count=%s",
            run_id,
            current_tick,
            int((perf_counter() - started_at) * 1000),
            len(result.accepted),
            len(result.rejected),
        )
        return result

    @staticmethod
    def resolve_runtime_agent_id(agent: Agent) -> str:
        return get_agent_config_id(agent.profile) or agent.id
