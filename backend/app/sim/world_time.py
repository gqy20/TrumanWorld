from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.sim.context import DEFAULT_WORLD_START_TIME


def resolve_world_start(run) -> datetime:
    metadata = run.metadata_json or {}
    raw_start = metadata.get("world_start_time")
    if isinstance(raw_start, str):
        try:
            world_start = datetime.fromisoformat(raw_start)
        except ValueError:
            world_start = DEFAULT_WORLD_START_TIME
    else:
        world_start = DEFAULT_WORLD_START_TIME
    if world_start.tzinfo is None:
        world_start = world_start.replace(tzinfo=UTC)
    return world_start


def parse_world_datetime(raw: str) -> datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def resolve_tick_bound(
    world_datetime: str | None,
    world_start: datetime,
    tick_minutes: int,
    current_value: int | None,
    *,
    prefer_min: bool,
) -> int | None:
    if not world_datetime:
        return current_value

    parsed = parse_world_datetime(world_datetime)
    if parsed is None:
        return current_value

    candidate = max(0, int(((parsed - world_start).total_seconds() / 60) // tick_minutes))
    if current_value is None:
        return candidate
    return min(current_value, candidate) if prefer_min else max(current_value, candidate)


def tick_to_world_time(tick_no: int, world_start: datetime, tick_minutes: int) -> tuple[str, str]:
    dt = world_start + timedelta(minutes=tick_no * tick_minutes)
    return dt.strftime("%H:%M"), dt.strftime("%Y-%m-%d")
