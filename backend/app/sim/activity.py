from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

ActivityStatus = Literal[
    "planned",
    "navigating",
    "waiting_for_resource",
    "performing",
    "completed",
    "interrupted",
    "failed",
    "cancelled",
]
ActivityStepStatus = Literal["pending", "waiting_for_resource", "performing", "completed"]

ACTIVE_ACTIVITY_STATUSES = frozenset(
    {"planned", "navigating", "waiting_for_resource", "performing"}
)
TERMINAL_ACTIVITY_STATUSES = frozenset({"completed", "interrupted", "failed", "cancelled"})


@dataclass(slots=True)
class ActivityStepInstance:
    id: str
    action: str
    status: ActivityStepStatus
    duration_seconds: float
    visual_state: str | None = None
    resource_required: bool = False
    candidate_resource_ids: tuple[str, ...] = ()
    claimed_resource_id: str | None = None
    release_after: bool = True
    started_at_world_time: datetime | None = None
    expected_end_world_time: datetime | None = None

    def progress_at(self, world_time: datetime) -> float:
        if self.status == "completed":
            return 1.0
        if (
            self.status != "performing"
            or self.started_at_world_time is None
            or self.expected_end_world_time is None
        ):
            return 0.0
        total = max(
            0.001,
            (self.expected_end_world_time - self.started_at_world_time).total_seconds(),
        )
        elapsed = max(0.0, (world_time - self.started_at_world_time).total_seconds())
        return round(min(1.0, elapsed / total), 4)

    def to_dict(self, *, world_time: datetime | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "visual_state": self.visual_state,
            "resource_required": self.resource_required,
            "candidate_resource_ids": list(self.candidate_resource_ids),
            "claimed_resource_id": self.claimed_resource_id,
            "release_after": self.release_after,
            "started_at_world_time": _format_datetime(self.started_at_world_time),
            "expected_end_world_time": _format_datetime(self.expected_end_world_time),
            "progress": self.progress_at(world_time) if world_time is not None else None,
        }

    @classmethod
    def from_dict(cls, value: object) -> ActivityStepInstance | None:
        if not isinstance(value, dict):
            return None
        status = value.get("status")
        if status not in {"pending", "waiting_for_resource", "performing", "completed"}:
            return None
        candidates = value.get("candidate_resource_ids", [])
        if not isinstance(candidates, list) or not all(
            isinstance(item, str) for item in candidates
        ):
            return None
        try:
            return cls(
                id=str(value["id"]),
                action=str(value["action"]),
                status=status,
                duration_seconds=max(0.0, float(value.get("duration_seconds", 0.0))),
                visual_state=_optional_str(value.get("visual_state")),
                resource_required=bool(value.get("resource_required", False)),
                candidate_resource_ids=tuple(candidates),
                claimed_resource_id=_optional_str(value.get("claimed_resource_id")),
                release_after=bool(value.get("release_after", True)),
                started_at_world_time=_parse_datetime(value.get("started_at_world_time")),
                expected_end_world_time=_parse_datetime(value.get("expected_end_world_time")),
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(slots=True)
class ActivityInstance:
    id: str
    agent_id: str
    activity_type: str
    status: ActivityStatus
    step_index: int
    started_at_world_time: datetime
    expected_end_world_time: datetime | None
    duration_seconds: float
    target_entity_id: str | None = None
    claimed_resource_ids: tuple[str, ...] = ()
    parent_intent_id: str | None = None
    interruption_reason: str | None = None
    interruptible: bool = True
    steps: tuple[ActivityStepInstance, ...] = ()
    zone_id: str | None = None
    queue_position: int | None = None

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_ACTIVITY_STATUSES

    def progress_at(self, world_time: datetime) -> float:
        if self.status == "completed":
            return 1.0
        if self.steps:
            completed = sum(1 for step in self.steps if step.status == "completed")
            current_progress = (
                self.current_step.progress_at(world_time) if self.current_step else 0.0
            )
            return round(min(1.0, (completed + current_progress) / len(self.steps)), 4)
        if self.status != "performing" or self.expected_end_world_time is None:
            return 0.0
        performing_started_at = self.expected_end_world_time - timedelta(
            seconds=self.duration_seconds
        )
        elapsed = max(0.0, (world_time - performing_started_at).total_seconds())
        return round(min(1.0, elapsed / max(self.duration_seconds, 0.001)), 4)

    def start_performing(self, world_time: datetime) -> None:
        self.status = "performing"
        self.step_index += 1
        self.expected_end_world_time = world_time + timedelta(seconds=self.duration_seconds)

    def complete(self) -> None:
        self.status = "completed"

    def interrupt(self, reason: str) -> None:
        self.status = "interrupted"
        self.interruption_reason = reason

    @property
    def current_step(self) -> ActivityStepInstance | None:
        if not self.steps or self.step_index >= len(self.steps):
            return None
        return self.steps[self.step_index]

    @property
    def current_step_id(self) -> str | None:
        return self.current_step.id if self.current_step is not None else None

    @property
    def current_action(self) -> str | None:
        return self.current_step.action if self.current_step is not None else None

    @property
    def visual_state(self) -> str | None:
        return self.current_step.visual_state if self.current_step is not None else None

    def to_dict(self, *, world_time: datetime | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "activity_type": self.activity_type,
            "status": self.status,
            "step_index": self.step_index,
            "started_at_world_time": self.started_at_world_time.isoformat(),
            "expected_end_world_time": (
                self.expected_end_world_time.isoformat()
                if self.expected_end_world_time is not None
                else None
            ),
            "duration_seconds": self.duration_seconds,
            "target_entity_id": self.target_entity_id,
            "claimed_resource_ids": list(self.claimed_resource_ids),
            "parent_intent_id": self.parent_intent_id,
            "interruption_reason": self.interruption_reason,
            "interruptible": self.interruptible,
            "steps": [step.to_dict(world_time=world_time) for step in self.steps],
            "current_step_id": self.current_step_id,
            "current_action": self.current_action,
            "visual_state": self.visual_state,
            "zone_id": self.zone_id,
            "queue_position": self.queue_position,
            "progress": self.progress_at(world_time) if world_time is not None else None,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> ActivityInstance | None:
        if not isinstance(value, dict):
            return None
        try:
            status = value["status"]
            if status not in ACTIVE_ACTIVITY_STATUSES | TERMINAL_ACTIVITY_STATUSES:
                return None
            started_at = datetime.fromisoformat(value["started_at_world_time"])
            raw_expected_end = value.get("expected_end_world_time")
            expected_end = (
                datetime.fromisoformat(raw_expected_end)
                if isinstance(raw_expected_end, str)
                else None
            )
            claimed = value.get("claimed_resource_ids", [])
            if not isinstance(claimed, list) or not all(isinstance(item, str) for item in claimed):
                return None
            raw_steps = value.get("steps", [])
            if not isinstance(raw_steps, list):
                return None
            steps = tuple(
                step for item in raw_steps if (step := ActivityStepInstance.from_dict(item))
            )
            if len(steps) != len(raw_steps):
                return None
            return cls(
                id=str(value["id"]),
                agent_id=str(value["agent_id"]),
                activity_type=str(value["activity_type"]),
                status=status,
                step_index=int(value.get("step_index", 0)),
                started_at_world_time=started_at,
                expected_end_world_time=expected_end,
                duration_seconds=max(0.0, float(value.get("duration_seconds", 0.0))),
                target_entity_id=value.get("target_entity_id"),
                claimed_resource_ids=tuple(claimed),
                parent_intent_id=value.get("parent_intent_id"),
                interruption_reason=value.get("interruption_reason"),
                interruptible=bool(value.get("interruptible", True)),
                steps=steps,
                zone_id=_optional_str(value.get("zone_id")),
                queue_position=(
                    int(value["queue_position"])
                    if isinstance(value.get("queue_position"), int)
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError):
            return None


def create_activity(
    *,
    agent_id: str,
    activity_type: str,
    started_at_world_time: datetime,
    duration_seconds: float,
    target_entity_id: str | None = None,
    requires_navigation: bool = False,
    parent_intent_id: str | None = None,
    steps: tuple[ActivityStepInstance, ...] = (),
    interruptible: bool = True,
) -> ActivityInstance:
    safe_duration = max(0.0, float(duration_seconds))
    status: ActivityStatus = "navigating" if requires_navigation else "performing"
    return ActivityInstance(
        id=f"activity-{agent_id}-{uuid4().hex[:12]}",
        agent_id=agent_id,
        activity_type=activity_type,
        status=status,
        step_index=0,
        started_at_world_time=started_at_world_time,
        expected_end_world_time=(
            None
            if requires_navigation
            else started_at_world_time + timedelta(seconds=safe_duration)
        ),
        duration_seconds=safe_duration,
        target_entity_id=target_entity_id,
        parent_intent_id=parent_intent_id,
        interruptible=interruptible,
        steps=steps,
    )


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
