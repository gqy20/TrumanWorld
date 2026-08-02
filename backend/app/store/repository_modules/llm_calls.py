from __future__ import annotations
# ruff: noqa: F403,F405

from app.store.repository_modules._common import *


class LlmCallRepository:
    """LLM 调用记录的持久化操作。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, record: LlmCall) -> None:
        self.session.add(record)
        await self.session.commit()

    async def get_token_totals(self, run_id: str) -> dict[str, int | float | str | None]:
        """查询指定 run 的全量 token 累计。

        Returns:
            包含 input_tokens, output_tokens, reasoning_tokens, cache_read_tokens,
            cache_creation_tokens 以及最近一次 provider/model 的字典
        """
        from sqlalchemy import func as sql_func

        stmt = select(
            sql_func.coalesce(sql_func.sum(LlmCall.input_tokens), 0).label("input_tokens"),
            sql_func.coalesce(sql_func.sum(LlmCall.output_tokens), 0).label("output_tokens"),
            sql_func.coalesce(sql_func.sum(LlmCall.reasoning_tokens), 0).label("reasoning_tokens"),
            sql_func.coalesce(sql_func.sum(LlmCall.cache_read_tokens), 0).label(
                "cache_read_tokens"
            ),
            sql_func.coalesce(sql_func.sum(LlmCall.cache_creation_tokens), 0).label(
                "cache_creation_tokens"
            ),
            sql_func.coalesce(sql_func.sum(LlmCall.total_cost_usd), 0.0).label("total_cost_usd"),
        ).where(LlmCall.run_id == run_id)
        result = await self.session.execute(stmt)
        row = result.one()
        latest_stmt = (
            select(LlmCall.provider, LlmCall.model)
            .where(LlmCall.run_id == run_id)
            .order_by(LlmCall.created_at.desc(), LlmCall.id.desc())
            .limit(1)
        )
        latest_result = await self.session.execute(latest_stmt)
        latest_row = latest_result.first()
        return {
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "reasoning_tokens": row.reasoning_tokens,
            "cache_read_tokens": row.cache_read_tokens,
            "cache_creation_tokens": row.cache_creation_tokens,
            "total_cost_usd": float(row.total_cost_usd),
            "provider": latest_row.provider if latest_row is not None else None,
            "model": latest_row.model if latest_row is not None else None,
        }
