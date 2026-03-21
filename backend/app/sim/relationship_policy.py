from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


SOCIAL_RELATION_EVENT_TYPES = {"talk", "speech"}
STRONG_RELATION_TYPES = {"family", "close_friend"}
FRIEND_RELATION_TYPES = {"friend"}
ACQUAINTANCE_RELATION_TYPES = {"acquaintance", "colleague"}


@dataclass(frozen=True)
class RelationshipDelta:
    familiarity_delta: float
    trust_delta: float
    affinity_delta: float
    modifiers: tuple[str, ...] = ()


def derive_relationship_level(
    *,
    familiarity: float,
    trust: float = 0.0,
    affinity: float = 0.0,
    relation_type: str | None = None,
) -> str:
    normalized_type = (relation_type or "").strip().lower()
    if normalized_type in STRONG_RELATION_TYPES:
        return normalized_type
    if normalized_type in FRIEND_RELATION_TYPES:
        return "friend"

    # Weight familiarity highest because it is the most stable signal the runtime has today.
    strength = (max(0.0, familiarity) * 0.5) + (max(0.0, trust) * 0.25) + (max(0.0, affinity) * 0.25)

    if strength >= 0.85 and familiarity >= 0.75 and trust >= 0.6 and affinity >= 0.6:
        return "close_friend"
    if strength >= 0.55:
        return "friend"
    if strength >= 0.18 or normalized_type in ACQUAINTANCE_RELATION_TYPES:
        return "acquaintance"
    return "stranger"


def compute_relationship_delta(
    *,
    event_type: str,
    world_time: datetime | None,
    location_id: str | None,
    location_type: str | None,
    rule_decision: str | None = None,
    rule_reason: str | None = None,
    risk_level: str | None = None,
    policy_values: dict[str, Any] | None = None,
) -> RelationshipDelta | None:
    if event_type not in SOCIAL_RELATION_EVENT_TYPES:
        return None

    familiarity_delta = 0.1
    trust_delta = 0.05
    affinity_delta = 0.05
    modifiers: list[str] = []

    values = policy_values or {}
    social_boost_locations = values.get("social_boost_locations")
    if isinstance(social_boost_locations, dict) and location_type:
        boost = social_boost_locations.get(location_type)
        if isinstance(boost, (int, float)) and boost > 0:
            affinity_delta += min(0.05, float(boost) * 0.1)
            modifiers.append(f"social_boost:{location_type}")

    sensitive_locations = values.get("sensitive_locations")
    if isinstance(sensitive_locations, list) and location_id and location_id in sensitive_locations:
        trust_delta -= 0.02
        affinity_delta -= 0.03
        modifiers.append("sensitive_location")

    talk_risk_after_hour = values.get("talk_risk_after_hour")
    if (
        isinstance(talk_risk_after_hour, (int, float))
        and world_time is not None
        and world_time.hour >= int(talk_risk_after_hour)
    ):
        trust_delta -= 0.02
        affinity_delta -= 0.03
        modifiers.append("late_hour")

    if rule_decision == "soft_risk":
        trust_delta -= 0.02
        affinity_delta -= 0.03
        modifiers.append("soft_risk")
        if risk_level == "medium":
            trust_delta -= 0.02
            affinity_delta -= 0.02
            modifiers.append("risk_level:medium")
        elif risk_level == "high":
            trust_delta -= 0.04
            affinity_delta -= 0.04
            modifiers.append("risk_level:high")
        if rule_reason in {"late_night_talk_risk", "subject_proximity_risk"}:
            affinity_delta -= 0.01
            modifiers.append(f"risk_reason:{rule_reason}")

    return RelationshipDelta(
        familiarity_delta=familiarity_delta,
        trust_delta=trust_delta,
        affinity_delta=affinity_delta,
        modifiers=tuple(modifiers),
    )
