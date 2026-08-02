from __future__ import annotations

from app.director.directives import compile_directives
from app.director.types import DirectorPlan


def test_compile_directives_validates_targets_and_builds_priority_command() -> None:
    plan = DirectorPlan(
        scene_goal="soft_check_in",
        target_agent_ids=["cast-1", "missing"],
        target_agent_id="subject-1",
        priority="high",
        urgency="immediate",
        message_hint="Talk naturally.",
        cooldown_ticks=4,
    )

    directives = compile_directives(
        plan,
        run_id="run-1",
        issued_tick=10,
        valid_agent_ids={"cast-1", "subject-1"},
        valid_location_ids={"square"},
    )

    assert len(directives) == 1
    directive = directives[0]
    assert directive.target_agent_id == "cast-1"
    assert directive.subject_agent_id == "subject-1"
    assert directive.mode == "priority"
    assert directive.expires_at_tick == 14
    assert directive.completion_criteria == {
        "action_type": "talk",
        "target_agent_id": "subject-1",
    }


def test_compile_directives_rejects_invalid_location_and_caps_expiry() -> None:
    plan = DirectorPlan(
        scene_goal="gather",
        target_agent_ids=["cast-1"],
        priority="normal",
        location_hint="unknown",
        cooldown_ticks=100,
    )

    directive = compile_directives(
        plan,
        run_id="run-1",
        issued_tick=2,
        valid_agent_ids={"cast-1"},
        valid_location_ids={"square"},
    )[0]

    assert directive.location_id is None
    assert "location_id" not in directive.constraints
    assert directive.expires_at_tick == 22
    assert directive.completion_criteria == {"accepted_action": True}
