from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any

from app.protocol.simulation import DIRECTOR_EVENT_PREFIX

ACTION_TYPES = frozenset(
    {
        "move",
        "talk",
        "listen",
        "conversation_started",
        "conversation_joined",
        "work",
        "rest",
        "plan",
        "reflect",
    }
)
REJECTED_SUFFIX = "_rejected"


def _rounded(value: float) -> float:
    return round(value, 6)


def _action_type(event_type: str) -> tuple[str, bool] | None:
    rejected = event_type.endswith(REJECTED_SUFFIX)
    base_type = event_type[: -len(REJECTED_SUFFIX)] if rejected else event_type
    if base_type not in ACTION_TYPES:
        return None
    return base_type, rejected


def _normalized_entropy(counts: Counter[str]) -> float:
    if len(counts) <= 1:
        return 0.0
    total = sum(counts.values())
    entropy = -sum((count / total) * math.log2(count / total) for count in counts.values())
    return _rounded(entropy / math.log2(len(counts)))


def _actor_key(event: Mapping[str, Any]) -> str | None:
    payload = event.get("payload")
    if isinstance(payload, Mapping):
        for key in ("actor_agent_id", "actor_name"):
            value = payload.get(key)
            if value:
                return str(value)
    for key in ("actor_agent_id", "actor_name"):
        value = event.get(key)
        if value:
            return str(value)
    return None


