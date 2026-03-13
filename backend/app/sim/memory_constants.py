"""Memory salience, subjective importance, and category rules."""

from __future__ import annotations


class MemoryCategory(str):
    """Memory category for time-based classification."""

    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"

    @classmethod
    def all_categories(cls) -> list[str]:
        return [cls.SHORT_TERM, cls.MEDIUM_TERM, cls.LONG_TERM]


EVENT_IMPORTANCE_DEFAULTS: dict[str, float] = {
    "director_broadcast": 0.85,
    "power_outage": 0.80,
    "talk": 0.55,
    "speech": 0.55,
    "listen": 0.68,
    "talk_rejected": 0.32,
    "listen_rejected": 0.18,
    "work_rejected": 0.22,
    "move_rejected": 0.18,
    "work": 0.20,
    "move": 0.08,
    "rest": 0.03,
}

EMOTIONAL_WORDS = {"喜欢", "爱", "讨厌", "恨", "担心", "开心", "难过", "想念", "抱歉", "谢谢"}

PERSPECTIVE_BONUS = {
    "actor": 0.12,
    "target": 0.30,
    "listener": 0.20,
    "observer": 0.04,
}


def _clamp(score: float) -> float:
    return round(min(1.0, max(0.0, score)), 2)


def _compress_high_importance(score: float) -> float:
    """Avoid saturating most strong social memories at 1.0."""
    if score <= 0.75:
        return score
    if score <= 0.95:
        return 0.75 + (score - 0.75) * 0.5
    return 0.85 + (score - 0.95) * 0.2


def calculate_event_importance(
    event_type: str,
    payload: dict | None = None,
    *,
    is_first_interaction: bool = False,
) -> float:
    """Calculate objective event salience before subjective memory encoding."""
    payload = payload or {}
    importance = EVENT_IMPORTANCE_DEFAULTS.get(event_type, 0.3)

    message = str(payload.get("message") or "")
    if event_type in {"talk", "speech"}:
        if any(word in message for word in EMOTIONAL_WORDS):
            importance += 0.12
        if len(message) > 100:
            importance += 0.08

    if is_first_interaction:
        importance += 0.10

    return _clamp(importance)


def calculate_memory_importance(
    *,
    event_importance: float,
    perspective: str,
    relationship_strength: float = 0.0,
    goal_relevance: bool = False,
    location_relevance: bool = False,
) -> float:
    """Calculate subjective importance for one agent's memory of an event."""
    score = event_importance
    score += PERSPECTIVE_BONUS.get(perspective, 0.0)
    score += max(0.0, min(1.0, relationship_strength)) * 0.2
    if goal_relevance:
        score += 0.10
    if location_relevance:
        score += 0.05
    score = _compress_high_importance(score)
    return _clamp(score)


def determine_memory_category(
    *,
    importance: float,
    tick_age: int = 0,
    tick_minutes: int = 5,
) -> str:
    """Determine the time layer for a memory."""
    if importance >= 0.85:
        return MemoryCategory.LONG_TERM
    if importance >= 0.45:
        return MemoryCategory.MEDIUM_TERM

    age_minutes = tick_age * tick_minutes
    if age_minutes < 30:
        return MemoryCategory.SHORT_TERM
    if age_minutes < 360:
        return MemoryCategory.MEDIUM_TERM
    return MemoryCategory.LONG_TERM


def should_consolidate_memory(
    current_category: str,
    importance: float,
    access_count: int,
    tick_age: int,
    tick_minutes: int = 5,
) -> bool:
    """Determine if a memory should be promoted to a higher category."""
    if current_category == MemoryCategory.LONG_TERM:
        return False

    if access_count >= 3:
        return True

    age_minutes = tick_age * tick_minutes
    if importance >= 0.6 and age_minutes >= 60:
        return True

    if current_category == MemoryCategory.SHORT_TERM and age_minutes >= 120:
        return True

    return False
