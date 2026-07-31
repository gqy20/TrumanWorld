from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy import event
from sqlalchemy.engine import Engine


@dataclass(slots=True)
class SqlQueryStats:
    query_count: int = 0
    duration_seconds: float = 0.0

    @property
    def duration_ms(self) -> float:
        return round(self.duration_seconds * 1000, 2)


_active_stats: ContextVar[tuple[SqlQueryStats, ...]] = ContextVar(
    "trumanworld_active_sql_stats",
    default=(),
)
_OBSERVATION_ATTRIBUTE = "_trumanworld_sql_observation"


@contextmanager
def track_sql_queries() -> Iterator[SqlQueryStats]:
    stats = SqlQueryStats()
    token = _active_stats.set((*_active_stats.get(), stats))
    try:
        yield stats
    finally:
        _active_stats.reset(token)


def _before_cursor_execute(_conn, _cursor, _statement, _parameters, context, _executemany):
    scopes = _active_stats.get()
    if scopes:
        setattr(context, _OBSERVATION_ATTRIBUTE, (perf_counter(), scopes))


def _finish_observation(context) -> None:
    observation = getattr(context, _OBSERVATION_ATTRIBUTE, None)
    if observation is None:
        return
    delattr(context, _OBSERVATION_ATTRIBUTE)
    started_at, scopes = observation
    duration_seconds = perf_counter() - started_at
    for stats in scopes:
        stats.query_count += 1
        stats.duration_seconds += duration_seconds


def _after_cursor_execute(_conn, _cursor, _statement, _parameters, context, _executemany):
    _finish_observation(context)


def _handle_error(exception_context):
    context = exception_context.execution_context
    if context is not None:
        _finish_observation(context)


def _install_sql_listeners() -> None:
    listeners = (
        ("before_cursor_execute", _before_cursor_execute),
        ("after_cursor_execute", _after_cursor_execute),
        ("handle_error", _handle_error),
    )
    for event_name, listener in listeners:
        if not event.contains(Engine, event_name, listener):
            event.listen(Engine, event_name, listener)


_install_sql_listeners()
