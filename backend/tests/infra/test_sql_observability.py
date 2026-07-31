from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.infra.sql_observability import track_sql_queries


@pytest.mark.asyncio
async def test_track_sql_queries_supports_nested_operations(db_session):
    with track_sql_queries() as outer:
        await db_session.execute(text("SELECT 1"))
        with track_sql_queries() as inner:
            await db_session.execute(text("SELECT 2"))

    assert outer.query_count == 2
    assert inner.query_count == 1
    assert outer.duration_seconds >= inner.duration_seconds >= 0


@pytest.mark.asyncio
async def test_track_sql_queries_counts_failed_statements(db_session):
    with track_sql_queries() as stats:
        with pytest.raises(OperationalError):
            await db_session.execute(text("SELECT * FROM table_that_does_not_exist"))

    assert stats.query_count == 1
    assert stats.duration_seconds >= 0
