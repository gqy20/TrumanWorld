from __future__ import annotations

# ruff: noqa: F403,F405

from sqlalchemy import true

from app.store.repository_modules._common import *


WORLD_EVENT_TYPES = (
    "speech",
    "talk",
    "listen",
    "move",
    "move_rejected",
    "talk_rejected",
)


@dataclass(slots=True)
class WorldStats:
    event_counts: dict[str, int]
    director_total: int
    director_executed: int
    token_totals: dict[str, int | str | None]


class WorldStatsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_run(self, run_id: str) -> WorldStats:
        event_stats = (
            select(
                *[
                    func.coalesce(
                        func.sum(case((Event.event_type == event_type, 1), else_=0)),
                        0,
                    ).label(event_type)
                    for event_type in WORLD_EVENT_TYPES
                ]
            )
            .where(Event.run_id == run_id)
            .subquery()
        )
        director_stats = (
            select(
                func.count(DirectorMemory.id).label("director_total"),
                func.coalesce(
                    func.sum(case((DirectorMemory.was_executed.is_(True), 1), else_=0)),
                    0,
                ).label("director_executed"),
            )
            .where(DirectorMemory.run_id == run_id)
            .subquery()
        )
        token_stats = (
            select(
                func.coalesce(func.sum(LlmCall.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(LlmCall.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(LlmCall.reasoning_tokens), 0).label("reasoning_tokens"),
                func.coalesce(func.sum(LlmCall.cache_read_tokens), 0).label("cache_read_tokens"),
                func.coalesce(func.sum(LlmCall.cache_creation_tokens), 0).label(
                    "cache_creation_tokens"
                ),
            )
            .where(LlmCall.run_id == run_id)
            .subquery()
        )
        latest_provider = (
            select(LlmCall.provider)
            .where(LlmCall.run_id == run_id)
            .order_by(LlmCall.created_at.desc(), LlmCall.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        latest_model = (
            select(LlmCall.model)
            .where(LlmCall.run_id == run_id)
            .order_by(LlmCall.created_at.desc(), LlmCall.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        statement = (
            select(
                *[event_stats.c[event_type] for event_type in WORLD_EVENT_TYPES],
                director_stats.c.director_total,
                director_stats.c.director_executed,
                token_stats.c.input_tokens,
                token_stats.c.output_tokens,
                token_stats.c.reasoning_tokens,
                token_stats.c.cache_read_tokens,
                token_stats.c.cache_creation_tokens,
                latest_provider.label("provider"),
                latest_model.label("model"),
            )
            .select_from(event_stats)
            .join(director_stats, true())
            .join(token_stats, true())
        )
        row = (await self.session.execute(statement)).one()
        return WorldStats(
            event_counts={
                event_type: int(getattr(row, event_type)) for event_type in WORLD_EVENT_TYPES
            },
            director_total=int(row.director_total),
            director_executed=int(row.director_executed),
            token_totals={
                "input_tokens": int(row.input_tokens),
                "output_tokens": int(row.output_tokens),
                "reasoning_tokens": int(row.reasoning_tokens),
                "cache_read_tokens": int(row.cache_read_tokens),
                "cache_creation_tokens": int(row.cache_creation_tokens),
                "provider": row.provider,
                "model": row.model,
            },
        )
