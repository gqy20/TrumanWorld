from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.scenario.truman_world.rules import (
    build_perception_context_for_agent,
    build_role_context,
    build_scene_guidance,
    filter_world_for_role,
)
from app.sim.world import AgentState, LocationState, WorldState


def test_filter_world_for_role_hides_director_and_cast_fields_for_truman():
    world = {
        "self_status": {"suspicion_score": 0.2},
        "director_scene_goal": "keep_truman_calm",
        "director_reason": "avoid escalation",
        "cast_secret": "hidden",
        "public_weather": "sunny",
    }

    filtered = filter_world_for_role("truman", world)

    assert filtered == {
        "self_status": {"suspicion_score": 0.2},
        "public_weather": "sunny",
    }


def test_build_role_context_and_scene_guidance_follow_world_role():
    truman_context = build_role_context("truman", {"self_status": {"suspicion_score": 0.4}})
    cast_context = build_role_context("cast", {})
    cast_guidance = build_scene_guidance(
        "cast",
        {
            "director_scene_goal": "guide_truman_home",
            "director_priority": "high",
            "director_target_agent_id": "truman",
        },
    )

    assert truman_context["perspective"] == "subjective"
    assert truman_context["current_suspicion_score"] == 0.4
    assert cast_context["perspective"] == "supporting_cast"
    assert cast_guidance["scene_goal"] == "guide_truman_home"
    assert cast_guidance["priority"] == "high"
    assert build_scene_guidance("truman", {"director_scene_goal": "ignored"}) == {}


def test_build_perception_context_for_agent_uses_location_and_relationships():
    world = WorldState(
        current_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        locations={
            "cafe": LocationState(
                id="cafe",
                name="Cafe",
                location_type="cafe",
                occupants={"truman", "meryl"},
            )
        },
        agents={
            "truman": AgentState(
                id="truman",
                name="Truman",
                location_id="cafe",
                occupation="insurance clerk",
            ),
            "meryl": AgentState(
                id="meryl",
                name="Meryl",
                location_id="cafe",
                occupation="hospital staff",
                workplace_id="hospital",
            ),
        },
    )
    relationships = [SimpleNamespace(other_agent_id="meryl", familiarity=0.8)]

    perception = build_perception_context_for_agent("truman", world, relationships, "cafe")

    assert len(perception["perceived_others"]) == 1
    perceived = perception["perceived_others"][0]
    assert perceived["id"] == "meryl"
    assert perceived["occupation"] == "hospital staff"
    assert perceived["familiarity"] == 0.8
