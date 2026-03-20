from __future__ import annotations

import pytest

from app.infra.settings import get_settings
from app.agent.context_builder import ContextBuilder
from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.scenario.factory import create_scenario
from app.scenario.open_world.scenario import OpenWorldScenario
from app.scenario.narrative_world.scenario import NarrativeWorldScenario
from app.scenario.narrative_world.seed import NarrativeWorldSeedBuilder
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
    NarrativeWorldScenario().configure_runtime(runtime)

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

    NarrativeWorldScenario().configure_runtime(runtime)

    assert backend.hook is not None


def test_truman_world_scenario_fallback_talks_to_nearby_agent():
    scenario = NarrativeWorldScenario()

    intent = scenario.fallback_intent(
        agent_id="cast-1",
        current_location_id="loc-square",
        home_location_id="loc-home",
        nearby_agent_id="truman-1",
        world_role="cast",
        current_status={},
        scenario_state={},
        scenario_guidance=None,
    )

    assert intent is not None
    assert intent.action_type == "talk"
    assert intent.target_agent_id == "truman-1"


def test_truman_world_scenario_fallback_uses_director_guidance_location_hint():
    scenario = NarrativeWorldScenario()

    intent = scenario.fallback_intent(
        agent_id="cast-1",
        current_location_id="loc-home",
        home_location_id="loc-home",
        nearby_agent_id=None,
        world_role="cast",
        current_status={},
        scenario_state={},
        scenario_guidance={
            "director_scene_goal": "gather",
            "director_location_hint": "loc-plaza",
            "director_message_hint": "Head to the plaza naturally.",
        },
    )

    assert intent is not None
    assert intent.action_type == "move"
    assert intent.target_location_id == "loc-plaza"


def test_truman_world_scenario_fallback_returns_home_when_idle_and_away():
    scenario = NarrativeWorldScenario()

    intent = scenario.fallback_intent(
        agent_id="cast-1",
        current_location_id="loc-plaza",
        home_location_id="loc-home",
        nearby_agent_id=None,
        world_role="cast",
        current_status={},
        scenario_state={},
        scenario_guidance=None,
    )

    assert intent is not None
    assert intent.action_type == "move"
    assert intent.target_location_id == "loc-home"


@pytest.mark.asyncio
async def test_truman_world_scenario_seed_and_state_update(db_session):
    run = SimulationRun(id="run-scenario-seed", name="scenario-seed", status="running")
    db_session.add(run)
    await db_session.commit()

    scenario = NarrativeWorldScenario(db_session)
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


def test_truman_world_scenario_defaults_subject_alert_tracking_enabled():
    scenario = NarrativeWorldScenario()

    assert scenario.subject_alert_tracking_enabled is True


