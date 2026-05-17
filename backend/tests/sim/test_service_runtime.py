import pytest
from sqlalchemy import select
from datetime import datetime, UTC
from unittest.mock import AsyncMock

from app.cognition.heuristic.agent_backend import HeuristicAgentBackend
import app.director.service as director_service_module
from app.director.service import DirectorEventService
from app.infra.settings import get_settings
from app.scenario.bundle_world.coordinator import BundleWorldCoordinator
from app.scenario.runtime_config import RuntimeRoleSemantics
from app.sim.action_resolver import ActionIntent, ActionResult
from app.sim.persistence import PersistenceManager
from app.sim.runner import TickResult
from app.sim.service import SimulationService
from app.sim.world import WorldState
from app.store.models import Event, GovernanceRecord, SimulationRun
from app.store.repositories import AgentRepository, DirectorMemoryRepository
from tests.factories import (
    make_agent,
    make_event,
    make_location,
    make_run,
    write_agent_config,
)

from .test_service import (
    ContextCapturingDecisionProvider,
    FakeScenario,
    RecordingDecisionProvider,
)


def test_simulation_service_switches_registry_root_with_scenario_bundle(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    scenario_root = tmp_path / "scenarios" / "open_world"
    scenario_root.mkdir(parents=True)
    (scenario_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: open_world",
                "name: Open World",
                "version: 1",
                "runtime_adapter: open_world",
            ]
        ),
        encoding="utf-8",
    )
    (scenario_root / "agents").mkdir()

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    service = SimulationService(db_session)
    service._configure_scenario("open_world")

    assert service.agent_runtime.registry.root == scenario_root / "agents"


@pytest.mark.asyncio
async def test_simulation_service_uses_world_role_and_clock_in_runtime_context(
    db_session, tmp_path
):
    run = make_run(
        "run-service-role-clock",
        name="service",
        current_tick=2,
        tick_minutes=15,
        metadata_json={"world_start_time": "2026-03-02T07:00:00+00:00"},
    )
    home = make_location(
        "loc-home-role-clock",
        run_id="run-service-role-clock",
        name="Home",
        location_type="home",
    )
    park = make_location(
        "loc-park-role-clock",
        run_id="run-service-role-clock",
        name="Park",
        location_type="park",
    )
    write_agent_config(
        tmp_path,
        "truman",
        name="Truman",
        home="loc-home-role-clock",
        world_role="truman",
    )

    truman = make_agent(
        "run-service-role-clock-truman",
        run_id="run-service-role-clock",
        location_id="loc-home-role-clock",
        name="Truman",
        current_goal="move:loc-park-role-clock",
        profile={"agent_config_id": "truman", "world_role": "truman"},
    )

    db_session.add_all([run, home, park, truman])
    await db_session.commit()

    recording_provider = RecordingDecisionProvider()
    runtime = SimulationService(db_session, agents_root=tmp_path).agent_runtime
    runtime.backend = HeuristicAgentBackend(recording_provider)
    service = SimulationService(db_session, agent_runtime=runtime, agents_root=tmp_path)

    result = await service.run_tick("run-service-role-clock")

    assert result.world_time == "2026-03-02T07:45:00+00:00"
    assert recording_provider.agent_ids == ["truman"]