def _action_metrics(timeline_events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    event_type_counts: Counter[str] = Counter()
    action_type_counts: Counter[str] = Counter()
    attempts: list[tuple[int, int, str | None, str, bool]] = []

    for index, event in enumerate(timeline_events):
        event_type = str(event.get("event_type") or "")
        if event_type:
            event_type_counts[event_type] += 1
        resolved_action = _action_type(event_type)
        if resolved_action is None:
            continue
        base_type, rejected = resolved_action
        action_type_counts[base_type] += 1
        attempts.append(
            (
                int(event.get("tick_no") or 0),
                index,
                _actor_key(event),
                base_type,
                rejected,
            )
        )

    attempts.sort(key=lambda item: (item[0], item[1]))
    previous_by_actor: dict[str, str] = {}
    repeat_count = 0
    repeat_opportunities = 0
    for _, _, actor, action_type, _ in attempts:
        if actor is None:
            continue
        if actor in previous_by_actor:
            repeat_opportunities += 1
            if previous_by_actor[actor] == action_type:
                repeat_count += 1
        previous_by_actor[actor] = action_type

    rejected_count = sum(1 for *_, rejected in attempts if rejected)
    attempt_count = len(attempts)
    return {
        "accepted_count": attempt_count - rejected_count,
        "rejected_count": rejected_count,
        "attempt_count": attempt_count,
        "rejection_rate": _rounded(rejected_count / attempt_count) if attempt_count else 0.0,
        "unique_action_types": len(action_type_counts),
        "action_type_entropy": _normalized_entropy(action_type_counts),
        "consecutive_repeat_count": repeat_count,
        "consecutive_repeat_rate": (
            _rounded(repeat_count / repeat_opportunities) if repeat_opportunities else 0.0
        ),
        "action_type_counts": dict(sorted(action_type_counts.items())),
        "event_type_counts": dict(sorted(event_type_counts.items())),
    }


def _subject_alert_metrics(
    director_observation: Mapping[str, Any] | None,
    tick_samples: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    observation = director_observation or {}
    tracking_enabled = bool(observation.get("subject_alert_tracking_enabled", True))
    current_score = observation.get("subject_alert_score") if tracking_enabled else None
    scores = [
        float(sample["subject_alert_score"])
        for sample in tick_samples
        if tracking_enabled and sample.get("subject_alert_score") is not None
    ]
    if not scores and current_score is not None:
        scores = [float(current_score)]

    if not scores:
        return {
            "tracking_enabled": tracking_enabled,
            "current_score": None,
            "sample_count": 0,
            "start_score": None,
            "end_score": None,
            "max_step_change": None,
            "mean_abs_step_change": None,
        }

    changes = [abs(current - previous) for previous, current in pairwise(scores)]
    return {
        "tracking_enabled": tracking_enabled,
        "current_score": _rounded(float(current_score))
        if current_score is not None
        else _rounded(scores[-1]),
        "sample_count": len(scores),
        "start_score": _rounded(scores[0]),
        "end_score": _rounded(scores[-1]),
        "max_step_change": _rounded(max(changes)) if changes else 0.0,
        "mean_abs_step_change": _rounded(sum(changes) / len(changes)) if changes else 0.0,
    }


def _memory_metrics(memory_snapshots: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not memory_snapshots:
        return {
            "snapshot_count": 0,
            "start_observed_count": None,
            "end_observed_count": None,
            "observed_delta": None,
            "capped": False,
            "capped_agent_ids": [],
        }

    snapshots = sorted(memory_snapshots, key=lambda item: int(item.get("tick_no") or 0))

    def total(snapshot: Mapping[str, Any]) -> int:
        counts = snapshot.get("observed_counts") or {}
        if not isinstance(counts, Mapping):
            return 0
        return sum(int(value) for value in counts.values())

    start_count = total(snapshots[0])
    end_count = total(snapshots[-1])
    capped_agent_ids = sorted(
        {
            str(agent_id)
            for snapshot in snapshots
            for agent_id in (snapshot.get("capped_agent_ids") or [])
        }
    )
    return {
        "snapshot_count": len(snapshots),
        "start_observed_count": start_count,
        "end_observed_count": end_count,
        "observed_delta": end_count - start_count,
        "capped": bool(capped_agent_ids),
        "capped_agent_ids": capped_agent_ids,
    }


def _performance_metrics(tick_samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    durations = sorted(
        float(sample["duration_seconds"])
        for sample in tick_samples
        if sample.get("duration_seconds") is not None
    )
    if not durations:
        return {
            "sample_count": 0,
            "mean_tick_seconds": None,
            "p95_tick_seconds": None,
        }
    p95_index = max(0, math.ceil(0.95 * len(durations)) - 1)
    return {
        "sample_count": len(durations),
        "mean_tick_seconds": _rounded(sum(durations) / len(durations)),
        "p95_tick_seconds": _rounded(durations[p95_index]),
    }


def build_run_quality_report(
    *,
    run: Mapping[str, Any],
    timeline_events: Sequence[Mapping[str, Any]],
    director_observation: Mapping[str, Any] | None = None,
    tick_samples: Sequence[Mapping[str, Any]] = (),
    memory_snapshots: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build a deterministic, JSON-serializable quality report from API snapshots."""
    ticks = sorted({int(event.get("tick_no") or 0) for event in timeline_events})
    action_metrics = _action_metrics(timeline_events)
    director_event_count = sum(
        1
        for event in timeline_events
        if str(event.get("event_type") or "").startswith(DIRECTOR_EVENT_PREFIX)
        and not str(event.get("event_type") or "").endswith(REJECTED_SUFFIX)
    )
    evaluated_tick_count = int(run.get("current_tick") or 0) or len(ticks)
    run_fields = ("id", "name", "scenario_type", "current_tick", "tick_minutes")

    return {
        "schema_version": 1,
        "run": {key: run.get(key) for key in run_fields if key in run},
        "window": {
            "tick_from": ticks[0] if ticks else None,
            "tick_to": ticks[-1] if ticks else None,
            "distinct_ticks": len(ticks),
            "event_count": len(timeline_events),
        },
        "actions": action_metrics,
        "director": {
            "event_count": director_event_count,
            "events_per_tick": (
                _rounded(director_event_count / evaluated_tick_count)
                if evaluated_tick_count
                else 0.0
            ),
        },
        "subject_alert": _subject_alert_metrics(director_observation, tick_samples),
        "memory": _memory_metrics(memory_snapshots),
        "performance": _performance_metrics(tick_samples),
    }