@pytest.mark.asyncio
async def test_truman_world_adapter_updates_configured_subject_alert_metric(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    bundle_root = tmp_path / "scenarios" / "alt_world"
    agent_dir = bundle_root / "agents" / "hero"
    agent_dir.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: alt_world",
                "name: Alt World",
                "version: 1",
                "adapter: narrative_world",
                "semantics:",
                "  subject_role: protagonist",
                "  support_roles:",
                "    - ally",
                "  alert_metric: anomaly_score",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "world.yml").write_text(
        "\n".join(
            [
                "locations:",
                "  - id_suffix: library",
                "    name: 静水图书馆",
                "    location_type: library",
                "    capacity: 4",
                "    x: 5",
                "    y: 6",
                "    attributes:",
                "      kind: quiet",
                "location_id_map:",
                "  apartment: library",
                "occupation_names:",
                "  resident: 住户",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: hero",
                "name: Hero",
                "world_role: protagonist",
                "occupation: resident",
                "home: apartment",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Hero\nBase prompt", encoding="utf-8")
    (agent_dir / "bio.md").write_text("Alt bundle hero", encoding="utf-8")

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    run = SimulationRun(
        id="run-alt-world-alert",
        name="alt-world-alert",
        status="running",
        scenario_type="alt_world",
    )
    db_session.add(run)
    await db_session.commit()

    scenario = create_scenario("alt_world", db_session)
    await scenario.seed_demo_run(run)

    agents = await AgentRepository(db_session).list_for_run(run.id)
    protagonist = next(agent for agent in agents if (agent.profile or {}).get("world_role") == "protagonist")
    starting_score = float((protagonist.status or {}).get("anomaly_score", 0.0))
    event = Event(
        id="evt-alt-world-alert",
        run_id=run.id,
        tick_no=1,
        event_type="move_rejected",
        actor_agent_id=protagonist.id,
        payload={"agent_id": protagonist.id},
    )

    await scenario.update_state_from_events(run.id, [event])
    await db_session.refresh(protagonist)

    assert protagonist.status["anomaly_score"] > starting_score


@pytest.mark.asyncio
async def test_truman_world_adapter_skips_subject_alert_updates_when_tracking_disabled(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    bundle_root = tmp_path / "scenarios" / "alt_world_no_alert"
    agent_dir = bundle_root / "agents" / "hero"
    agent_dir.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: alt_world_no_alert",
                "name: Alt World No Alert",
                "version: 1",
                "adapter: narrative_world",
                "semantics:",
                "  subject_role: protagonist",
                "  support_roles:",
                "    - ally",
                "  alert_metric: anomaly_score",
                "capabilities:",
                "  subject_alert_tracking: false",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "world.yml").write_text(
        "\n".join(
            [
                "locations:",
                "  - id_suffix: library",
                "    name: 静水图书馆",
                "    location_type: library",
                "    capacity: 4",
                "    x: 5",
                "    y: 6",
                "    attributes:",
                "      kind: quiet",
                "location_id_map:",
                "  apartment: library",
                "occupation_names:",
                "  resident: 住户",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: hero",
                "name: Hero",
                "world_role: protagonist",
                "occupation: resident",
                "home: apartment",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Hero\nBase prompt", encoding="utf-8")
    (agent_dir / "bio.md").write_text("Alt bundle hero", encoding="utf-8")

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    run = SimulationRun(
        id="run-alt-world-no-alert",
        name="alt-world-no-alert",
        status="running",
        scenario_type="alt_world_no_alert",
    )
    db_session.add(run)
    await db_session.commit()

    scenario = create_scenario("alt_world_no_alert", db_session)
    await scenario.seed_demo_run(run)

    agents = await AgentRepository(db_session).list_for_run(run.id)
    protagonist = next(
        agent for agent in agents if (agent.profile or {}).get("world_role") == "protagonist"
    )
    starting_score = float((protagonist.status or {}).get("anomaly_score", 0.0))
    event = Event(
        id="evt-alt-world-no-alert",
        run_id=run.id,
        tick_no=1,
        event_type="move_rejected",
        actor_agent_id=protagonist.id,
        payload={"agent_id": protagonist.id},
    )

    await scenario.update_state_from_events(run.id, [event])
    await db_session.refresh(protagonist)

    assert protagonist.status["anomaly_score"] == starting_score


@pytest.mark.asyncio
async def test_truman_world_adapter_seed_supports_spawn_aliases(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    bundle_root = tmp_path / "scenarios" / "alt_world_spawn"
    agent_dir = bundle_root / "agents" / "hero"
    agent_dir.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: alt_world_spawn",
                "name: Alt World Spawn",
                "version: 1",
                "adapter: narrative_world",
                "semantics:",
                "  subject_role: protagonist",
                "  alert_metric: anomaly_score",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "world.yml").write_text(
        "\n".join(
            [
                "locations:",
                "  - id_suffix: library",
                "    name: 静水图书馆",
                "    location_type: library",
                "    capacity: 4",
                "    x: 5",
                "    y: 6",
                "    attributes:",
                "      kind: quiet",
                "location_id_map:",
                "  apartment: library",
                "  workplace: library",
                "occupation_names:",
                "  resident: 住户",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: hero",
                "name: Hero",
                "world_role: protagonist",
                "occupation: resident",
                "home: apartment",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Hero\nBase prompt", encoding="utf-8")
    (agent_dir / "initial.yml").write_text(
        "\n".join(
            [
                "status:",
                "  energy: 0.9",
                "  suspicion_score: 0.25",
                "spawn:",
                "  location: workplace",
                "  goal: greet",
                "plan:",
                "  default: patrol",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    run = SimulationRun(
        id="run-alt-world-spawn",
        name="alt-world-spawn",
        status="running",
        scenario_type="alt_world_spawn",
    )
    db_session.add(run)
    await db_session.commit()

    scenario = create_scenario("alt_world_spawn", db_session)
    await scenario.seed_demo_run(run)

    agents = await AgentRepository(db_session).list_for_run(run.id)
    protagonist = agents[0]

    assert protagonist.current_location_id == f"{run.id}-library"
    assert protagonist.current_goal == "greet"
    assert protagonist.status["anomaly_score"] == 0.25


@pytest.mark.asyncio
async def test_truman_world_adapter_seed_supports_generic_alert_status_inputs(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    bundle_root = tmp_path / "scenarios" / "alt_world_alert_seed"
    agent_dir = bundle_root / "agents" / "hero"
    agent_dir.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: alt_world_alert_seed",
                "name: Alt World Alert Seed",
                "version: 1",
                "adapter: narrative_world",
                "semantics:",
                "  subject_role: protagonist",
                "  alert_metric: anomaly_score",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "world.yml").write_text(
        "\n".join(
            [
                "locations:",
                "  - id_suffix: apartment",
                "    name: 住处",
                "    location_type: home",
                "    capacity: 2",
                "    x: 1",
                "    y: 1",
                "    attributes:",
                "      mood: quiet",
                "location_id_map:",
                "  apartment: apartment",
                "occupation_names:",
                "  resident: 住户",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: hero",
                "name: Hero",
                "world_role: protagonist",
                "occupation: resident",
                "home: apartment",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Hero\nBase prompt", encoding="utf-8")
    (agent_dir / "initial.yml").write_text(
        "\n".join(
            [
                "status:",
                "  energy: 0.9",
                "  anomaly_score: 0.4",
                "  alert_score: 0.6",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    run = SimulationRun(
        id="run-alt-world-alert-seed",
        name="alt-world-alert-seed",
        status="running",
        scenario_type="alt_world_alert_seed",
    )
    db_session.add(run)
    await db_session.commit()

    scenario = create_scenario("alt_world_alert_seed", db_session)
    await scenario.seed_demo_run(run)

    agents = await AgentRepository(db_session).list_for_run(run.id)
    protagonist = agents[0]

    assert protagonist.status["anomaly_score"] == 0.4


@pytest.mark.asyncio
async def test_truman_world_seed_builder_prefers_scenario_bundle_agents(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    scenario_agents_root = tmp_path / "scenarios" / "narrative_world" / "agents" / "bundle_agent"
    scenario_agents_root.mkdir(parents=True)
    (tmp_path / "scenarios" / "narrative_world" / "scenario.yml").write_text(
        "\n".join(
            [
                "id: narrative_world",
                "name: Truman World",
                "version: 1",
                "runtime_adapter: narrative_world",
            ]
        ),
        encoding="utf-8",
    )
    (scenario_agents_root / "agent.yml").write_text(
        "\n".join(
            [
                "id: bundle_agent",
                "name: Bundle Agent",
                "world_role: cast",
                "occupation: resident",
                "home: apartment",
            ]
        ),
        encoding="utf-8",
    )
    (scenario_agents_root / "prompt.md").write_text("# Bundle Agent", encoding="utf-8")

    project_agents_root = tmp_path / "agents" / "project_agent"
    project_agents_root.mkdir(parents=True)
    (project_agents_root / "agent.yml").write_text(
        "\n".join(
            [
                "id: project_agent",
                "name: Project Agent",
                "world_role: cast",
                "occupation: resident",
                "home: apartment",
            ]
        ),
        encoding="utf-8",
    )
    (project_agents_root / "prompt.md").write_text("# Project Agent", encoding="utf-8")

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    run = SimulationRun(id="run-scenario-bundle-seed", name="scenario-seed", status="running")
    db_session.add(run)
    await db_session.commit()

    builder = NarrativeWorldSeedBuilder(db_session)
    await builder.seed_demo_run(run)

    agents = await AgentRepository(db_session).list_for_run(run.id)

    assert [agent.name for agent in agents] == ["Bundle Agent"]


@pytest.mark.asyncio
async def test_truman_world_adapter_seed_demo_run_uses_active_bundle_files(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    bundle_root = tmp_path / "scenarios" / "alt_world"
    agent_dir = bundle_root / "agents" / "hero"
    agent_dir.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: alt_world",
                "name: Alt World",
                "version: 1",
                "runtime_adapter: narrative_world",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "world.yml").write_text(
        "\n".join(
            [
                "locations:",
                "  - id_suffix: library",
                "    name: 静水图书馆",
                "    location_type: library",
                "    capacity: 4",
                "    x: 5",
                "    y: 6",
                "    attributes:",
                "      kind: quiet",
                "location_id_map:",
                "  apartment: library",
                "occupation_names:",
                "  resident: 住户",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: hero",
                "name: Hero",
                "world_role: truman",
                "occupation: resident",
                "home: apartment",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Hero\nBase prompt", encoding="utf-8")
    (agent_dir / "bio.md").write_text("Alt bundle hero", encoding="utf-8")

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    run = SimulationRun(
        id="run-alt-world",
        name="alt-world",
        status="running",
        scenario_type="alt_world",
    )
    db_session.add(run)
    await db_session.commit()

    scenario = create_scenario("alt_world", db_session)
    await scenario.seed_demo_run(run)

    agents = await AgentRepository(db_session).list_for_run(run.id)

    assert [agent.name for agent in agents] == ["Hero"]
    assert agents[0].occupation == "住户"
    assert agents[0].home_location_id == f"{run.id}-library"
    assert agents[0].status["suspicion_score"] == 0.0


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
    assert isinstance(create_scenario("narrative_world", db_session), NarrativeWorldScenario)
    assert isinstance(create_scenario(None, db_session), NarrativeWorldScenario)


def test_truman_world_adapter_uses_active_bundle_world_knowledge(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    bundle_root = tmp_path / "scenarios" / "alt_world"
    agent_dir = bundle_root / "agents" / "hero"
    agent_dir.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: alt_world",
                "name: Alt World",
                "version: 1",
                "runtime_adapter: narrative_world",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "world.yml").write_text(
        "\n".join(
            [
                "social_norms:",
                "  - 保持安静排队",
                "location_purposes:",
                "  library:",
                "    - 阅读",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: hero",
                "name: Hero",
                "world_role: truman",
                "occupation: resident",
                "home: apartment",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Hero\nBase prompt", encoding="utf-8")

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

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
