from __future__ import annotations

from pathlib import Path

import pytest

from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.cognition.claude.decision_provider import AgentDecisionProvider
from app.cognition.claude.decision_utils import RuntimeDecision
from app.cognition.heuristic.agent_backend import HeuristicAgentBackend
from app.infra.settings import get_settings
from app.sim.service import SimulationService
from app.sim.tick_orchestrator import TickOrchestrator
from app.store.models import Agent, Base, Location, SimulationRun
from sqlalchemy.ext.asyncio import create_async_engine


class RestOnlyDecisionProvider(AgentDecisionProvider):
    async def decide(self, invocation, runtime_ctx=None) -> RuntimeDecision:  # noqa: ANN001
        return RuntimeDecision(action_type="rest")


async def create_clock_run(
    session,
    *,
    run_id: str,
    current_tick: int = 0,
    tick_minutes: int = 5,
    world_start_time: str = "2026-03-02T06:00:00+00:00",
    include_agent: bool = False,
    scenario_type: str = "narrative_world",
) -> SimulationRun:
    run = SimulationRun(
        id=run_id,
        name=f"clock-{run_id}",
        status="running",
        scenario_type=scenario_type,
        current_tick=current_tick,
        tick_minutes=tick_minutes,
        metadata_json={"world_start_time": world_start_time},
    )
    home = Location(
        id=f"{run_id}-home",
        run_id=run_id,
        name="Home",
        location_type="home",
        capacity=2,
    )
    session.add_all([run, home])

    if include_agent:
        session.add(
            Agent(
                id=f"{run_id}-agent",
                run_id=run_id,
                name="Clock Tester",
                occupation="resident",
                home_location_id=home.id,
                current_location_id=home.id,
                personality={},
                profile={"agent_config_id": "clock_agent"},
                status={},
                current_plan={},
            )
        )

    await session.commit()
    return run


def build_rest_runtime(tmp_path: Path) -> AgentRuntime:
    agent_dir = tmp_path / "clock_agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "agent.yml").write_text(
        "id: clock_agent\nname: Clock Tester\noccupation: resident\nhome: home\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Clock Tester\nBase prompt", encoding="utf-8")
    return AgentRuntime(
        registry=AgentRegistry(tmp_path),
        backend=HeuristicAgentBackend(RestOnlyDecisionProvider()),
    )


async def create_isolated_sqlite_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


def build_scheduler_service(tmp_path: Path, backend: HeuristicAgentBackend | None = None):
    runtime = AgentRuntime(
        registry=AgentRegistry(tmp_path),
        backend=backend or HeuristicAgentBackend(),
    )
    return SimulationService.create_for_scheduler(runtime)


def build_orchestrator(
    tmp_path: Path,
    *,
    provider: AgentDecisionProvider | None = None,
    backend: HeuristicAgentBackend | None = None,
    scenario=None,  # noqa: ANN001
) -> TickOrchestrator:
    runtime = AgentRuntime(
        registry=AgentRegistry(tmp_path),
        backend=backend or HeuristicAgentBackend(provider),
    )
    return TickOrchestrator(agent_runtime=runtime, scenario=scenario)


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def configure_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()


def write_hero_bundle(
    tmp_path: Path,
    scenario_id: str,
    *,
    scenario_lines: list[str],
    world_lines: list[str],
    agent_lines: list[str] | None = None,
    bio: str | None = None,
    initial_lines: list[str] | None = None,
) -> Path:
    bundle_root = tmp_path / "scenarios" / scenario_id
    agent_dir = bundle_root / "agents" / "hero"
    agent_dir.mkdir(parents=True)
    write_lines(bundle_root / "scenario.yml", scenario_lines)
    write_lines(bundle_root / "world.yml", world_lines)
    write_lines(
        agent_dir / "agent.yml",
        agent_lines
        or [
            "id: hero",
            "name: Hero",
            "world_role: truman",
            "occupation: resident",
            "home: apartment",
        ],
    )
    (agent_dir / "prompt.md").write_text("# Hero\nBase prompt", encoding="utf-8")
    if bio is not None:
        (agent_dir / "bio.md").write_text(bio, encoding="utf-8")
    if initial_lines is not None:
        write_lines(agent_dir / "initial.yml", initial_lines)
    return bundle_root
