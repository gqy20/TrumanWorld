from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.sim.action_resolver import ActionIntent
from app.sim.activity import ActivityInstance, create_activity
from app.scenario.embodiment_config import load_embodiment_catalog_for_scenario
from app.sim.runner import SimulationRunner
from app.sim.world import AgentState, LocationState, WorldState


def test_activity_round_trip_and_progress_are_world_time_based():
    started_at = datetime(2026, 3, 2, 9, 0, tzinfo=UTC)
    activity = create_activity(
        agent_id="mei",
        activity_type="drink_coffee",
        started_at_world_time=started_at,
        duration_seconds=600,
        target_entity_id="studio-cafe",
    )

    payload = activity.to_dict(world_time=started_at + timedelta(minutes=5))
    restored = ActivityInstance.from_dict(payload)

    assert payload["progress"] == 0.5
    assert restored is not None
    assert restored.expected_end_world_time == started_at + timedelta(minutes=10)


def test_fixed_duration_activity_survives_first_tick_and_completes_on_world_time():
    world = _world()
    runner = SimulationRunner(world)

    started = runner.tick(
        [
            ActionIntent(
                agent_id="mei",
                action_type="start_activity",
                payload={"activity_type": "drink_coffee", "duration_seconds": 480},
            )
        ]
    )

    assert [result.action_type for result in started.accepted] == ["activity_started"]
    assert world.agents["mei"].activity.status == "performing"
    assert world.agents["mei"].activity.progress_at(world.current_time) == 0.0

    still_performing = runner.tick([])
    assert still_performing.accepted == []
    assert world.agents["mei"].activity.progress_at(world.current_time) == 0.625

    completed = runner.tick([])

    assert [result.action_type for result in completed.accepted] == ["activity_completed"]
    assert completed.accepted[0].event_payload["occurred_at_world_time"] == (
        "2026-03-02T09:13:00+00:00"
    )
    assert world.agents["mei"].activity.status == "completed"


def test_active_interval_prevents_sleep_jump_from_consuming_whole_activity() -> None:
    world = _configured_world()
    world.current_time = datetime(2026, 3, 2, 6, 0, tzinfo=UTC)
    world.sleep_end_hour = 7
    runner = SimulationRunner(world)

    result = runner.tick(
        [
            ActionIntent(
                agent_id="mei",
                action_type="start_activity",
                target_location_id="run-cafe",
                payload={"activity_type": "drink_coffee"},
            )
        ]
    )

    assert result.tick_delta == 1
    assert world.current_time == datetime(2026, 3, 2, 6, 5, tzinfo=UTC)
    assert world.agents["mei"].activity is not None
    assert world.agents["mei"].activity.status == "performing"


def test_activity_navigation_and_performance_complete_in_timestamp_order():
    world = _world()
    runner = SimulationRunner(world)

    runner.tick(
        [
            ActionIntent(
                agent_id="mei",
                action_type="start_activity",
                target_location_id="cafe",
                payload={"activity_type": "drink_coffee", "duration_seconds": 60},
            )
        ]
    )
    assert world.agents["mei"].activity.status == "navigating"

    completed = runner.tick([])

    assert world.agents["mei"].location_id == "cafe"
    assert world.agents["mei"].activity.status == "completed"
    assert [result.action_type for result in completed.accepted] == [
        "move_arrived",
        "activity_step_completed",
        "activity_step_started",
        "activity_completed",
    ]
    assert [result.event_payload.get("activity_status") for result in completed.accepted[1:]] == [
        "navigating",
        "performing",
        "completed",
    ]
    assert [result.event_payload.get("step_index") for result in completed.accepted[1:]] == [
        0,
        1,
        1,
    ]
    timestamps = [result.event_payload["occurred_at_world_time"] for result in completed.accepted]
    assert timestamps == sorted(timestamps)


