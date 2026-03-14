from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.director.observer import DirectorAssessment
from app.infra.logging import get_logger
from app.infra.metrics import observe_tick
from app.infra.settings import get_settings
from app.scenario.base import Scenario
from app.scenario.factory import create_scenario
from app.sim.action_resolver import ActionIntent
from app.sim.context import ContextBuilder
from app.sim.day_boundary_coordinator import DayBoundaryCoordinator
from app.sim.isolated_tick_runner import IsolatedTickRunner
from app.sim.persistence import PersistenceManager
from app.sim.runner import TickResult
from app.sim.tick_event_writer import TickEventWriter
from app.sim.tick_orchestrator import TickOrchestrator
from app.sim.world import WorldState
from app.store.models import SimulationRun
from app.store.repositories import (
    AgentRepository,
    RunRepository,
)

if TYPE_CHECKING:
    from app.infra.db import async_engine


logger = get_logger(__name__)


class SimulationService:
    """Thin application service coordinating tick orchestration and persistence."""

    def __init__(
        self,
        session: AsyncSession | None,
        agent_runtime: AgentRuntime | None = None,
        agents_root: Path | None = None,
        scenario: Scenario | None = None,
    ) -> None:
        self.session = session
        self.run_repo = RunRepository(session) if session is not None else None
        self.agent_repo = AgentRepository(session) if session is not None else None
        self._context_builder = ContextBuilder(session) if session is not None else None
        self._persistence = PersistenceManager(session) if session is not None else None
        # Track whether a scenario was explicitly injected (e.g. in tests).
        # When True, run_tick will NOT override _scenario based on run.scenario_type.
        self._injected_scenario: bool = scenario is not None
        self._scenario = (
            scenario.with_session(session)
            if scenario is not None
            else create_scenario("truman_world", session)
        )
        settings = get_settings()
        self.agent_runtime = agent_runtime or AgentRuntime(
            registry=AgentRegistry(agents_root or (settings.project_root / "agents"))
        )
        self.day_boundary_coordinator = DayBoundaryCoordinator()
        self._scenario.configure_runtime(self.agent_runtime)

    def _configure_scenario(self, scenario_type: str | None) -> Scenario:
        self._scenario = create_scenario(scenario_type, self.session)
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
    ) -> SimulationService:
        return cls(
            session=None,
            agent_runtime=agent_runtime,
            scenario=(
                scenario.with_session(None)
                if scenario is not None
                else create_scenario("truman_world")
            ),
        )

    def _require_session_bound(self) -> AsyncSession:
        if self.session is None:
            msg = "SimulationService is not bound to a database session"
            raise RuntimeError(msg)
        return self.session

    def _require_run_repo(self) -> RunRepository:
        if self.run_repo is None:
            msg = "SimulationService requires a bound RunRepository"
            raise RuntimeError(msg)
        return self.run_repo

    def _require_agent_repo(self) -> AgentRepository:
        if self.agent_repo is None:
            msg = "SimulationService requires a bound AgentRepository"
            raise RuntimeError(msg)
        return self.agent_repo

    def _require_context_builder(self) -> ContextBuilder:
        if self._context_builder is None:
            msg = "SimulationService requires a bound ContextBuilder"
            raise RuntimeError(msg)
        return self._context_builder

    def _require_persistence(self) -> PersistenceManager:
        if self._persistence is None:
            msg = "SimulationService requires a bound PersistenceManager"
            raise RuntimeError(msg)
        return self._persistence

    def _build_tick_orchestrator(self) -> TickOrchestrator:
        return TickOrchestrator(
            agent_runtime=self.agent_runtime,
            scenario=self._scenario,
            session=self.session,
            context_builder=self._context_builder,
            agent_repo=self.agent_repo,
        )

    def _build_tick_event_writer(self) -> TickEventWriter:
        return TickEventWriter(self.session)

    async def run_tick(self, run_id: str, intents: list[ActionIntent] | None = None) -> TickResult:
        started_at = perf_counter()
        logger.debug(f"Starting tick for run {run_id}")
        run_repo = self._require_run_repo()
        try:
            run = await run_repo.get(run_id)
            if run is None:
                msg = f"Run not found: {run_id}"
                raise ValueError(msg)
            self._configure_scenario_for_run(run)

            world = await self._load_world(run_id, tick_minutes=run.tick_minutes)
            planner_ran = await self.day_boundary_coordinator.run_planner_if_needed(
                run_id=run_id,
                tick_no=run.current_tick,
                world=world,
                engine=self._require_session_bound().bind,
                agent_runtime=self.agent_runtime,
            )
            if planner_ran:
                world = await self._load_world(run_id, tick_minutes=run.tick_minutes)
            if not intents:
                intents = await self.prepare_tick_intents(run_id, world)
            result = self._build_tick_orchestrator().execute_tick(
                run_id=run_id,
                world=world,
                current_tick=run.current_tick,
                intents=intents,
            )

            await self._require_persistence().persist_agent_locations(run_id, world)
            await run_repo.update_tick(run, result.tick_no)
            await self._persist_tick_events(run_id, result)
            await self.day_boundary_coordinator.run(
                run_id=run_id,
                result=result,
                world=world,
                engine=self._require_session_bound().bind,
                agent_runtime=self.agent_runtime,
            )
        except Exception as e:
            logger.error(f"Tick failed for run {run_id}: {e}")
            observe_tick(
                mode="inline", status="error", duration_seconds=perf_counter() - started_at
            )
            raise
        duration = perf_counter() - started_at
        logger.debug(
            f"Tick completed for run {run_id}: tick_no={result.tick_no}, duration={duration:.3f}s"
        )
        observe_tick(mode="inline", status="success", duration_seconds=duration)
        return result

    async def run_tick_isolated(
        self,
        run_id: str,
        engine: async_engine,
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
        started_at = perf_counter()
        try:
            result, scenario = await IsolatedTickRunner(agent_runtime=self.agent_runtime).run(
                run_id=run_id,
                engine=engine,
                intents=intents,
            )
        except Exception:
            observe_tick(
                mode="isolated",
                status="error",
                duration_seconds=perf_counter() - started_at,
            )
            raise
        observe_tick(
            mode="isolated",
            status="success",
            duration_seconds=perf_counter() - started_at,
        )
        self._scenario = scenario
        return result

    async def _persist_tick_events(self, run_id: str, result: TickResult) -> None:
        await self._build_tick_event_writer().persist(
            run_id=run_id,
            result=result,
            scenario=self._scenario,
        )

    async def prepare_tick_intents(self, run_id: str, world: WorldState) -> list[ActionIntent]:
        return await self._build_tick_orchestrator().prepare_tick_intents(run_id, world)

    async def observe_run(self, run_id: str, event_limit: int = 20) -> DirectorAssessment:
        run = await self._require_run_repo().get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)
        self._configure_scenario_for_run(run)
        return await self._scenario.observe_run(run_id, event_limit=event_limit)

    async def seed_demo_run(self, run_id: str) -> None:
        logger.info(f"Seeding demo run {run_id}")
        run = await self._require_run_repo().get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)
        self._configure_scenario_for_run(run)

        existing_agents = await self._require_agent_repo().list_for_run(run_id)
        if existing_agents:
            logger.debug(f"Demo run {run_id} already has agents, skipping seed")
            return
        await self._scenario.seed_demo_run(run)
        logger.info(f"Demo run {run_id} seeded successfully")

    async def _load_world(self, run_id: str, tick_minutes: int) -> WorldState:
        run = await self._require_run_repo().get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)
        return await self._require_context_builder().load_world(run_id, run, tick_minutes)
