from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text

from app.sim.errors import TickInProgressError

_LOCAL_LOCKS: dict[str, asyncio.Lock] = {}


@asynccontextmanager
async def acquire_run_tick_lock(engine: Any, run_id: str) -> AsyncIterator[None]:
    """Acquire a non-blocking run-scoped lock for one complete tick."""
    if engine.dialect.name == "postgresql":
        async with _acquire_postgres_lock(engine, run_id):
            yield
        return

    lock = _LOCAL_LOCKS.setdefault(run_id, asyncio.Lock())
    if lock.locked():
        raise TickInProgressError(run_id)
    await lock.acquire()
    try:
        yield
    finally:
        lock.release()
        if not lock.locked():
            _LOCAL_LOCKS.pop(run_id, None)


@asynccontextmanager
async def _acquire_postgres_lock(engine: Any, run_id: str) -> AsyncIterator[None]:
    # Transaction-scoped locks work safely through Neon/PgBouncer transaction pooling
    # and are released automatically even when the tick fails or is cancelled.
    async with engine.begin() as connection:
        acquired = await connection.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended(:run_id, 0))"),
            {"run_id": run_id},
        )
        if not acquired:
            raise TickInProgressError(run_id)
        yield
