from __future__ import annotations

import pytest

from app.agent.context_builder import ContextBuilder
from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.scenario.open_world.scenario import OpenWorldScenario
from app.scenario.truman_world.scenario import TrumanWorldScenario
from app.store.models import Agent, Event, SimulationRun
from app.store.repositories import AgentRepository


def test_truman_world_scenario_configures_runtime_context(tmp_path):
    agent_dir = tmp_path / "truman"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: truman",
                "name: Truman",
                "world_role: truman",
                "occupation: resident",
                "home: demo_home",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Truman\nBase prompt", encoding="utf-8")

    runtime = AgentRuntime(registry=AgentRegistry(tmp_path), context_builder=ContextBuilder())
    TrumanWorldScenario().configure_runtime(runtime)

    invocation = runtime.prepare_reactor(
        "truman",
        world={
            "current_goal": "rest",
            "self_status": {"suspicion_score": 0.3},
            "director_hint": "ignore-me",
        },
    )

    assert invocation.context["role_context"]["perspective"] == "subjective"
    assert "director_hint" not in invocation.context["world"]


@pytest.mark.asyncio
async def test_truman_world_scenario_seed_and_state_update(db_session):
    run = SimulationRun(id="run-scenario-seed", name="scenario-seed", status="running")
    db_session.add(run)
    await db_session.commit()

    scenario = TrumanWorldScenario(db_session)
    await scenario.seed_demo_run(run)

    agents = await AgentRepository(db_session).list_for_run(run.id)
    assert [agent.name for agent in agents] == ["Lauren", "Marlon", "Meryl", "Truman"]

    truman = next(agent for agent in agents if (agent.profile or {}).get("world_role") == "truman")
    starting_score = float((truman.status or {}).get("suspicion_score", 0.0))
    event = Event(
        id="evt-scenario",
        run_id=run.id,
        tick_no=1,
        event_type="move_rejected",
        actor_agent_id=truman.id,
        payload={"agent_id": truman.id},
    )

    await scenario.update_state_from_events(run.id, [event])
    await db_session.refresh(truman)

    assert truman.status["suspicion_score"] > starting_score


@pytest.mark.asyncio
async def test_open_world_scenario_seed_is_minimal(db_session):
    run = SimulationRun(id="run-open-world", name="open-world", status="running")
    db_session.add(run)
    await db_session.commit()

    scenario = OpenWorldScenario(db_session)
    await scenario.seed_demo_run(run)

    agents = await AgentRepository(db_session).list_for_run(run.id)
    assert [agent.name for agent in agents] == ["Rover"]

    assessment = scenario.assess(run_id=run.id, current_tick=0, agents=agents, events=[])
    assert assessment.continuity_risk == "stable"
    assert assessment.suspicion_level == "low"
