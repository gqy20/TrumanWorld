from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.logging import get_logger
from app.infra.metrics import observe_llm_records

if TYPE_CHECKING:
    from app.store.models import LlmCall


logger = get_logger(__name__)


class LlmCallWriter:
    async def persist(self, *, run_id: str, llm_records: list[LlmCall], engine) -> None:
        if not llm_records or engine is None:
            return

        try:
            async with AsyncSession(engine, expire_on_commit=False) as llm_session:
                for record in llm_records:
                    llm_session.add(record)
                await llm_session.commit()
            observe_llm_records(llm_records)
        except Exception as exc:
            logger.warning(f"Failed to persist llm_calls for run {run_id}: {exc}")