@pytest.mark.asyncio
async def test_simulation_service_includes_director_system_events_for_cast_recent_events(
    db_session, tmp_path
):
    run = make_run(
        "run-service-director-events",
        name="service",
    )
    square = make_location(
        "loc-square-director-events",
        run_id=run.id,
        name="Square",
        location_type="plaza",
    )
    cast = make_agent(
        "run-service-director-events-cast",
        run_id=run.id,
        location_id=square.id,
        name="Meryl",
        current_goal="rest",
        profile={"agent_config_id": "spouse", "world_role": "cast"},
    )
    truman = make_agent(
        "run-service-director-events-truman",
        run_id=run.id,
        location_id=square.id,
        name="Truman",
        current_goal="rest",
        profile={"agent_config_id": "truman", "world_role": "truman"},
    )

    db_session.add_all([run, square, cast, truman])
    await db_session.commit()

    await DirectorEventService(db_session).inject_event(
        run_id=run.id,
        event_type="broadcast",
        payload={"message": "Town hall at plaza"},
        importance=0.8,
    )

    write_agent_config(
        tmp_path,
        "spouse",
        name="Meryl",
        home="loc-square-director-events",
    )
    write_agent_config(
        tmp_path,
        "truman",
        name="Truman",
        home="loc-square-director-events",
    )

    capturing_provider = ContextCapturingDecisionProvider()
    runtime = SimulationService(db_session, agents_root=tmp_path).agent_runtime
    runtime.backend = HeuristicAgentBackend(capturing_provider)
    service = SimulationService(db_session, agent_runtime=runtime, agents_root=tmp_path)

    await service.run_tick(run.id)

    spouse_recent_events = capturing_provider.recent_events_by_agent["spouse"]
    truman_recent_events = capturing_provider.recent_events_by_agent["truman"]

    assert any(event["event_type"] == "director_broadcast" for event in spouse_recent_events)
    assert all(event["event_type"] != "director_broadcast" for event in truman_recent_events)


@pytest.mark.asyncio
async def test_manual_director_intervention_is_not_consumed_in_read_phase(db_session):
    run = make_run(
        "run-service-manual-once",
        name="service",
    )
    square = make_location(
        "loc-square-manual-once",
        run_id=run.id,
        name="Square",
        location_type="plaza",
    )
    cast = make_agent(
        "run-service-manual-once-cast",
        run_id=run.id,
        location_id=square.id,
        name="Meryl",
        current_goal="rest",
        profile={"agent_config_id": "spouse", "world_role": "cast"},
    )
    truman = make_agent(
        "run-service-manual-once-truman",
        run_id=run.id,
        location_id=square.id,
        name="Truman",
        current_goal="rest",
        profile={"agent_config_id": "truman", "world_role": "truman"},
    )

    db_session.add_all([run, square, cast, truman])
    await db_session.commit()

    await DirectorEventService(db_session).inject_event(
        run_id=run.id,
        event_type="broadcast",
        payload={"message": "Town hall at plaza"},
        location_id=square.id,
        importance=0.8,
    )

    agents = list(await AgentRepository(db_session).list_for_run(run.id))
    coordinator = BundleWorldCoordinator(db_session)

    first_plan = await coordinator.build_director_plan(run.id, agents)
    pending = await DirectorMemoryRepository(db_session).get_pending_manual_interventions(
        run_id=run.id,
        current_tick=run.current_tick,
        max_age_ticks=5,
    )

    assert first_plan is not None
    assert first_plan.scene_goal == "gather"
    assert first_plan.location_hint == square.id
    assert len(pending) == 1
    assert pending[0].was_executed is False


