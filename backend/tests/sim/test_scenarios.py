from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.agent.context_builder import ContextBuilder
from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.scenario.factory import create_scenario
from app.scenario.bundle_world import module_registry as bundle_module_registry
from app.scenario.bundle_world.scenario import BundleWorldScenario
from app.scenario.bundle_world.seed import BundleWorldSeedBuilder
from app.store.models import Agent, Event, Location, Relationship, SimulationRun
from app.store.repositories import AgentRepository
from tests.factories import make_agent, make_event, make_location, make_run, write_agent_config

from .helpers import configure_project_root, write_hero_bundle, write_lines


def test_narrative_world_scenario_configures_runtime_context(tmp_path):
    write_agent_config(
        tmp_path,
        "truman",
        name="Truman",
        home="demo_home",
        world_role="truman",
    )

    runtime = AgentRuntime(registry=AgentRegistry(tmp_path), context_builder=ContextBuilder())
    BundleWorldScenario().configure_runtime(runtime)

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


def test_narrative_world_scenario_registers_fallback_hook_on_runtime(tmp_path):
    write_agent_config(
        tmp_path,
        "demo_agent",
        name="Demo Agent",
        home="demo_home",
    )

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

    BundleWorldScenario().configure_runtime(runtime)

    assert backend.hook is not None


def test_narrative_world_scenario_fallback_talks_to_nearby_agent():
    scenario = BundleWorldScenario()

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


def test_narrative_world_scenario_fallback_uses_director_guidance_location_hint():
    scenario = BundleWorldScenario()

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


def test_narrative_world_scenario_fallback_returns_home_when_idle_and_away():
    scenario = BundleWorldScenario()

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
async def test_narrative_world_scenario_seed_and_state_update(db_session):
    run = make_run("run-scenario-seed", name="scenario-seed")
    db_session.add(run)
    await db_session.commit()

    scenario = BundleWorldScenario(db_session)
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
    event = make_event(
        "evt-scenario",
        run_id=run.id,
        event_type="move_rejected",
        actor_agent_id=truman.id,
        payload={"agent_id": truman.id},
    )

    await scenario.update_state_from_events(run.id, [event])
    await db_session.refresh(truman)

    assert truman.status["suspicion_score"] > starting_score


