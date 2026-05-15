from datetime import UTC, datetime
from types import SimpleNamespace

from app.api.presenters.world import build_world_clock, enrich_event_payload


def test_enrich_event_payload_fills_missing_readable_names():
    event = SimpleNamespace(
        actor_agent_id="agent-a",
        target_agent_id="agent-b",
        location_id="loc-home",
        payload={
            "to_location_id": "loc-cafe",
            "from_location_id": "loc-home",
        },
    )

    payload = enrich_event_payload(
        event,
        {"agent-a": "Alice", "agent-b": "Bob"},
        {"loc-home": "Home", "loc-cafe": "Cafe"},
    )

    assert payload["actor_name"] == "Alice"
    assert payload["target_name"] == "Bob"
    assert payload["location_name"] == "Home"
    assert payload["to_location_name"] == "Cafe"
    assert payload["from_location_name"] == "Home"


def test_enrich_event_payload_preserves_existing_names():
    event = SimpleNamespace(
        actor_agent_id="agent-a",
        target_agent_id=None,
        location_id="loc-home",
        payload={"actor_name": "Existing Alice", "location_name": "Existing Home"},
    )

    payload = enrich_event_payload(event, {"agent-a": "Alice"}, {"loc-home": "Home"})

    assert payload["actor_name"] == "Existing Alice"
    assert payload["location_name"] == "Existing Home"


def test_build_world_clock_maps_time_period_and_weekday():
    clock = build_world_clock(datetime(2026, 3, 2, 6, 30, tzinfo=UTC))

    assert clock.date == "2026-03-02"
    assert clock.time == "06:30"
    assert clock.weekday_name == "Monday"
    assert clock.weekday_name_cn == "星期一"
    assert clock.time_period == "dawn"
    assert clock.time_period_cn == "黎明"
