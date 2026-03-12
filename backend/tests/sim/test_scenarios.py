from __future__ import annotations

import pytest

from app.agent.context_builder import ContextBuilder
from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.scenario.factory import create_scenario
from app.scenario.open_world.scenario import OpenWorldScenario
from app.scenario.truman_world.scenario import TrumanWorldScenario
from app.store.models import Event, SimulationRun
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


def test_truman_world_scenario_registers_fallback_hook_on_runtime(tmp_path):
    agent_dir = tmp_path / "demo_agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: demo_agent",
                "name: Demo Agent",
                "occupation: resident",
                "home: demo_home",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Demo Agent\nBase prompt", encoding="utf-8")

    class HookAwareBackend:
        def __init__(self) -> None:
            self.hook = None

        def set_decision_hook(self, decision_hook) -> None:
            self.hook = decision_hook

        async def decide_action(self, invocation, runtime_ctx=None):
            raise NotImplementedError

        async def plan_day(self, invocation, runtime_ctx=None):
            return None

        async def reflect_day(self, invocation, runtime_ctx=None):
            return None

    backend = HookAwareBackend()
    runtime = AgentRuntime(
        registry=AgentRegistry(tmp_path),
        context_builder=ContextBuilder(),
        backend=backend,
    )

    TrumanWorldScenario().configure_runtime(runtime)

    assert backend.hook is not None


@pytest.mark.asyncio
async def test_truman_world_scenario_seed_and_state_update(db_session):
    run = SimulationRun(id="run-scenario-seed", name="scenario-seed", status="running")
    db_session.add(run)
    await db_session.commit()

    scenario = TrumanWorldScenario(db_session)
    await scenario.seed_demo_run(run)

    agents = await AgentRepository(db_session).list_for_run(run.id)
    assert [agent.name for agent in agents] == [
        "Alice",
        "Bob",
        "Lauren",
        "Marlon",
        "Meryl",
        "Truman",
    ]

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


@pytest.mark.asyncio
async def test_open_world_scenario_persist_director_plan_is_noop(db_session):
    scenario = OpenWorldScenario(db_session)

    await scenario.persist_director_plan("run-open-world", None)


def test_scenario_factory_returns_expected_implementation(db_session):
    assert isinstance(create_scenario("open_world", db_session), OpenWorldScenario)
    assert isinstance(create_scenario("truman_world", db_session), TrumanWorldScenario)
    assert isinstance(create_scenario(None, db_session), TrumanWorldScenario)


def test_scenario_configures_runtime_allowed_actions(tmp_path):
    agent_dir = tmp_path / "demo_agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: demo_agent",
                "name: Demo Agent",
                "occupation: resident",
                "home: demo_home",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Demo Agent\nBase prompt", encoding="utf-8")

    runtime = AgentRuntime(registry=AgentRegistry(tmp_path), context_builder=ContextBuilder())
    scenario = create_scenario("open_world")
    scenario.configure_runtime(runtime)

    invocation = runtime.prepare_reactor("demo_agent", world={"current_goal": "rest"})

    assert invocation.allowed_actions == scenario.allowed_actions()
