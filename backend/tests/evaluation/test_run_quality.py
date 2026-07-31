from __future__ import annotations

import pytest

from app.evaluation.run_quality import build_run_quality_report


def test_build_run_quality_report_calculates_deterministic_metrics() -> None:
    report = build_run_quality_report(
        run={
            "id": "run-1",
            "name": "Morning run",
            "scenario_type": "bundle_world",
            "current_tick": 3,
            "tick_minutes": 5,
        },
        timeline_events=[
            {
                "id": "event-1",
                "tick_no": 1,
                "event_type": "move",
                "payload": {"actor_name": "Alice"},
            },
            {
                "id": "event-2",
                "tick_no": 2,
                "event_type": "move",
                "payload": {"actor_name": "Alice"},
            },
            {
                "id": "event-3",
                "tick_no": 2,
                "event_type": "talk",
                "payload": {"actor_name": "Bob"},
            },
            {
                "id": "event-4",
                "tick_no": 3,
                "event_type": "move_rejected",
                "payload": {"actor_name": "Alice"},
            },
            {
                "id": "event-5",
                "tick_no": 3,
                "event_type": "director_broadcast",
                "payload": {},
            },
            {
                "id": "event-6",
                "tick_no": 3,
                "event_type": "speech",
                "payload": {"actor_name": "Bob"},
            },
        ],
        director_observation={
            "subject_alert_tracking_enabled": True,
            "subject_alert_score": 0.3,
        },
        tick_samples=[
            {
                "tick_no": 1,
                "subject_alert_score": 0.2,
                "duration_seconds": 1.0,
                "accepted_count": 1,
                "rejected_count": 0,
            },
            {
                "tick_no": 2,
                "subject_alert_score": 0.35,
                "duration_seconds": 2.0,
                "accepted_count": 2,
                "rejected_count": 0,
            },
            {
                "tick_no": 3,
                "subject_alert_score": 0.3,
                "duration_seconds": 1.5,
                "accepted_count": 0,
                "rejected_count": 1,
            },
        ],
        memory_snapshots=[
            {
                "tick_no": 1,
                "observed_counts": {"alice": 2, "bob": 1},
                "capped_agent_ids": [],
            },
            {
                "tick_no": 3,
                "observed_counts": {"alice": 4, "bob": 2},
                "capped_agent_ids": ["alice"],
            },
        ],
    )

    assert report["schema_version"] == 1
    assert report["run"] == {
        "id": "run-1",
        "name": "Morning run",
        "scenario_type": "bundle_world",
        "current_tick": 3,
        "tick_minutes": 5,
    }
    assert report["window"] == {
        "tick_from": 1,
        "tick_to": 3,
        "distinct_ticks": 3,
        "event_count": 6,
    }
    assert report["actions"]["accepted_count"] == 3
    assert report["actions"]["rejected_count"] == 1
    assert report["actions"]["attempt_count"] == 4
    assert report["actions"]["rejection_rate"] == 0.25
    assert report["actions"]["unique_action_types"] == 2
    assert report["actions"]["action_type_entropy"] == pytest.approx(0.811278, abs=1e-6)
    assert report["actions"]["consecutive_repeat_count"] == 2
    assert report["actions"]["consecutive_repeat_rate"] == 1.0
    assert report["actions"]["action_type_counts"] == {"move": 3, "talk": 1}
    assert report["actions"]["event_type_counts"] == {
        "director_broadcast": 1,
        "move": 2,
        "move_rejected": 1,
        "speech": 1,
        "talk": 1,
    }
    assert report["director"] == {
        "event_count": 1,
        "events_per_tick": pytest.approx(1 / 3),
    }
    assert report["subject_alert"] == {
        "tracking_enabled": True,
        "current_score": 0.3,
        "sample_count": 3,
        "start_score": 0.2,
        "end_score": 0.3,
        "max_step_change": 0.15,
        "mean_abs_step_change": 0.1,
    }
    assert report["memory"] == {
        "snapshot_count": 2,
        "start_observed_count": 3,
        "end_observed_count": 6,
        "observed_delta": 3,
        "capped": True,
        "capped_agent_ids": ["alice"],
    }
    assert report["performance"] == {
        "sample_count": 3,
        "mean_tick_seconds": 1.5,
        "p95_tick_seconds": 2.0,
    }


def test_build_run_quality_report_handles_empty_inputs() -> None:
    report = build_run_quality_report(
        run={"id": "run-empty", "current_tick": 0},
        timeline_events=[],
        director_observation={
            "subject_alert_tracking_enabled": False,
            "subject_alert_score": None,
        },
    )

    assert report["window"] == {
        "tick_from": None,
        "tick_to": None,
        "distinct_ticks": 0,
        "event_count": 0,
    }
    assert report["actions"]["rejection_rate"] == 0.0
    assert report["actions"]["action_type_entropy"] == 0.0
    assert report["actions"]["consecutive_repeat_rate"] == 0.0
    assert report["director"]["events_per_tick"] == 0.0
    assert report["subject_alert"] == {
        "tracking_enabled": False,
        "current_score": None,
        "sample_count": 0,
        "start_score": None,
        "end_score": None,
        "max_step_change": None,
        "mean_abs_step_change": None,
    }
    assert report["memory"] == {
        "snapshot_count": 0,
        "start_observed_count": None,
        "end_observed_count": None,
        "observed_delta": None,
        "capped": False,
        "capped_agent_ids": [],
    }
    assert report["performance"] == {
        "sample_count": 0,
        "mean_tick_seconds": None,
        "p95_tick_seconds": None,
    }


def test_report_uses_current_observation_when_no_tick_samples_exist() -> None:
    report = build_run_quality_report(
        run={"id": "run-existing", "current_tick": 8},
        timeline_events=[],
        director_observation={
            "subject_alert_tracking_enabled": True,
            "subject_alert_score": 0.42,
        },
    )

    assert report["subject_alert"] == {
        "tracking_enabled": True,
        "current_score": 0.42,
        "sample_count": 1,
        "start_score": 0.42,
        "end_score": 0.42,
        "max_step_change": 0.0,
        "mean_abs_step_change": 0.0,
    }


def test_director_rate_uses_run_ticks_including_ticks_without_events() -> None:
    report = build_run_quality_report(
        run={"id": "run-sparse", "current_tick": 5},
        timeline_events=[
            {"tick_no": 1, "event_type": "move", "payload": {"actor_name": "Alice"}},
            {"tick_no": 3, "event_type": "director_broadcast", "payload": {}},
        ],
    )

    assert report["window"]["distinct_ticks"] == 2
    assert report["director"]["events_per_tick"] == 0.2