@pytest.mark.asyncio
async def test_campus_world_bundle_seeds_from_repo_scenarios(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    project_root = Path(__file__).resolve().parents[3]
    configure_project_root(project_root, monkeypatch)

    run = make_run(
        "run-campus-world",
        name="campus-world",
        scenario_type="campus_world",
    )
    db_session.add(run)
    await db_session.commit()

    scenario = create_scenario("campus_world", db_session)
    await scenario.seed_demo_run(run)

    agents = await AgentRepository(db_session).list_for_run(run.id)

    assert sorted(agent.name for agent in agents) == ["Lin", "Mei", "Professor Chen"]

    lin = next(agent for agent in agents if (agent.profile or {}).get("world_role") == "student")
    assert lin.occupation == "学生"
    assert lin.status["anomaly_score"] == 0.0
    assert lin.home_location_id == f"{run.id}-dorm"
    assert lin.profile["workplace_location_id"] == f"{run.id}-lecture-hall"


def test_narrative_world_scenario_defaults_subject_alert_tracking_enabled():
    scenario = BundleWorldScenario()

    assert scenario.subject_alert_tracking_enabled is True


@pytest.mark.asyncio
async def test_bundle_world_scenario_assembles_modules_from_manifest(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    class CustomDirectorPolicy:
        def __init__(self, session, *, scenario_id: str) -> None:
            self.session = session
            self.scenario_id = scenario_id
            self.coordinator = object()

        async def observe_run(self, run_id: str, event_limit: int = 20):
            return None

        def assess(self, *, run_id: str, current_tick: int, agents: list, events: list):
            return None

        async def build_director_plan(self, run_id: str, agents: list):
            return None

        async def persist_director_plan(self, run_id: str, plan) -> None:
            return None

    class CustomAgentContextPolicy:
        def __init__(self, *, scenario_id: str, semantics) -> None:
            self.scenario_id = scenario_id
            self.semantics = semantics

        def configure_agent_context(self, context_builder) -> None:
            return None

    class CustomAllowedActionsPolicy:
        def __init__(self) -> None:
            self.actions = ["observe", "signal"]

        def configure_runtime(self, agent_runtime) -> None:
            agent_runtime.configure_allowed_actions(self.allowed_actions())

        def allowed_actions(self) -> list[str]:
            return list(self.actions)

    class CustomProfileMergePolicy:
        def merge_agent_profile(self, agent, plan):
            return {"profile_source": "custom"}

    class CustomFallbackPolicy:
        def __init__(self, *, scenario_id: str, semantics) -> None:
            self.scenario_id = scenario_id
            self.semantics = semantics

        def configure_runtime(self, agent_runtime) -> None:
            return None

        def fallback_intent(self, **kwargs):
            return None

    class CustomSeedPolicy:
        def __init__(self, session, *, scenario_id: str) -> None:
            self.session = session
            self.scenario_id = scenario_id

        async def seed_demo_run(self, run) -> None:
            return None

    class CustomStateUpdatePolicy:
        def __init__(self, session, *, semantics) -> None:
            self.session = session
            self.semantics = semantics

        async def persist_subject_alert(self, run_id: str, events: list[Event]) -> None:
            return None

    bundle_module_registry.get_bundle_world_module_registry().register_fallback_policy(
        "custom_fallback", CustomFallbackPolicy
    )
    bundle_module_registry.get_bundle_world_module_registry().register_director_policy(
        "custom_director", CustomDirectorPolicy
    )
    bundle_module_registry.get_bundle_world_module_registry().register_agent_context_policy(
        "custom_context", CustomAgentContextPolicy
    )
    bundle_module_registry.get_bundle_world_module_registry().register_allowed_actions_policy(
        "custom_actions", CustomAllowedActionsPolicy
    )
    bundle_module_registry.get_bundle_world_module_registry().register_profile_merge_policy(
        "custom_profile_merge", CustomProfileMergePolicy
    )
    bundle_module_registry.get_bundle_world_module_registry().register_seed_policy(
        "custom_seed", CustomSeedPolicy
    )
    bundle_module_registry.get_bundle_world_module_registry().register_state_update_policy(
        "custom_state", CustomStateUpdatePolicy
    )

    bundle_root = tmp_path / "scenarios" / "hero_world"
    bundle_root.mkdir(parents=True)
    write_lines(
        bundle_root / "scenario.yml",
        [
            "id: hero_world",
            "name: Hero World",
            "version: 1",
            "adapter: bundle_world",
            "modules:",
            "  director_policy: custom_director",
            "  agent_context_policy: custom_context",
            "  allowed_actions_policy: custom_actions",
            "  profile_merge_policy: custom_profile_merge",
            "  fallback_policy: custom_fallback",
            "  seed_policy: custom_seed",
            "  state_update_policy: custom_state",
        ],
    )

    configure_project_root(tmp_path, monkeypatch)

    scenario = BundleWorldScenario(db_session, scenario_id="hero_world")

    assert scenario.module_ids["fallback_policy"] == "custom_fallback"
    assert scenario.module_ids["director_policy"] == "custom_director"
    assert scenario.module_ids["agent_context_policy"] == "custom_context"
    assert scenario.module_ids["allowed_actions_policy"] == "custom_actions"
    assert scenario.module_ids["profile_merge_policy"] == "custom_profile_merge"
    assert scenario.module_ids["seed_policy"] == "custom_seed"
    assert scenario.module_ids["state_update_policy"] == "custom_state"
    assert isinstance(scenario.director_policy, CustomDirectorPolicy)
    assert isinstance(scenario.agent_context_policy, CustomAgentContextPolicy)
    assert isinstance(scenario.allowed_actions_policy, CustomAllowedActionsPolicy)
    assert isinstance(scenario.profile_merge_policy, CustomProfileMergePolicy)
    assert isinstance(scenario.fallback_policy, CustomFallbackPolicy)
    assert isinstance(scenario.seed_builder, CustomSeedPolicy)
    assert isinstance(scenario.state_updater, CustomStateUpdatePolicy)
    assert scenario.allowed_actions() == ["observe", "signal"]


@pytest.mark.asyncio
async def test_narrative_world_adapter_updates_configured_subject_alert_metric(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    write_hero_bundle(
        tmp_path,
        "alt_world",
        scenario_lines=[
            "id: alt_world",
            "name: Alt World",
            "version: 1",
            "adapter: narrative_world",
            "semantics:",
            "  subject_role: protagonist",
            "  support_roles:",
            "    - ally",
            "  alert_metric: anomaly_score",
        ],
        world_lines=[
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
        ],
        agent_lines=[
            "id: hero",
            "name: Hero",
            "world_role: protagonist",
            "occupation: resident",
            "home: apartment",
        ],
        bio="Alt bundle hero",
    )
    configure_project_root(tmp_path, monkeypatch)

    run = make_run(
        "run-alt-world-alert",
        name="alt-world-alert",
        scenario_type="alt_world",
    )
    db_session.add(run)
    await db_session.commit()

    scenario = create_scenario("alt_world", db_session)
    await scenario.seed_demo_run(run)

    agents = await AgentRepository(db_session).list_for_run(run.id)
    protagonist = next(
        agent for agent in agents if (agent.profile or {}).get("world_role") == "protagonist"
    )
    starting_score = float((protagonist.status or {}).get("anomaly_score", 0.0))
    event = make_event(
        "evt-alt-world-alert",
        run_id=run.id,
        event_type="move_rejected",
        actor_agent_id=protagonist.id,
        payload={"agent_id": protagonist.id},
    )

    await scenario.update_state_from_events(run.id, [event])
    await db_session.refresh(protagonist)

    assert protagonist.status["anomaly_score"] > starting_score


@pytest.mark.asyncio
async def test_narrative_world_update_state_reuses_external_transaction(db_session):
    run = make_run(
        "run-scenario-update-transaction",
        name="original",
    )
    home = make_location(
        "loc-scenario-update-transaction",
        run_id=run.id,
        name="Home",
        location_type="home",
    )
    truman = make_agent(
        "truman-scenario-update-transaction",
        run_id=run.id,
        location_id=home.id,
        name="Truman",
        profile={"world_role": "truman", "agent_config_id": "truman"},
        status={"suspicion_score": 0.1},
    )
    db_session.add_all([run, home, truman])
    await db_session.commit()
    run_id = run.id
    truman_id = truman.id

    run.name = "pending-change"
    event = make_event(
        "evt-scenario-update-transaction",
        run_id=run_id,
        event_type="move_rejected",
        actor_agent_id=truman_id,
        payload={"agent_id": truman_id},
    )

    await BundleWorldScenario(db_session).update_state_from_events(run_id, [event])
    await db_session.rollback()

    refreshed_run = await db_session.get(SimulationRun, run_id)
    refreshed_truman = await db_session.get(Agent, truman_id)

    assert refreshed_run is not None
    assert refreshed_run.name == "original"
    assert refreshed_truman is not None
    assert refreshed_truman.status["suspicion_score"] == 0.1


@pytest.mark.asyncio
async def test_narrative_world_adapter_skips_subject_alert_updates_when_tracking_disabled(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    write_hero_bundle(
        tmp_path,
        "alt_world_no_alert",
        scenario_lines=[
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
        ],
        world_lines=[
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
        ],
        agent_lines=[
            "id: hero",
            "name: Hero",
            "world_role: protagonist",
            "occupation: resident",
            "home: apartment",
        ],
        bio="Alt bundle hero",
    )
    configure_project_root(tmp_path, monkeypatch)

    run = make_run(
        "run-alt-world-no-alert",
        name="alt-world-no-alert",
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
    event = make_event(
        "evt-alt-world-no-alert",
        run_id=run.id,
        event_type="move_rejected",
        actor_agent_id=protagonist.id,
        payload={"agent_id": protagonist.id},
    )

    await scenario.update_state_from_events(run.id, [event])
    await db_session.refresh(protagonist)

    assert protagonist.status["anomaly_score"] == starting_score


@pytest.mark.asyncio
async def test_narrative_world_adapter_seed_supports_spawn_aliases(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    write_hero_bundle(
        tmp_path,
        "alt_world_spawn",
        scenario_lines=[
            "id: alt_world_spawn",
            "name: Alt World Spawn",
            "version: 1",
            "adapter: narrative_world",
            "semantics:",
            "  subject_role: protagonist",
            "  alert_metric: anomaly_score",
        ],
        world_lines=[
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
        ],
        agent_lines=[
            "id: hero",
            "name: Hero",
            "world_role: protagonist",
            "occupation: resident",
            "home: apartment",
        ],
        initial_lines=[
            "status:",
            "  energy: 0.9",
            "  alert_score: 0.25",
            "spawn:",
            "  location: workplace",
            "  goal: greet",
            "plan:",
            "  default: patrol",
        ],
    )
    configure_project_root(tmp_path, monkeypatch)

    run = make_run(
        "run-alt-world-spawn",
        name="alt-world-spawn",
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
async def test_narrative_world_adapter_seed_supports_generic_alert_status_inputs(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    write_hero_bundle(
        tmp_path,
        "alt_world_alert_seed",
        scenario_lines=[
            "id: alt_world_alert_seed",
            "name: Alt World Alert Seed",
            "version: 1",
            "adapter: narrative_world",
            "semantics:",
            "  subject_role: protagonist",
            "  alert_metric: anomaly_score",
        ],
        world_lines=[
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
        ],
        agent_lines=[
            "id: hero",
            "name: Hero",
            "world_role: protagonist",
            "occupation: resident",
            "home: apartment",
        ],
        initial_lines=[
            "status:",
            "  energy: 0.9",
            "  anomaly_score: 0.4",
            "  alert_score: 0.6",
        ],
    )
    configure_project_root(tmp_path, monkeypatch)

    run = make_run(
        "run-alt-world-alert-seed",
        name="alt-world-alert-seed",
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
async def test_narrative_world_seed_builder_prefers_scenario_bundle_agents(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    scenario_agents_root = tmp_path / "scenarios" / "narrative_world" / "agents" / "bundle_agent"
    scenario_agents_root.mkdir(parents=True)
    write_lines(
        tmp_path / "scenarios" / "narrative_world" / "scenario.yml",
        [
            "id: narrative_world",
            "name: Narrative World",
            "version: 1",
            "runtime_adapter: narrative_world",
        ],
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

    configure_project_root(tmp_path, monkeypatch)

    run = make_run("run-scenario-bundle-seed", name="scenario-seed")
    db_session.add(run)
    await db_session.commit()

    builder = BundleWorldSeedBuilder(db_session)
    await builder.seed_demo_run(run)

    agents = await AgentRepository(db_session).list_for_run(run.id)

    assert [agent.name for agent in agents] == ["Bundle Agent"]


@pytest.mark.asyncio
async def test_narrative_world_adapter_seed_demo_run_uses_active_bundle_files(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    write_hero_bundle(
        tmp_path,
        "alt_world",
        scenario_lines=[
            "id: alt_world",
            "name: Alt World",
            "version: 1",
            "runtime_adapter: narrative_world",
        ],
        world_lines=[
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
        ],
        bio="Alt bundle hero",
    )
    configure_project_root(tmp_path, monkeypatch)

    run = make_run(
        "run-alt-world",
        name="alt-world",
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
    assert run.metadata_json["world_start_time"] == "2026-03-02T06:00:00+00:00"


@pytest.mark.asyncio
async def test_bundle_seed_rolls_back_seed_records_when_final_commit_fails(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    write_hero_bundle(
        tmp_path,
        "seed_failure_world",
        scenario_lines=[
            "id: seed_failure_world",
            "name: Seed Failure World",
            "version: 1",
            "runtime_adapter: narrative_world",
        ],
        world_lines=[
            "locations:",
            "  - id_suffix: apartment",
            "    name: Test Apartment",
            "    location_type: home",
            "    capacity: 2",
            "    x: 1",
            "    y: 1",
            "    attributes:",
            "      kind: private",
            "location_id_map:",
            "  apartment: apartment",
        ],
    )
    configure_project_root(tmp_path, monkeypatch)

    run = make_run(
        "run-seed-failure-world",
        name="seed-failure-world",
        scenario_type="seed_failure_world",
    )
    db_session.add(run)
    await db_session.commit()
    run_id = run.id

    async def fail_commit() -> None:
        raise RuntimeError("seed commit failed")

    monkeypatch.setattr(db_session, "commit", fail_commit)

    scenario = create_scenario("seed_failure_world", db_session)
    with pytest.raises(RuntimeError, match="seed commit failed"):
        await scenario.seed_demo_run(run)

    await db_session.rollback()
    locations = (
        (await db_session.execute(select(Location).where(Location.run_id == run_id)))
        .scalars()
        .all()
    )
    agents = (await db_session.execute(select(Agent).where(Agent.run_id == run_id))).scalars().all()
    relationships = (
        (await db_session.execute(select(Relationship).where(Relationship.run_id == run_id)))
        .scalars()
        .all()
    )

    assert locations == []
    assert agents == []
    assert relationships == []


@pytest.mark.asyncio
async def test_bundle_seed_uses_world_start_time_from_scenario_world_config(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    write_hero_bundle(
        tmp_path,
        "late_world",
        scenario_lines=[
            "id: late_world",
            "name: Late World",
            "version: 1",
            "runtime_adapter: narrative_world",
        ],
        world_lines=[
            "world_start_time: 2030-01-15T09:30:00+00:00",
            "locations:",
            "  - id_suffix: apartment",
            "    name: Harbor Flat",
            "    location_type: home",
            "    capacity: 2",
            "    x: 1",
            "    y: 1",
            "    attributes:",
            "      kind: private",
            "location_id_map:",
            "  apartment: apartment",
            "occupation_names:",
            "  resident: Resident",
        ],
        bio="Late world hero",
    )
    configure_project_root(tmp_path, monkeypatch)

    run = make_run(
        "run-late-world",
        name="late-world",
        scenario_type="late_world",
    )
    db_session.add(run)
    await db_session.commit()

    scenario = create_scenario("late_world", db_session)
    await scenario.seed_demo_run(run)

    assert run.metadata_json["world_start_time"] == "2030-01-15T09:30:00+00:00"


@pytest.mark.asyncio
async def test_bundle_seed_preserves_explicit_run_world_start_time(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    write_hero_bundle(
        tmp_path,
        "override_world",
        scenario_lines=[
            "id: override_world",
            "name: Override World",
            "version: 1",
            "runtime_adapter: narrative_world",
        ],
        world_lines=[
            "world_start_time: 2035-06-01T08:00:00+00:00",
            "locations:",
            "  - id_suffix: apartment",
            "    name: Lantern House",
            "    location_type: home",
            "    capacity: 2",
            "    x: 1",
            "    y: 1",
            "    attributes:",
            "      kind: private",
            "location_id_map:",
            "  apartment: apartment",
            "occupation_names:",
            "  resident: Resident",
        ],
        bio="Override world hero",
    )
    configure_project_root(tmp_path, monkeypatch)

    run = make_run(
        "run-override-world",
        name="override-world",
        scenario_type="override_world",
        metadata_json={"world_start_time": "2040-12-31T23:55:00+00:00"},
    )
    db_session.add(run)
    await db_session.commit()

    scenario = create_scenario("override_world", db_session)
    await scenario.seed_demo_run(run)

    assert run.metadata_json["world_start_time"] == "2040-12-31T23:55:00+00:00"
