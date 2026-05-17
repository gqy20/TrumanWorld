from __future__ import annotations

import pytest

from app.sim.action_resolver import ActionIntent
from app.sim.persistence import PersistenceManager
from app.sim.service import SimulationService
from app.store.repositories import AgentRepository, EventRepository
from tests.factories import (
    make_agent,
    make_event,
    make_location,
    make_run,
    make_run_with_location_agents,
)


@pytest.mark.asyncio
async def test_simulation_service_updates_relationships_from_talk_events(db_session):
    run, plaza, (alice, bob) = make_run_with_location_agents(
        "run-service-5",
        run_kwargs={"name": "service"},
        location_id="loc-plaza-5",
        location_kwargs={"name": "Plaza"},
        agents=[
            {"agent_id": "alice-5", "name": "Alice"},
            {"agent_id": "bob-5", "name": "Bob"},
        ],
    )

    db_session.add_all([run, plaza, alice, bob])
    await db_session.commit()

    service = SimulationService(db_session)
    result = await service.run_tick(
        "run-service-5",
        [ActionIntent(agent_id="alice-5", action_type="talk", target_agent_id="bob-5")],
    )

    alice_relationships = await AgentRepository(db_session).list_relationships(
        "run-service-5", "alice-5"
    )
    bob_relationships = await AgentRepository(db_session).list_relationships(
        "run-service-5", "bob-5"
    )
    events = await EventRepository(db_session).list_for_run("run-service-5", limit=10)
    alice_memories = await AgentRepository(db_session).list_recent_memories("alice-5")
    bob_memories = await AgentRepository(db_session).list_recent_memories("bob-5")

    assert result.tick_no == 1
    assert len(result.accepted) == 3
    assert {item.action_type for item in result.accepted} == {
        "conversation_started",
        "talk",
        "listen",
    }
    assert (
        next(item for item in result.accepted if item.action_type == "talk").event_payload[
            "conversation_event_type"
        ]
        == "speech"
    )
    assert (
        next(item for item in result.accepted if item.action_type == "listen").event_payload[
            "conversation_event_type"
        ]
        == "listen"
    )
    assert {event.event_type for event in events} == {"conversation_started", "speech", "listen"}
    assert len(alice_relationships) == 1
    assert len(bob_relationships) == 1
    assert alice_relationships[0].other_agent_id == "bob-5"
    assert bob_relationships[0].other_agent_id == "alice-5"
    assert alice_relationships[0].familiarity == 0.1
    assert bob_relationships[0].trust == 0.05
    assert alice_memories[0].summary.startswith("Said to Bob")
    assert bob_memories[0].summary.startswith("Talked with Alice")


