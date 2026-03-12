from __future__ import annotations

from pathlib import Path

from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.cognition.claude.decision_provider import AgentDecisionProvider
from app.cognition.claude.decision_utils import RuntimeDecision
from app.cognition.heuristic.agent_backend import HeuristicAgentBackend
from app.store.models import Agent, Location, SimulationRun


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
    scenario_type: str = "truman_world",
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
