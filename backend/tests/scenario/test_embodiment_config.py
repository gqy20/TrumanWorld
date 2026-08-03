from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.scenario.embodiment_config import (
    load_embodiment_catalog_for_scenario,
    load_social_spatial_config_for_scenario,
)
from app.scenario.factory import create_scenario
from app.sim.runtime_context_utils import build_agent_world_context
from app.sim.world import AgentState, LocationState, WorldState


def test_campus_embodiment_catalog_links_activity_resources_to_map():
    catalog = load_embodiment_catalog_for_scenario("campus_world")

    assert catalog is not None
    activity = catalog.get_activity("drink_coffee")
    assert activity is not None
    assert [step.id for step in activity.steps] == ["order", "take_seat", "drink"]
    assert {resource.id for resource in catalog.resources} == {
        "slot:cafe:coffee-counter:queue-1",
        "slot:cafe:coffee-counter:queue-2",
        "slot:cafe:coffee-counter:queue-3",
        "slot:cafe:coffee-counter:service",
        "slot:cafe:window-chair-1:sit",
    }
    service_resources = catalog.resources_for(
        location_id="run-id-cafe",
        object_types=("coffee_counter",),
        slot_kind="service",
    )
    assert [resource.id for resource in service_resources] == ["slot:cafe:coffee-counter:service"]


def test_campus_social_spatial_config_is_strictly_loaded():
    config = load_social_spatial_config_for_scenario("campus_world")

    assert config is not None
    assert config.perception.vision_range_meters == 8
    assert config.encounter.candidate_distance_meters == 2.5
    assert config.encounter.cooldown_minutes == 30


def test_embodiment_catalog_requires_both_configuration_files(tmp_path: Path):
    scenario_root = tmp_path / "scenarios" / "partial"
    scenario_root.mkdir(parents=True)
    (scenario_root / "scenario.yml").write_text(
        "id: partial\nname: Partial\nversion: 1\nadapter: bundle_world\n",
        encoding="utf-8",
    )
    (scenario_root / "activities.yml").write_text(
        "schema_version: 1\nactivities: {}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be provided together"):
        load_embodiment_catalog_for_scenario("partial", project_root=tmp_path)


def test_duration_resolution_is_stable_and_bounded():
    catalog = load_embodiment_catalog_for_scenario("campus_world")

    assert catalog is not None
    first = catalog.resolve_duration(
        (45, 75),
        world_seed=42,
        agent_id="mei",
        activity_type="drink_coffee",
        step_id="order",
        started_at_iso="2026-03-02T09:00:00+00:00",
    )
    second = catalog.resolve_duration(
        (45, 75),
        world_seed=42,
        agent_id="mei",
        activity_type="drink_coffee",
        step_id="order",
        started_at_iso="2026-03-02T09:00:00+00:00",
    )

    assert first == second
    assert 45 <= first <= 75


def test_campus_actor_policy_and_context_expose_configured_activities():
    catalog = load_embodiment_catalog_for_scenario("campus_world")
    assert catalog is not None
    scenario = create_scenario("campus_world")
    world = WorldState(
        current_time=datetime(2026, 3, 2, 9, 0, tzinfo=UTC),
        embodiment_catalog=catalog,
        locations={
            "run-quad": LocationState(
                id="run-quad", name="Quad", location_type="quad", occupants={"mei"}
            ),
            "run-cafe": LocationState(id="run-cafe", name="Cafe", location_type="cafe"),
        },
        agents={"mei": AgentState(id="mei", name="Mei", location_id="run-quad")},
    )

    context = build_agent_world_context(
        agent_id="mei",
        world=world,
        current_goal=None,
        current_location_id="run-quad",
        home_location_id="run-quad",
        nearby_agent_id=None,
    )

    assert "start_activity" in scenario.allowed_actions()
    assert context["available_activities"] == [
        {
            "activity_type": "drink_coffee",
            "target_location_ids": ["run-cafe"],
            "steps": ["order_coffee", "sit", "drink"],
        }
    ]
