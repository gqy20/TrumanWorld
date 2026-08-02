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

ACTIVE_ACTIVITY_STATUSES = frozenset(
    {"planned", "navigating", "waiting_for_resource", "performing"}
)
TERMINAL_ACTIVITY_STATUSES = frozenset({"completed", "interrupted", "failed", "cancelled"})


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

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_ACTIVITY_STATUSES

    def progress_at(self, world_time: datetime) -> float:
        if self.status == "completed":
            return 1.0
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
    )
