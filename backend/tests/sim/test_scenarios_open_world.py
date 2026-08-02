from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agent.context_builder import ContextBuilder
from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.scenario.bundle_world.scenario import BundleWorldScenario
from app.scenario.factory import create_scenario
from app.scenario.open_world.scenario import OpenWorldScenario
from app.store.models import Agent, Location
from app.store.repositories import AgentRepository
from tests.factories import make_run

from .helpers import configure_project_root, write_hero_bundle, write_lines


@pytest.mark.asyncio
async def test_open_world_scenario_seed_is_minimal(db_session):
    run = make_run("run-open-world", name="open-world")
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
async def test_open_world_seed_rolls_back_seed_records_when_final_commit_fails(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    run = make_run("run-open-world-seed-fails", name="open-world")
    db_session.add(run)
    await db_session.commit()
    run_id = run.id

    async def fail_commit() -> None:
        raise RuntimeError("open world seed commit failed")

    monkeypatch.setattr(db_session, "commit", fail_commit)

    scenario = OpenWorldScenario(db_session)
    with pytest.raises(RuntimeError, match="open world seed commit failed"):
        await scenario.seed_demo_run(run)

    await db_session.rollback()
    locations = (
        (await db_session.execute(select(Location).where(Location.run_id == run_id)))
        .scalars()
        .all()
    )
    agents = (await db_session.execute(select(Agent).where(Agent.run_id == run_id))).scalars().all()

    assert locations == []
    assert agents == []


@pytest.mark.asyncio
async def test_open_world_scenario_persist_director_plan_is_noop(db_session):
    scenario = OpenWorldScenario(db_session)

    await scenario.persist_director_plan("run-open-world", None)


def test_scenario_factory_returns_expected_implementation(db_session):
    assert isinstance(create_scenario("open_world", db_session), OpenWorldScenario)
    assert isinstance(create_scenario("narrative_world", db_session), BundleWorldScenario)
    assert isinstance(create_scenario(None, db_session), BundleWorldScenario)


def test_narrative_world_adapter_uses_active_bundle_world_knowledge(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    bundle_root = write_hero_bundle(
        tmp_path,
        "alt_world",
        scenario_lines=[
            "id: alt_world",
            "name: Alt World",
            "version: 1",
            "adapter: bundle_world",
        ],
        world_lines=[
            "social_norms:",
            "  - 保持安静排队",
            "location_purposes:",
            "  library:",
            "    - 阅读",
        ],
    )
    configure_project_root(tmp_path, monkeypatch)

    runtime = AgentRuntime(
        registry=AgentRegistry(bundle_root / "agents"),
        context_builder=ContextBuilder(),
    )
    scenario = create_scenario("alt_world")
    scenario.configure_runtime(runtime)

    invocation = runtime.prepare_reactor(
        "hero",
        world={
            "current_goal": "rest",
            "self_status": {"suspicion_score": 0.1},
        },
    )

    assert invocation.context["world_common_knowledge"]["social_norms"] == ["保持安静排队"]
    assert invocation.context["world_common_knowledge"]["location_purposes"] == {
        "library": ["阅读"]
    }


def test_scenario_configures_runtime_allowed_actions(tmp_path):
    agent_dir = tmp_path / "demo_agent"
    agent_dir.mkdir(parents=True)
    write_lines(
        agent_dir / "agent.yml",
        [
            "id: demo_agent",
            "name: Demo Agent",
            "occupation: resident",
            "home: demo_home",
        ],
    )
    (agent_dir / "prompt.md").write_text("# Demo Agent\nBase prompt", encoding="utf-8")

    runtime = AgentRuntime(registry=AgentRegistry(tmp_path), context_builder=ContextBuilder())
    scenario = create_scenario("open_world")
    scenario.configure_runtime(runtime)

    invocation = runtime.prepare_reactor("demo_agent", world={"current_goal": "rest"})

    assert invocation.allowed_actions == scenario.allowed_actions()
