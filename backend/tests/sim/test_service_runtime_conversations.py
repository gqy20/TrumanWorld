from __future__ import annotations

import pytest

from app.sim.action_resolver import ActionIntent
from app.sim.service import SimulationService
from app.store.repositories import AgentRepository, EventRepository
from tests.factories import make_run_with_location_agents


@pytest.mark.asyncio
async def test_simulation_service_persists_rejected_talk_with_requested_target_only(db_session):
    run, plaza, (alice, bob) = make_run_with_location_agents(
        "run-invalid-target",
        run_kwargs={"name": "invalid-target"},
        location_id="loc-plaza-invalid-target",
        location_kwargs={"name": "Plaza", "location_type": "plaza"},
        agents=[
            {"agent_id": "alice-invalid-target", "name": "Alice"},
            {"agent_id": "bob-invalid-target", "name": "Bob"},
        ],
    )

    db_session.add_all([run, plaza, alice, bob])
    await db_session.commit()

    service = SimulationService(db_session)
    result = await service.run_tick(
        run.id,
        [
            ActionIntent(
                agent_id=alice.id,
                action_type="talk",
                target_agent_id="marlon",
                payload={"message": "Hi Marlon."},
            )
        ],
    )

    events = await EventRepository(db_session).list_for_run(run.id, limit=10)

    assert len(result.rejected) == 1
    assert events[0].event_type == "talk_rejected"
    assert events[0].target_agent_id is None
    assert events[0].payload["requested_target_agent_id"] == "marlon"


@pytest.mark.asyncio
async def test_talk_memories_use_subjective_importance_per_agent(db_session):
    run, plaza, (alice, bob) = make_run_with_location_agents(
        "run-memory-subjective",
        run_kwargs={"name": "subjective"},
        location_id="loc-plaza-subjective",
        location_kwargs={"name": "Plaza", "location_type": "plaza"},
        agents=[
            {"agent_id": "alice-subjective", "name": "Alice", "current_goal": "talk"},
            {"agent_id": "bob-subjective", "name": "Bob", "current_goal": "rest"},
        ],
    )

    db_session.add_all([run, plaza, alice, bob])
    await db_session.commit()

    service = SimulationService(db_session)
    await service.run_tick(
        "run-memory-subjective",
        [
            ActionIntent(
                agent_id="alice-subjective",
                action_type="talk",
                target_agent_id="bob-subjective",
                payload={"message": "I am really worried about you."},
            )
        ],
    )

    alice_memories = await AgentRepository(db_session).list_recent_memories("alice-subjective")
    bob_memories = await AgentRepository(db_session).list_recent_memories("bob-subjective")

    assert len(alice_memories) == 1
    assert len(bob_memories) == 1
    assert alice_memories[0].importance < bob_memories[0].importance
    assert alice_memories[0].memory_category == "medium_term"
    assert bob_memories[0].memory_category == "medium_term"
    assert alice_memories[0].self_relevance < bob_memories[0].self_relevance
    assert "Alice said" in bob_memories[0].content


@pytest.mark.asyncio
async def test_simulation_service_reuses_conversation_id_across_ticks(db_session):
    run, cafe, (alice, bob) = make_run_with_location_agents(
        "run-service-conversation-continuity",
        run_kwargs={"name": "conversation-continuity", "scenario_type": "narrative_world"},
        location_id="loc-cafe-conversation-continuity",
        location_kwargs={"name": "Cafe", "location_type": "cafe"},
        agents=[
            {"agent_id": "alice-continuity", "name": "Alice", "current_goal": "talk"},
            {"agent_id": "bob-continuity", "name": "Bob", "current_goal": "talk"},
        ],
    )

    db_session.add_all([run, cafe, alice, bob])
    await db_session.commit()

    service = SimulationService(db_session)

    await service.run_tick(
        run.id,
        [
            ActionIntent(
                agent_id=alice.id,
                action_type="talk",
                target_agent_id=bob.id,
                payload={"message": "First tick"},
            )
        ],
    )
    await service.run_tick(
        run.id,
        [
            ActionIntent(
                agent_id=bob.id,
                action_type="talk",
                target_agent_id=alice.id,
                payload={"message": "Second tick"},
            )
        ],
    )

    timeline_events, _total = await EventRepository(db_session).list_timeline_events(
        run.id,
        order_desc=False,
    )
    conversation_started = [
        event for event in timeline_events if event.event_type == "conversation_started"
    ]
    speeches = [event for event in timeline_events if event.event_type == "speech"]

    assert len(conversation_started) == 1
    assert len(speeches) == 2
    conversation_id = conversation_started[0].payload["conversation_id"]
    assert speeches[0].payload["conversation_id"] == conversation_id
    assert speeches[1].payload["conversation_id"] == conversation_id