@pytest.mark.asyncio
async def test_director_event_service_uses_subject_role_semantics_for_manual_events(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    run = make_run(
        "run-service-manual-semantics",
        name="service",
        scenario_type="hero_world",
    )
    square = make_location(
        "loc-square-manual-semantics",
        run_id=run.id,
        name="Square",
        location_type="plaza",
    )
    ally = make_agent(
        "run-service-manual-semantics-ally",
        run_id=run.id,
        location_id=square.id,
        name="Guide",
        current_goal="rest",
        profile={"agent_config_id": "guide", "world_role": "ally"},
    )
    protagonist = make_agent(
        "run-service-manual-semantics-protagonist",
        run_id=run.id,
        location_id=square.id,
        name="Hero",
        current_goal="rest",
        profile={"agent_config_id": "hero", "world_role": "protagonist"},
    )
    db_session.add_all([run, square, ally, protagonist])
    await db_session.commit()

    monkeypatch.setattr(
        director_service_module,
        "build_runtime_role_semantics",
        lambda scenario_id: RuntimeRoleSemantics(
            subject_role="protagonist",
            support_roles=["ally"],
            alert_metric="anomaly_score",
        ),
    )

    await DirectorEventService(db_session).inject_event(
        run_id=run.id,
        event_type="broadcast",
        payload={"message": "Town hall at plaza"},
        location_id=square.id,
        importance=0.8,
    )

    memories = await DirectorMemoryRepository(db_session).list_for_run(run.id)

    assert len(memories) == 1
    assert memories[0].target_agent_id == protagonist.id
    assert memories[0].target_agent_ids == f'["{ally.id}"]'


@pytest.mark.asyncio
async def test_seed_demo_run_creates_narrative_world_agents(db_session):
    run = SimulationRun(id="run-demo-seed", name="demo-seed", status="running")
    db_session.add(run)
    await db_session.commit()

    service = SimulationService(db_session)
    await service.seed_demo_run("run-demo-seed")

    agents = await AgentRepository(db_session).list_for_run("run-demo-seed")

    assert [agent.name for agent in agents] == [
        "Alice",
        "Bob",
        "Lauren",
        "Marlon",
        "Meryl",
        "Truman",
    ]
    profile_by_name = {agent.name: agent.profile for agent in agents}
    assert profile_by_name["Truman"]["world_role"] == "truman"
    assert profile_by_name["Meryl"]["world_role"] == "cast"
    assert profile_by_name["Alice"]["world_role"] == "cast"


@pytest.mark.asyncio
async def test_simulation_service_updates_subject_alert_from_rejected_events(db_session):
    run = make_run(
        "run-truman-suspicion",
        name="suspicion",
    )
    home = make_location(
        "loc-home-suspicion",
        run_id="run-truman-suspicion",
        name="Home",
        location_type="home",
    )
    truman = make_agent(
        "truman-suspicion",
        run_id="run-truman-suspicion",
        location_id="loc-home-suspicion",
        name="Truman",
        profile={"world_role": "truman", "agent_config_id": "truman"},
        status={"suspicion_score": 0.1},
    )

    db_session.add_all([run, home, truman])
    await db_session.commit()

    service = SimulationService(db_session)
    await service.run_tick(
        "run-truman-suspicion",
        [
            ActionIntent(
                agent_id="truman-suspicion",
                action_type="move",
                target_location_id="missing-location",
            )
        ],
    )

    await db_session.refresh(truman)
    updated = await AgentRepository(db_session).get("truman-suspicion")

    assert updated is not None
    assert updated.status["suspicion_score"] > 0.1


@pytest.mark.asyncio
async def test_simulation_service_accepts_injected_scenario(db_session):
    run = make_run(
        "run-fake-scenario",
        name="fake-scenario",
    )
    home = make_location(
        "loc-home-fake",
        run_id="run-fake-scenario",
        name="Home",
        location_type="home",
    )
    agent = make_agent(
        "agent-fake",
        run_id="run-fake-scenario",
        location_id="loc-home-fake",
        name="Agent",
        current_goal="rest",
    )

    db_session.add_all([run, home, agent])
    await db_session.commit()

    scenario = FakeScenario()
    service = SimulationService(db_session, scenario=scenario)
    result = await service.run_tick(
        "run-fake-scenario",
        [ActionIntent(agent_id="agent-fake", action_type="rest")],
    )

    assert scenario.runtime_configured is True
    assert scenario.state_update_calls == [("run-fake-scenario", 1)]
    assert result.tick_no == 1


@pytest.mark.asyncio
async def test_persist_tick_memories_adds_governance_warning_memory(db_session):
    run = make_run(
        "run-governance-warning-memory",
        name="governance-warning-memory",
    )
    plaza = make_location(
        "loc-governance-warning-memory",
        run_id=run.id,
        name="Plaza",
        location_type="plaza",
    )
    alice = make_agent(
        "alice-governance-warning-memory",
        run_id=run.id,
        location_id=plaza.id,
        name="Alice",
    )
    db_session.add_all([run, plaza, alice])
    await db_session.commit()

    event = make_event(
        "event-governance-warning-memory",
        run_id=run.id,
        event_type="move",
        actor_agent_id=alice.id,
        location_id=plaza.id,
        importance=0.8,
        payload={
            "to_location_id": plaza.id,
            "governance_execution": {
                "decision": "warn",
                "reason": "high_attention_warning",
                "enforcement_action": "warning",
                "matched_signals": ["high_attention_location"],
            },
        },
    )

    await PersistenceManager(db_session).persist_tick_memories(run.id, [event])

    memories = await AgentRepository(db_session).list_recent_memories(alice.id, limit=10)
    summaries = [memory.summary for memory in memories]
    assert "Governance warning: high_attention_warning" in summaries


@pytest.mark.asyncio
async def test_persist_tick_results_creates_governance_record_ledger_entries(db_session):
    run = make_run(
        "run-governance-ledger",
        name="governance-ledger",
    )
    plaza = make_location(
        "loc-governance-ledger",
        run_id=run.id,
        name="Plaza",
        location_type="plaza",
    )
    alice = make_agent(
        "alice-governance-ledger",
        run_id=run.id,
        location_id=plaza.id,
        name="Alice",
    )
    db_session.add_all([run, plaza, alice])
    await db_session.commit()

    event = make_event(
        "event-governance-ledger",
        run_id=run.id,
        event_type="talk",
        actor_agent_id=alice.id,
        location_id=plaza.id,
        importance=0.6,
        payload={
            "agent_id": alice.id,
            "governance_execution": {
                "decision": "record_only",
                "reason": "late_night_talk_risk",
                "enforcement_action": "record",
                "observed": True,
                "observation_score": 0.61,
                "intervention_score": 0.62,
                "matched_signals": ["social"],
            },
        },
    )

    await PersistenceManager(db_session).persist_tick_governance_records(run.id, [event])

    records = (
        (
            await db_session.execute(
                select(GovernanceRecord).where(GovernanceRecord.run_id == run.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(records) == 1
    assert records[0].agent_id == alice.id
    assert records[0].decision == "record_only"
    assert records[0].reason == "late_night_talk_risk"
    assert records[0].observed is True
    assert records[0].observation_score == 0.61
    assert records[0].intervention_score == 0.62
    assert records[0].source_event_id == event.id


@pytest.mark.asyncio
async def test_persist_tick_results_rolls_back_events_when_followup_persistence_fails(db_session):
    run = make_run(
        "run-persist-atomic",
        name="persist-atomic",
    )
    home = make_location(
        "loc-persist-atomic",
        run_id=run.id,
        name="Home",
        location_type="home",
    )
    alice = make_agent(
        "alice-persist-atomic",
        run_id=run.id,
        location_id=home.id,
        name="Alice",
    )
    db_session.add_all([run, home, alice])
    await db_session.commit()
    run_id = run.id

    manager = PersistenceManager(db_session)

    async def fail_memories(*_args, **_kwargs):
        raise RuntimeError("memory write failed")

    manager.persist_tick_memories = fail_memories
    manager.persist_tick_governance_cases = AsyncMock()
    manager.persist_tick_economic_state = AsyncMock()
    manager.persist_tick_relationships = AsyncMock()
    world = WorldState(current_time=datetime(2026, 3, 2, 6, 0, tzinfo=UTC), current_tick=0)
    result = TickResult(
        tick_no=1,
        world_time="2026-03-02T06:05:00+00:00",
        tick_delta=1,
        accepted=[
            ActionResult(
                accepted=True,
                action_type="rest",
                reason="accepted",
                event_payload={"agent_id": alice.id, "location_id": home.id},
            )
        ],
        rejected=[],
    )

    with pytest.raises(RuntimeError, match="memory write failed"):
        await manager.persist_tick_results(run_id, result, world, new_tick=1)

    await db_session.rollback()
    persisted_events = (
        (
            await db_session.execute(select(Event).where(Event.run_id == run_id))
        )
        .scalars()
        .all()
    )
    refreshed_run = await db_session.get(SimulationRun, run_id)

    assert persisted_events == []
    assert refreshed_run is not None
    assert refreshed_run.current_tick == 0


@pytest.mark.asyncio
async def test_persist_tick_memories_includes_governance_block_for_rejected_event(db_session):
    run = make_run(
        "run-governance-block-memory",
        name="governance-block-memory",
    )
    plaza = make_location(
        "loc-governance-block-memory",
        run_id=run.id,
        name="Plaza",
        location_type="plaza",
    )
    alice = make_agent(
        "alice-governance-block-memory",
        run_id=run.id,
        location_id=plaza.id,
        name="Alice",
    )
    db_session.add_all([run, plaza, alice])
    await db_session.commit()

    event = make_event(
        "event-governance-block-memory",
        run_id=run.id,
        event_type="move_rejected",
        actor_agent_id=alice.id,
        location_id=plaza.id,
        importance=0.9,
        payload={
            "reason": "location_closed",
            "governance_execution": {
                "decision": "block",
                "reason": "location_closed",
                "enforcement_action": "intercept",
                "matched_signals": ["policy_block"],
            },
        },
    )

    await PersistenceManager(db_session).persist_tick_memories(run.id, [event])

    memories = await AgentRepository(db_session).list_recent_memories(alice.id, limit=10)
    summaries = [memory.summary for memory in memories]
    assert "Governance block: location_closed" in summaries


@pytest.mark.asyncio
async def test_persist_tick_memories_adds_governance_record_memory(db_session):
    run = make_run(
        "run-governance-record-memory",
        name="governance-record-memory",
    )
    plaza = make_location(
        "loc-governance-record-memory",
        run_id=run.id,
        name="Plaza",
        location_type="plaza",
    )
    alice = make_agent(
        "alice-governance-record-memory",
        run_id=run.id,
        location_id=plaza.id,
        name="Alice",
    )
    db_session.add_all([run, plaza, alice])
    await db_session.commit()

    event = make_event(
        "event-governance-record-memory",
        run_id=run.id,
        event_type="talk",
        actor_agent_id=alice.id,
        location_id=plaza.id,
        importance=0.6,
        payload={
            "governance_execution": {
                "decision": "record_only",
                "reason": "late_night_talk_risk",
                "enforcement_action": "record",
                "matched_signals": ["social"],
            },
        },
    )

    await PersistenceManager(db_session).persist_tick_memories(run.id, [event])

    memories = await AgentRepository(db_session).list_recent_memories(alice.id, limit=10)
    summaries = [memory.summary for memory in memories]
    assert "Governance record: late_night_talk_risk" in summaries


@pytest.mark.asyncio
async def test_persist_tick_memories_includes_soft_risk_rule_feedback_memory(db_session):
    run = make_run(
        "run-rule-feedback-memory",
        name="rule-feedback-memory",
    )
    plaza = make_location(
        "loc-rule-feedback-memory",
        run_id=run.id,
        name="Plaza",
        location_type="plaza",
    )
    alice = make_agent(
        "alice-rule-feedback-memory",
        run_id=run.id,
        location_id=plaza.id,
        name="Alice",
    )
    db_session.add_all([run, plaza, alice])
    await db_session.commit()

    event = make_event(
        "event-rule-feedback-memory",
        run_id=run.id,
        event_type="talk",
        actor_agent_id=alice.id,
        location_id=plaza.id,
        importance=0.7,
        payload={
            "message": "Want to talk?",
            "rule_evaluation": {
                "decision": "soft_risk",
                "reason": "late_night_talk_risk",
                "matched_tags": ["night", "social"],
            },
        },
    )

    await PersistenceManager(db_session).persist_tick_memories(run.id, [event])

    memories = await AgentRepository(db_session).list_recent_memories(alice.id, limit=10)
    summaries = [memory.summary for memory in memories]
    assert "Rule risk: late_night_talk_risk" in summaries


@pytest.mark.asyncio
async def test_persist_tick_memories_includes_rule_block_feedback_without_governance(db_session):
    run = make_run(
        "run-rule-block-memory",
        name="rule-block-memory",
    )
    cafe = make_location(
        "loc-rule-block-memory",
        run_id=run.id,
        name="Cafe",
        location_type="cafe",
    )
    alice = make_agent(
        "alice-rule-block-memory",
        run_id=run.id,
        location_id=cafe.id,
        name="Alice",
    )
    db_session.add_all([run, cafe, alice])
    await db_session.commit()

    event = make_event(
        "event-rule-block-memory",
        run_id=run.id,
        event_type="move_rejected",
        actor_agent_id=alice.id,
        location_id=cafe.id,
        importance=0.8,
        payload={
            "reason": "location_closed",
            "rule_evaluation": {
                "decision": "violates_rule",
                "reason": "location_closed",
                "matched_tags": ["closure"],
            },
        },
    )

    await PersistenceManager(db_session).persist_tick_memories(run.id, [event])

    memories = await AgentRepository(db_session).list_recent_memories(alice.id, limit=10)
    summaries = [memory.summary for memory in memories]
    assert "Rule block: location_closed" in summaries