def test_activity_can_be_interrupted_without_advancing_world_time():
    world = _world()
    world.start_agent_activity("mei", "plaza_jog", duration_seconds=900)

    interrupted = world.interrupt_agent_activity("mei", "director_override")

    assert interrupted is not None
    assert interrupted.status == "interrupted"
    assert interrupted.interruption_reason == "director_override"
    assert world.current_time == datetime(2026, 3, 2, 9, 0, tzinfo=UTC)


def test_interrupt_activity_intent_emits_authoritative_transition():
    world = _world()
    world.start_agent_activity("mei", "plaza_jog", duration_seconds=900)

    result = SimulationRunner(world).resolver.resolve(
        world,
        ActionIntent(
            agent_id="mei",
            action_type="interrupt_activity",
            payload={"reason": "director_override"},
        ),
    )

    assert result.accepted is True
    assert result.action_type == "activity_interrupted"
    assert result.event_payload["interruption_reason"] == "director_override"


def test_configured_coffee_activity_claims_resources_and_queues_deterministically():
    world = _configured_world()
    runner = SimulationRunner(world)

    started = runner.tick(
        [
            ActionIntent(
                agent_id="mei",
                action_type="start_activity",
                target_location_id="run-cafe",
                payload={"activity_type": "drink_coffee"},
            ),
            ActionIntent(
                agent_id="noah",
                action_type="start_activity",
                target_location_id="run-cafe",
                payload={"activity_type": "drink_coffee"},
            ),
        ]
    )

    assert [result.action_type for result in started.accepted[:2]] == [
        "activity_started",
        "activity_started",
    ]
    assert world.agents["mei"].activity.current_step_id == "order"
    assert world.agents["mei"].activity.claimed_resource_ids == (
        "slot:cafe:coffee-counter:service",
    )
    assert world.agents["noah"].activity.status == "waiting_for_resource"
    assert world.agents["noah"].activity.queue_position == 1

    runner.tick([])

    assert world.agents["mei"].activity.current_step_id == "drink"
    assert world.agents["mei"].activity.claimed_resource_ids == ("slot:cafe:window-chair-1:sit",)
    assert world.agents["noah"].activity.current_step_id == "take_seat"
    assert world.agents["noah"].activity.status == "waiting_for_resource"
    assert world.agents["noah"].activity.queue_position == 1


def test_interrupting_configured_activity_releases_resource_for_first_waiter():
    world = _configured_world()
    world.start_agent_activity("mei", "drink_coffee", target_location_id="run-cafe")
    world.start_agent_activity("noah", "drink_coffee", target_location_id="run-cafe")

    interrupted = world.interrupt_agent_activity("mei", "director_override")

    assert interrupted is not None
    assert interrupted.claimed_resource_ids == ()
    assert world.agents["noah"].activity.status == "performing"
    assert world.agents["noah"].activity.claimed_resource_ids == (
        "slot:cafe:coffee-counter:service",
    )


def _world() -> WorldState:
    return WorldState(
        current_time=datetime(2026, 3, 2, 9, 0, tzinfo=UTC),
        tick_minutes=5,
        locations={
            "quad": LocationState(id="quad", name="Quad", x=0, y=0, occupants={"mei"}),
            "cafe": LocationState(id="cafe", name="Cafe", x=4, y=2),
        },
        agents={"mei": AgentState(id="mei", name="Mei", location_id="quad")},
    )


def _configured_world() -> WorldState:
    catalog = load_embodiment_catalog_for_scenario("campus_world")
    assert catalog is not None
    return WorldState(
        current_time=datetime(2026, 3, 2, 9, 0, tzinfo=UTC),
        tick_minutes=5,
        world_seed=42,
        embodiment_catalog=catalog,
        locations={
            "run-cafe": LocationState(
                id="run-cafe",
                name="Studio Cafe",
                location_type="cafe",
                occupants={"mei", "noah"},
            )
        },
        agents={
            "mei": AgentState(id="mei", name="Mei", location_id="run-cafe"),
            "noah": AgentState(id="noah", name="Noah", location_id="run-cafe"),
        },
    )
