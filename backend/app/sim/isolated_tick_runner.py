from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.logging import get_logger
from app.scenario.factory import create_scenario
from app.sim.day_boundary_coordinator import DayBoundaryCoordinator
from app.sim.llm_call_writer import LlmCallWriter
from app.sim.persistence import PersistenceManager
from app.sim.tick_orchestrator import TickOrchestrator
from app.sim.world_loader import load_tick_data
from app.store.models import SimulationRun

if TYPE_CHECKING:
    from app.agent.runtime import AgentRuntime
    from app.scenario.base import Scenario
    from app.sim.action_resolver import ActionIntent
    from app.sim.runner import TickResult


logger = get_logger(__name__)


class IsolatedTickRunner:
    def __init__(
        self,
        *,
        agent_runtime: AgentRuntime,
        llm_call_writer: LlmCallWriter | None = None,
        day_boundary_coordinator: DayBoundaryCoordinator | None = None,
    ) -> None:
        self.agent_runtime = agent_runtime
        self.llm_call_writer = llm_call_writer or LlmCallWriter()
        self.day_boundary_coordinator = day_boundary_coordinator or DayBoundaryCoordinator()

    async def run(
        self,
        *,
        run_id: str,
        engine,
        intents: list[ActionIntent] | None = None,
    ) -> tuple[TickResult, Scenario]:
        read_started_at = perf_counter()
        async with AsyncSession(engine) as read_session:
            run = await read_session.get(SimulationRun, run_id)
            if run is None:
                msg = f"Run not found: {run_id}"
                raise ValueError(msg)
            scenario = create_scenario(run.scenario_type, read_session)
            scenario.configure_runtime(self.agent_runtime)
            loaded = await load_tick_data(
                session=read_session,
                run_id=run_id,
                scenario=scenario,
            )
        logger.debug(
            "tick_phase_completed run_id=%s tick_no=%s phase=load_tick_data duration_ms=%s "
            "agent_count=%s",
            run_id,
            loaded.run.current_tick,
            int((perf_counter() - read_started_at) * 1000),
            len(loaded.agent_data),
        )

        runtime_scenario = create_scenario(loaded.run.scenario_type)
        runtime_scenario.configure_runtime(self.agent_runtime)
        orchestrator = TickOrchestrator(
            agent_runtime=self.agent_runtime,
            scenario=runtime_scenario,
        )

        # ── 清晨边界：在 agent 决策前先执行 Planner，使当日第一个 tick 即可用新计划 ──
        planner_started_at = perf_counter()
        planner_ran = await self.day_boundary_coordinator.run_planner_if_needed(
            run_id=run_id,
            tick_no=loaded.run.current_tick,
            world=loaded.world,
            engine=engine,
            agent_runtime=self.agent_runtime,
        )
        logger.debug(
            "tick_phase_completed run_id=%s tick_no=%s phase=planner_boundary duration_ms=%s "
            "planner_ran=%s",
            run_id,
            loaded.run.current_tick,
            int((perf_counter() - planner_started_at) * 1000),
            planner_ran,
        )

        # 若 Planner 已写入新计划，重新加载 agent_data 使决策使用当日计划
        if planner_ran:
            reload_started_at = perf_counter()
            async with AsyncSession(engine) as reload_session:
                reload_scenario = create_scenario(loaded.run.scenario_type, reload_session)
                reload_scenario.configure_runtime(self.agent_runtime)
                reloaded = await load_tick_data(
                    session=reload_session,
                    run_id=run_id,
                    scenario=reload_scenario,
                )
            agent_data = reloaded.agent_data
            logger.debug(
                "tick_phase_completed run_id=%s tick_no=%s phase=reload_tick_data duration_ms=%s "
                "agent_count=%s",
                run_id,
                loaded.run.current_tick,
                int((perf_counter() - reload_started_at) * 1000),
                len(agent_data),
            )
        else:
            agent_data = loaded.agent_data

        if not intents:
            intents, llm_records = await orchestrator.prepare_intents_from_data(
                loaded.world,
                agent_data,
                engine,
                run_id,
                loaded.run.current_tick,
            )
        else:
            llm_records = []

        result = orchestrator.execute_tick(
            run_id=run_id,
            world=loaded.world,
            current_tick=loaded.run.current_tick,
            intents=intents,
        )

        persist_started_at = perf_counter()
        async with AsyncSession(engine, expire_on_commit=False) as write_session:
            persistence = PersistenceManager(write_session)
            persisted_events = await persistence.persist_tick_results(
                run_id,
                result,
                loaded.world,
                result.tick_no,
            )
            write_scenario = runtime_scenario.with_session(write_session)
            await write_scenario.update_state_from_events(run_id, persisted_events)
            if loaded.director_plan is not None:
                await write_scenario.persist_director_plan(run_id, loaded.director_plan)
        logger.debug(
            "tick_phase_completed run_id=%s tick_no=%s phase=persist_tick duration_ms=%s "
            "persisted_event_count=%s llm_call_count=%s",
            run_id,
            loaded.run.current_tick,
            int((perf_counter() - persist_started_at) * 1000),
            len(persisted_events),
            len(llm_records),
        )

        llm_write_started_at = perf_counter()
        await self.llm_call_writer.persist(
            run_id=run_id,
            llm_records=llm_records,
            engine=engine,
        )
        logger.debug(
            "tick_phase_completed run_id=%s tick_no=%s phase=persist_llm_calls duration_ms=%s "
            "llm_call_count=%s",
            run_id,
            loaded.run.current_tick,
            int((perf_counter() - llm_write_started_at) * 1000),
            len(llm_records),
        )
        # ── 夜晚边界：tick 结束后执行 Reflector ──
        reflector_started_at = perf_counter()
        await self.day_boundary_coordinator.run(
            run_id=run_id,
            result=result,
            world=loaded.world,
            engine=engine,
            agent_runtime=self.agent_runtime,
        )
        logger.debug(
            "tick_phase_completed run_id=%s tick_no=%s phase=reflector_boundary duration_ms=%s",
            run_id,
            loaded.run.current_tick,
            int((perf_counter() - reflector_started_at) * 1000),
        )
        return result, runtime_scenario
