from datetime import UTC, datetime
from types import SimpleNamespace

from app.sim.context import DEFAULT_WORLD_START_TIME
from app.sim.world_time import (
    parse_world_datetime,
    resolve_tick_bound,
    resolve_world_start,
    tick_to_world_time,
)


def test_resolve_world_start_uses_run_metadata_and_normalizes_timezone():
    run = SimpleNamespace(metadata_json={"world_start_time": "2026-03-02T07:00:00"})

    assert resolve_world_start(run) == datetime(2026, 3, 2, 7, 0, tzinfo=UTC)


def test_resolve_world_start_falls_back_for_invalid_metadata():
    run = SimpleNamespace(metadata_json={"world_start_time": "not-a-date"})

    assert resolve_world_start(run) == DEFAULT_WORLD_START_TIME


def test_parse_world_datetime_accepts_supported_formats():
    assert parse_world_datetime("2026-03-02T07:05") == datetime(2026, 3, 2, 7, 5, tzinfo=UTC)
    assert parse_world_datetime("2026-03-02 07:05") == datetime(2026, 3, 2, 7, 5, tzinfo=UTC)
    assert parse_world_datetime("2026-03-02T07:05:30") == datetime(
        2026, 3, 2, 7, 5, 30, tzinfo=UTC
    )


def test_resolve_tick_bound_combines_datetime_with_existing_bounds():
    world_start = datetime(2026, 3, 2, 7, 0, tzinfo=UTC)

    assert resolve_tick_bound("2026-03-02T07:15", world_start, 5, None, prefer_min=True) == 3
    assert resolve_tick_bound("2026-03-02T07:15", world_start, 5, 2, prefer_min=True) == 2
    assert resolve_tick_bound("2026-03-02T07:15", world_start, 5, 4, prefer_min=False) == 4


def test_tick_to_world_time_formats_tick_relative_to_world_start():
    world_start = datetime(2026, 3, 2, 7, 0, tzinfo=UTC)

    assert tick_to_world_time(3, world_start, 5) == ("07:15", "2026-03-02")
