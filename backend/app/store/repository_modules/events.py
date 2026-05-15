from __future__ import annotations
# ruff: noqa: F403,F405

from app.store.repository_modules._common import *

class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _event_api_columns():
        return (
            Event.id,
            Event.tick_no,
            Event.world_time,
            Event.event_type,
            Event.actor_agent_id,
            Event.target_agent_id,
            Event.location_id,
            Event.importance,
            Event.visibility,
            Event.payload,
            Event.created_at,
        )

    @staticmethod
    def _to_event_api_rows(rows) -> list[EventApiRow]:
        return [
            EventApiRow(
                id=row.id,
                tick_no=row.tick_no,
                world_time=row.world_time,
                event_type=row.event_type,
                actor_agent_id=row.actor_agent_id,
                target_agent_id=row.target_agent_id,
                location_id=row.location_id,
                importance=row.importance,
                visibility=row.visibility,
                payload=row.payload or {},
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def list_for_run(
        self, run_id: str, limit: int = 50, since_tick: int | None = None
    ) -> Sequence[Event]:
        # Priority ordering mirrors list_recent_events: social/move surface before
        # work/rest noise so the world snapshot always contains meaningful events.
        event_priority = case(
            (
                Event.event_type.in_(
                    [
                        "talk",
                        "speech",
                        "listen",
                        "conversation_started",
                        "conversation_joined",
                        "move",
                    ]
                ),
                0,
            ),
            (Event.event_type.in_(["work", "rest"]), 2),
            else_=1,
        )
        stmt: Select[tuple[Event]] = (
            select(Event)
            .where(Event.run_id == run_id)
            .order_by(event_priority, Event.tick_no.desc(), Event.created_at.desc())
            .limit(limit)
        )
        # 增量查询：只获取指定 tick 之后的事件
        if since_tick is not None:
            stmt = stmt.where(Event.tick_no > since_tick)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_api_rows_for_run(
        self, run_id: str, limit: int = 50, since_tick: int | None = None
    ) -> Sequence[EventApiRow]:
        event_priority = case(
            (
                Event.event_type.in_(
                    [
                        "talk",
                        "speech",
                        "listen",
                        "conversation_started",
                        "conversation_joined",
                        "move",
                    ]
                ),
                0,
            ),
            (Event.event_type.in_(["work", "rest"]), 2),
            else_=1,
        )
        stmt = (
            select(*self._event_api_columns())
            .where(Event.run_id == run_id)
            .order_by(event_priority, Event.tick_no.desc(), Event.created_at.desc())
            .limit(limit)
        )
        if since_tick is not None:
            stmt = stmt.where(Event.tick_no > since_tick)
        result = await self.session.execute(stmt)
        return self._to_event_api_rows(result.all())

    async def list_timeline_events(
        self,
        run_id: str,
        tick_from: int | None = None,
        tick_to: int | None = None,
        event_type: str | None = None,
        actor_agent_id: str | None = None,
        target_agent_id: str | None = None,
        keyword: str | None = None,
        limit: int = 2000,
        offset: int = 0,
        order_desc: bool = False,
    ) -> tuple[Sequence[Event], int]:
        """专为时间线回放设计的全量查询，支持多维过滤和排序。

        Args:
            order_desc: 是否按 tick 倒序排列（最新事件在前），默认为 False（正序）

        Returns:
            (events, total_count) 元组，total_count 为过滤后的总条数（用于分页提示）。
        """
        from sqlalchemy import func as sql_func

        conditions = [Event.run_id == run_id]

        if tick_from is not None:
            conditions.append(Event.tick_no >= tick_from)
        if tick_to is not None:
            conditions.append(Event.tick_no <= tick_to)
        if event_type:
            # 支持逗号分隔的多类型过滤，如 "talk,move"
            types = [t.strip() for t in event_type.split(",") if t.strip()]
            if types:
                conditions.append(Event.event_type.in_(types))
        if actor_agent_id:
            conditions.append(
                or_(Event.actor_agent_id == actor_agent_id, Event.target_agent_id == actor_agent_id)
            )

        where_clause = and_(*conditions)

        # 统计总条数
        count_stmt = select(sql_func.count(Event.id)).where(where_clause)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one() or 0

        # 根据 order_desc 参数决定排序方向
        if order_desc:
            # 按 tick 倒序 + created_at 倒序（最新事件在前，方便复盘最近发生的事件）
            stmt: Select[tuple[Event]] = (
                select(Event)
                .where(where_clause)
                .order_by(Event.tick_no.desc(), Event.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        else:
            # 按 tick 正序 + created_at 正序（方便时间线从旧到新回放）
            stmt = (
                select(Event)
                .where(where_clause)
                .order_by(Event.tick_no.asc(), Event.created_at.asc())
                .limit(limit)
                .offset(offset)
            )
        result = await self.session.execute(stmt)
        return result.scalars().all(), total

    async def list_timeline_api_rows(
        self,
        run_id: str,
        tick_from: int | None = None,
        tick_to: int | None = None,
        event_type: str | None = None,
        actor_agent_id: str | None = None,
        target_agent_id: str | None = None,
        keyword: str | None = None,
        limit: int = 2000,
        offset: int = 0,
        order_desc: bool = False,
    ) -> tuple[Sequence[EventApiRow], int]:
        from sqlalchemy import func as sql_func

        conditions = [Event.run_id == run_id]

        if tick_from is not None:
            conditions.append(Event.tick_no >= tick_from)
        if tick_to is not None:
            conditions.append(Event.tick_no <= tick_to)
        if event_type:
            types = [t.strip() for t in event_type.split(",") if t.strip()]
            if types:
                conditions.append(Event.event_type.in_(types))
        if actor_agent_id:
            conditions.append(
                or_(Event.actor_agent_id == actor_agent_id, Event.target_agent_id == actor_agent_id)
            )

        where_clause = and_(*conditions)

        count_stmt = select(sql_func.count(Event.id)).where(where_clause)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one() or 0

        stmt = select(*self._event_api_columns()).where(where_clause)
        if order_desc:
            stmt = stmt.order_by(Event.tick_no.desc(), Event.created_at.desc())
        else:
            stmt = stmt.order_by(Event.tick_no.asc(), Event.created_at.asc())
        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return self._to_event_api_rows(result.all()), total

    async def count_events_by_type(
        self,
        run_id: str,
        tick_from: int | None = None,
        tick_to: int | None = None,
        event_types: list[str] | None = None,
    ) -> dict[str, int]:
        """统计指定 tick 范围内各类型事件的数量。

        Args:
            run_id: 运行 ID
            tick_from: 起始 tick（包含）
            tick_to: 结束 tick（包含）
            event_types: 要统计的事件类型列表，默认为常用类型

        Returns:
            事件类型到数量的映射字典
        """
        from sqlalchemy import func as sql_func

        if event_types is None:
            event_types = ["speech", "listen", "move", "move_rejected", "talk_rejected"]

        conditions = [Event.run_id == run_id]
        if tick_from is not None:
            conditions.append(Event.tick_no >= tick_from)
        if tick_to is not None:
            conditions.append(Event.tick_no <= tick_to)

        where_clause = and_(*conditions)

        # 按事件类型分组统计
        stmt = (
            select(Event.event_type, sql_func.count(Event.id))
            .where(where_clause)
            .where(Event.event_type.in_(event_types))
            .group_by(Event.event_type)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        return {row[0]: row[1] for row in rows}

    async def create(self, event: Event) -> Event:
        await self.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def add(self, event: Event) -> Event:
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def add_many(self, events: Sequence[Event]) -> Sequence[Event]:
        self.session.add_all(list(events))
        await self.session.flush()
        for event in events:
            await self.session.refresh(event)
        return events

    async def create_many(self, events: Sequence[Event]) -> Sequence[Event]:
        await self.add_many(events)
        await self.session.commit()
        for event in events:
            await self.session.refresh(event)
        return events