@pytest.mark.asyncio
async def test_persistence_relationships_apply_social_location_policy_boost(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    run, cafe, (alice, bob) = make_run_with_location_agents(
        "run-service-relationship-policy",
        run_kwargs={"name": "relationship-policy", "scenario_type": "narrative_world"},
        location_id="loc-cafe-policy",
        location_kwargs={"name": "Cafe", "location_type": "cafe"},
        agents=[
            {"agent_id": "alice-policy", "name": "Alice"},
            {"agent_id": "bob-policy", "name": "Bob"},
        ],
    )
    db_session.add_all([run, cafe, alice, bob])
    await db_session.commit()

    monkeypatch.setattr(
        "app.sim.relationship_persistence.load_world_design_runtime_package",
        lambda _scenario_id: type(
            "Package",
            (),
            {
                "policy_config": type(
                    "Policy", (), {"values": {"social_boost_locations": {"cafe": 0.3}}}
                )()
            },
        )(),
    )

    event = make_event(
        "event-policy-speech",
        run_id=run.id,
        event_type="speech",
        actor_agent_id=alice.id,
        target_agent_id=bob.id,
        location_id=cafe.id,
    )

    await PersistenceManager(db_session).persist_tick_relationships(run.id, [event])

    alice_relationships = await AgentRepository(db_session).list_relationships(run.id, alice.id)
    assert alice_relationships[0].affinity == pytest.approx(0.08)
    assert event.payload["relationship_impact"]["affinity_delta"] == pytest.approx(0.08)
    assert "social_boost:cafe" in event.payload["relationship_impact"]["modifiers"]
    assert event.payload["relationship_impact"]["summary"] == "社交场景提升了亲近感的增长。"


@pytest.mark.asyncio
async def test_persistence_relationships_soft_risk_reduces_social_gain(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    run = make_run(
        "run-service-relationship-soft-risk",
        name="relationship-soft-risk",
        scenario_type="narrative_world",
    )
    plaza = make_location(
        "loc-plaza-soft-risk",
        run_id=run.id,
        name="Plaza",
        location_type="plaza",
    )
    alice = make_agent(
        "alice-soft-risk",
        run_id=run.id,
        location_id=plaza.id,
        name="Alice",
    )
    bob = make_agent(
        "bob-soft-risk",
        run_id=run.id,
        location_id=plaza.id,
        name="Bob",
    )
    db_session.add_all([run, plaza, alice, bob])
    await db_session.commit()

    monkeypatch.setattr(
        "app.sim.relationship_persistence.load_world_design_runtime_package",
        lambda _scenario_id: type(
            "Package", (), {"policy_config": type("Policy", (), {"values": {}})()}
        )(),
    )

    event = make_event(
        "event-soft-risk-speech",
        run_id=run.id,
        event_type="speech",
        actor_agent_id=alice.id,
        target_agent_id=bob.id,
        location_id=plaza.id,
        payload={
            "rule_evaluation": {
                "decision": "soft_risk",
                "reason": "late_night_talk_risk",
                "risk_level": "low",
                "matched_rule_ids": ["late_night_talk_risk"],
            }
        },
    )

    await PersistenceManager(db_session).persist_tick_relationships(run.id, [event])

    alice_relationships = await AgentRepository(db_session).list_relationships(run.id, alice.id)
    assert alice_relationships[0].familiarity == pytest.approx(0.1)
    assert alice_relationships[0].trust < 0.05
    assert alice_relationships[0].affinity < 0.05
    assert event.payload["relationship_impact"]["rule_decision"] == "soft_risk"
    assert event.payload["relationship_impact"]["rule_reason"] == "late_night_talk_risk"
    assert event.payload["relationship_impact"]["risk_level"] == "low"
    assert "soft_risk" in event.payload["relationship_impact"]["modifiers"]
    assert (
        event.payload["relationship_impact"]["summary"]
        == "高风险社交接触降低了信任和亲近感的增长。"
    )


@pytest.mark.asyncio
async def test_persistence_relationships_governance_warn_further_reduces_social_gain(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    run, plaza, (alice, bob) = make_run_with_location_agents(
        "run-service-relationship-governance-warn",
        run_kwargs={"name": "relationship-governance-warn", "scenario_type": "narrative_world"},
        location_id="loc-plaza-governance-warn",
        location_kwargs={"name": "Plaza", "location_type": "plaza"},
        agents=[
            {"agent_id": "alice-governance-warn", "name": "Alice"},
            {"agent_id": "bob-governance-warn", "name": "Bob"},
        ],
    )
    db_session.add_all([run, plaza, alice, bob])
    await db_session.commit()

    monkeypatch.setattr(
        "app.sim.relationship_persistence.load_world_design_runtime_package",
        lambda _scenario_id: type(
            "Package", (), {"policy_config": type("Policy", (), {"values": {}})()}
        )(),
    )

    event = make_event(
        "event-governance-warn-speech",
        run_id=run.id,
        event_type="speech",
        actor_agent_id=alice.id,
        target_agent_id=bob.id,
        location_id=plaza.id,
        payload={
            "governance_execution": {
                "decision": "warn",
                "reason": "high_attention_warning",
                "enforcement_action": "warning",
                "matched_signals": ["high_attention_location"],
            }
        },
    )

    await PersistenceManager(db_session).persist_tick_relationships(run.id, [event])

    alice_relationships = await AgentRepository(db_session).list_relationships(run.id, alice.id)
    assert alice_relationships[0].familiarity == pytest.approx(0.1)
    assert alice_relationships[0].trust == pytest.approx(0.04)
    assert alice_relationships[0].affinity == pytest.approx(0.04)
    assert event.payload["relationship_impact"]["governance_decision"] == "warn"
    assert event.payload["relationship_impact"]["governance_reason"] == "high_attention_warning"
    assert "governance_warn" in event.payload["relationship_impact"]["modifiers"]


@pytest.mark.asyncio
async def test_persistence_relationships_governance_block_turns_social_result_negative(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    run = make_run(
        "run-service-relationship-governance-block",
        name="relationship-governance-block",
        scenario_type="narrative_world",
    )
    plaza = make_location(
        "loc-plaza-governance-block",
        run_id=run.id,
        name="Plaza",
        location_type="plaza",
    )
    alice = make_agent(
        "alice-governance-block",
        run_id=run.id,
        location_id=plaza.id,
        name="Alice",
    )
    bob = make_agent(
        "bob-governance-block",
        run_id=run.id,
        location_id=plaza.id,
        name="Bob",
    )
    db_session.add_all([run, plaza, alice, bob])
    await db_session.commit()

    monkeypatch.setattr(
        "app.sim.relationship_persistence.load_world_design_runtime_package",
        lambda _scenario_id: type(
            "Package", (), {"policy_config": type("Policy", (), {"values": {}})()}
        )(),
    )

    event = make_event(
        "event-governance-block-speech",
        run_id=run.id,
        event_type="speech",
        actor_agent_id=alice.id,
        target_agent_id=bob.id,
        location_id=plaza.id,
        payload={
            "governance_execution": {
                "decision": "block",
                "reason": "location_closed",
                "enforcement_action": "intercept",
                "matched_signals": ["policy_block"],
            }
        },
    )

    await PersistenceManager(db_session).persist_tick_relationships(run.id, [event])

    alice_relationships = await AgentRepository(db_session).list_relationships(run.id, alice.id)
    assert alice_relationships[0].familiarity == pytest.approx(0.1)
    assert alice_relationships[0].trust == pytest.approx(0.0)
    assert alice_relationships[0].affinity == pytest.approx(0.0)
    assert event.payload["relationship_impact"]["governance_decision"] == "block"
    assert event.payload["relationship_impact"]["governance_reason"] == "location_closed"
    assert "governance_block" in event.payload["relationship_impact"]["modifiers"]


@pytest.mark.asyncio
async def test_persistence_relationships_actor_attention_reduces_social_gain(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    run, plaza, (alice, bob) = make_run_with_location_agents(
        "run-service-relationship-actor-attention",
        run_kwargs={"name": "relationship-actor-attention", "scenario_type": "narrative_world"},
        location_id="loc-plaza-actor-attention",
        location_kwargs={"name": "Plaza", "location_type": "plaza"},
        agents=[
            {
                "agent_id": "alice-actor-attention",
                "name": "Alice",
                "status": {"governance_attention_score": 0.6},
            },
            {"agent_id": "bob-actor-attention", "name": "Bob"},
        ],
    )
    db_session.add_all([run, plaza, alice, bob])
    await db_session.commit()

    monkeypatch.setattr(
        "app.sim.relationship_persistence.load_world_design_runtime_package",
        lambda _scenario_id: type(
            "Package", (), {"policy_config": type("Policy", (), {"values": {}})()}
        )(),
    )

    event = make_event(
        "event-actor-attention-speech",
        run_id=run.id,
        event_type="speech",
        actor_agent_id=alice.id,
        target_agent_id=bob.id,
        location_id=plaza.id,
    )

    await PersistenceManager(db_session).persist_tick_relationships(run.id, [event])

    alice_relationships = await AgentRepository(db_session).list_relationships(run.id, alice.id)
    assert alice_relationships[0].trust == pytest.approx(0.04)
    assert alice_relationships[0].affinity == pytest.approx(0.04)
    assert "attention_elevated" in event.payload["relationship_impact"]["modifiers"]
    assert (
        event.payload["relationship_impact"]["summary"] == "制度关注使这次互动的关系增益有所减弱。"
    )


@pytest.mark.asyncio
async def test_persistence_relationships_target_high_attention_further_reduces_social_gain(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    run = make_run(
        "run-service-relationship-target-attention",
        name="relationship-target-attention",
        scenario_type="narrative_world",
    )
    plaza = make_location(
        "loc-plaza-target-attention",
        run_id=run.id,
        name="Plaza",
        location_type="plaza",
    )
    alice = make_agent(
        "alice-target-attention",
        run_id=run.id,
        location_id=plaza.id,
        name="Alice",
    )
    bob = make_agent(
        "bob-target-attention",
        run_id=run.id,
        location_id=plaza.id,
        name="Bob",
        status={"governance_attention_score": 0.85},
    )
    db_session.add_all([run, plaza, alice, bob])
    await db_session.commit()

    monkeypatch.setattr(
        "app.sim.relationship_persistence.load_world_design_runtime_package",
        lambda _scenario_id: type(
            "Package", (), {"policy_config": type("Policy", (), {"values": {}})()}
        )(),
    )

    event = make_event(
        "event-target-attention-speech",
        run_id=run.id,
        event_type="speech",
        actor_agent_id=alice.id,
        target_agent_id=bob.id,
        location_id=plaza.id,
    )

    await PersistenceManager(db_session).persist_tick_relationships(run.id, [event])

    alice_relationships = await AgentRepository(db_session).list_relationships(run.id, alice.id)
    assert alice_relationships[0].trust == pytest.approx(0.03)
    assert alice_relationships[0].affinity == pytest.approx(0.03)
    assert "attention_high" in event.payload["relationship_impact"]["modifiers"]
    assert (
        event.payload["relationship_impact"]["summary"]
        == "高关注状态削弱了这次互动带来的关系增益。"
    )


