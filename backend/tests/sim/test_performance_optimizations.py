"""TDD: 性能优化测试

覆盖三个优化点：
1. Phase1 并行查询：build_agent_recent_events 和 build_agent_memory_cache 应并行执行
2. Director plan 消除重复事件查询：observe_run 和 _build_auto_plan 中事件只查一次
3. Day boundary 预加载并行化：has_plan_for_today/记忆预加载应并行执行
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.sim.agent_snapshot_builder import build_agent_memory_cache
from app.store.models import Agent, Location, Memory, SimulationRun


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_run(run_id: str) -> SimulationRun:
    return SimulationRun(
        id=run_id,
        name="perf-test",
        status="running",
        current_tick=5,
        tick_minutes=5,
    )


def _make_location(loc_id: str, run_id: str) -> Location:
    return Location(
        id=loc_id,
        run_id=run_id,
        name="Test Square",
        location_type="plaza",
        capacity=10,
    )


def _make_agent(agent_id: str, run_id: str, loc_id: str, role: str = "cast") -> Agent:
    return Agent(
        id=agent_id,
        run_id=run_id,
        name=f"Agent-{agent_id}",
        occupation="resident",
        home_location_id=loc_id,
        current_location_id=loc_id,
        current_goal="rest",
        personality={},
        profile={"agent_config_id": role, "world_role": role},
        status={},
        current_plan={},
    )


# ---------------------------------------------------------------------------
# 1. Phase1 并行查询：build_agent_recent_events
# ---------------------------------------------------------------------------


class TestBuildAgentRecentEventsParallel:
    """build_agent_recent_events 应并发查询各 agent，不应串行等待。

    验证方式：mock list_recent_events，让每次调用等待一小段时间，
    验证总耗时远小于 N * 单次耗时（即并行执行）。
    """

    @pytest.mark.asyncio
    async def test_recent_events_queries_run_concurrently(self, db_session):
        """多个 agent 的 recent_events 查询应并发执行，不串行。"""
        run_id = "perf-recent-events-concurrent"
        run = _make_run(run_id)
        loc = _make_location(f"{run_id}-loc", run_id)
        agents = [_make_agent(f"{run_id}-agent-{i}", run_id, loc.id) for i in range(4)]
        db_session.add_all([run, loc] + agents)
        await db_session.commit()

        call_times: list[float] = []
        call_order: list[str] = []

        async def slow_list_recent_events(
            self_or_run_id, agent_id_or_run_id=None, agent_id=None, **kwargs
        ):
            # patch.object 调用时第一个参数是 self（repo 实例）
            actual_agent_id = agent_id_or_run_id if agent_id is None else agent_id
            call_order.append(actual_agent_id)
            start = asyncio.get_event_loop().time()
            await asyncio.sleep(0.05)  # 模拟 50ms 的 DB 查询延迟
            call_times.append(asyncio.get_event_loop().time() - start)
            return []

        from app.store.repositories import AgentRepository

        with patch.object(AgentRepository, "list_recent_events", slow_list_recent_events):
            from app.sim.agent_snapshot_builder import build_agent_recent_events
            from app.sim.world import AgentState, LocationState

            agent_states = {
                a.id: AgentState(
                    id=a.id, name=a.name, location_id=loc.id, status={}, occupation="resident"
                )
                for a in agents
            }
            location_states = {
                loc.id: LocationState(
                    id=loc.id, name=loc.name, capacity=10, occupants=set(), location_type="plaza"
                )
            }

            import time

            t0 = time.monotonic()
            result = await build_agent_recent_events(
                session=db_session,
                run_id=run_id,
                agents=agents,
                agent_states=agent_states,
                location_states=location_states,
            )
            elapsed = time.monotonic() - t0

        # 4 个 agent 各需 50ms，串行需 200ms+，并行应该 < 100ms
        assert elapsed < 0.15, (
            f"build_agent_recent_events 应并行执行，但耗时 {elapsed:.3f}s（预期 < 0.15s）"
        )
        # 所有 agent 都应被处理
        assert set(result.keys()) == {a.id for a in agents}


# ---------------------------------------------------------------------------
# 2. Phase1 并行查询：build_agent_memory_cache
# ---------------------------------------------------------------------------


class TestBuildAgentMemoryCacheParallel:
    """build_agent_memory_cache 应并发查询各 agent 的记忆，不串行。"""

    @pytest.mark.asyncio
    async def test_memory_cache_queries_run_concurrently(self, db_session):
        """多个 agent 的记忆查询应并发执行。"""
        run_id = "perf-memory-cache-concurrent"
        run = _make_run(run_id)
        loc = _make_location(f"{run_id}-loc", run_id)
        agents = [_make_agent(f"{run_id}-agent-{i}", run_id, loc.id) for i in range(4)]
        db_session.add_all([run, loc] + agents)
        await db_session.commit()

        query_call_count = 0
        concurrent_peak = 0
        current_concurrent = 0

        # 通过 patch session.execute 注入延迟来验证并发
        real_execute = db_session.execute

        async def slow_execute(stmt, *args, **kwargs):
            nonlocal current_concurrent, concurrent_peak, query_call_count
            query_call_count += 1
            current_concurrent += 1
            concurrent_peak = max(concurrent_peak, current_concurrent)
            await asyncio.sleep(0.02)  # 20ms 延迟
            result = await real_execute(stmt, *args, **kwargs)
            current_concurrent -= 1
            return result

        import time

        with patch.object(db_session, "execute", slow_execute):
            t0 = time.monotonic()
            result = await build_agent_memory_cache(
                session=db_session,
                run_id=run_id,
                agents=agents,
            )
            elapsed = time.monotonic() - t0

        # 4 个 agent，串行需要 4*20ms=80ms+，并行应快很多
        assert elapsed < 0.12, (
            f"build_agent_memory_cache 应并行执行，但耗时 {elapsed:.3f}s（预期 < 0.12s）"
        )
        # 结果中应包含所有 agent
        assert set(result.keys()) == {a.id for a in agents}

    @pytest.mark.asyncio
    async def test_memory_cache_returns_correct_structure(self, db_session):
        """build_agent_memory_cache 并行化后，结果结构应与串行版本一致。"""
        run_id = "perf-memory-cache-structure"
        run = _make_run(run_id)
        loc = _make_location(f"{run_id}-loc", run_id)
        agent = _make_agent(f"{run_id}-agent-0", run_id, loc.id)
        db_session.add_all([run, loc, agent])
        await db_session.commit()

        # 添加一条记忆
        mem = Memory(
            id=f"{run_id}-mem-1",
            run_id=run_id,
            agent_id=agent.id,
            tick_no=1,
            memory_type="event",
            memory_category="long_term",
            content="测试记忆内容",
            summary="测试摘要",
            importance=0.5,
        )
        db_session.add(mem)
        await db_session.commit()

        result = await build_agent_memory_cache(
            session=db_session,
            run_id=run_id,
            agents=[agent],
        )

        assert agent.id in result
        cache = result[agent.id]
        assert "short_term" in cache
        assert "medium_term" in cache
        assert "long_term" in cache
        assert "about_others" in cache
        assert "all" in cache
        assert len(cache["long_term"]) == 1
        assert cache["long_term"][0]["content"] == "测试记忆内容"


# ---------------------------------------------------------------------------
# 3. Director plan 消除重复事件查询
# ---------------------------------------------------------------------------


class TestDirectorPlanNoDuplicateEventQuery:
    """_build_auto_plan 中 events 只应查询一次，不应重复查询。

    当前问题：
    - observe_run() → event_repo.list_for_run(limit=20)
    - _build_auto_plan() 又调用 event_repo.list_for_run(limit=20)
    优化后应只查询一次。
    """

    @pytest.mark.asyncio
    async def test_events_queried_only_once_in_auto_plan(self, db_session):
        """_build_auto_plan 中事件只应被查询一次。"""
        from app.scenario.truman_world.coordinator import TrumanWorldCoordinator
        from app.store.repositories import EventRepository

        run_id = "perf-director-events"
        run = SimulationRun(
            id=run_id,
            name="director-events-test",
            status="running",
            current_tick=3,
            tick_minutes=5,
        )
        loc = _make_location(f"{run_id}-loc", run_id)
        cast = _make_agent(f"{run_id}-cast", run_id, loc.id, "cast")
        truman = _make_agent(f"{run_id}-truman", run_id, loc.id, "truman")
        truman.profile = {"agent_config_id": "truman", "world_role": "truman"}
        db_session.add_all([run, loc, cast, truman])
        await db_session.commit()

        list_for_run_calls = []
        original_list_for_run = EventRepository.list_for_run

        async def tracking_list_for_run(self, run_id, limit=None, **kwargs):
            list_for_run_calls.append({"run_id": run_id, "limit": limit})
            return await original_list_for_run(self, run_id, limit=limit, **kwargs)

        with patch.object(EventRepository, "list_for_run", tracking_list_for_run):
            coordinator = TrumanWorldCoordinator(db_session)
            agents = [cast, truman]
            await coordinator._build_auto_plan(run_id, agents)

        # 事件查询次数应该只有 1 次（不是 2 次）
        event_queries = [c for c in list_for_run_calls]
        assert len(event_queries) <= 1, (
            f"事件应只查询一次，但实际查询了 {len(event_queries)} 次: {event_queries}"
        )


# ---------------------------------------------------------------------------
# 4. Day boundary 预加载并行化（has_plan_for_today 检查 + 记忆预加载）
# ---------------------------------------------------------------------------


class TestDayBoundaryPreloadParallel:
    """run_morning_planning 中 has_plan_for_today 检查和记忆预加载应并行执行。

    当前：
        for agent in agents:
            if not await has_plan_for_today(...):   # 串行
                pending.append(agent)
        for agent in pending:
            memories_by_agent[agent.id] = await _load_recent_memories(...)  # 串行

    优化后：
        - has_plan_for_today 并行检查所有 agent
        - _load_recent_memories 并行加载所有待处理 agent
    """

    @pytest.mark.asyncio
    async def test_has_plan_check_runs_concurrently(self):
        """has_plan_for_today 检查应对所有 agent 并行执行。"""
        from app.sim.day_boundary import run_morning_planning
        from app.sim.world import WorldState
        from datetime import datetime

        world = MagicMock(spec=WorldState)
        world.current_time = datetime(2026, 3, 10, 6, 0)
        world.tick_minutes = 5
        world._time_period = MagicMock(return_value="morning")
        world._weekday_name = MagicMock(return_value="周一")

        agents_data = [
            {"id": f"agent-{i}", "name": f"Agent{i}", "profile": {}, "personality": {}}
            for i in range(4)
        ]

        concurrent_count = 0
        peak_concurrent = 0

        async def slow_has_plan(session, run_id, agent_id, today):
            nonlocal concurrent_count, peak_concurrent
            concurrent_count += 1
            peak_concurrent = max(peak_concurrent, concurrent_count)
            await asyncio.sleep(0.04)  # 40ms
            concurrent_count -= 1
            return False  # 所有 agent 都需要生成计划

        async def mock_list_for_run(run_id):
            return [
                MagicMock(
                    id=d["id"],
                    name=d["name"],
                    profile=d["profile"],
                    personality=d["personality"],
                )
                for d in agents_data
            ]

        async def mock_load_memories(session, run_id, agent_id, limit=5):
            return []

        async def mock_load_yesterday_execution(
            session,
            run_id,
            agent_id,
            yesterday,
            current_tick,
            ticks_per_day,
        ):
            return ""

        mock_agent_repo = AsyncMock()
        mock_agent_repo.list_for_run = mock_list_for_run

        mock_runtime = AsyncMock()
        mock_runtime.run_planner = AsyncMock(return_value=None)

        mock_engine = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session_ctx)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session_ctx.get = AsyncMock(return_value=None)
        mock_session_ctx.add = MagicMock()
        mock_session_ctx.commit = AsyncMock()

        import time

        with (
            patch("app.sim.day_boundary.AgentRepository", return_value=mock_agent_repo),
            patch("app.sim.day_boundary.MemoryRepository") as mock_mem_repo_cls,
            patch("app.sim.day_boundary.has_plan_for_today", slow_has_plan),
            patch("app.sim.day_boundary._load_recent_memories", mock_load_memories),
            patch(
                "app.sim.day_boundary._load_yesterday_plan_execution", mock_load_yesterday_execution
            ),
            patch("sqlalchemy.ext.asyncio.AsyncSession", return_value=mock_session_ctx),
        ):
            mock_mem_repo = AsyncMock()
            mock_mem_repo.create_many = AsyncMock()
            mock_mem_repo_cls.return_value = mock_mem_repo

            t0 = time.monotonic()
            await run_morning_planning(
                run_id="perf-day-boundary",
                tick_no=5,
                world=world,
                engine=mock_engine,
                agent_runtime=mock_runtime,
            )
            elapsed = time.monotonic() - t0

        # 4 个 agent 各 40ms，串行需 160ms+，并行应 < 80ms
        assert elapsed < 0.10, (
            f"has_plan_for_today 应并行执行，但耗时 {elapsed:.3f}s（预期 < 0.10s）"
        )
        # 并行时峰值并发应 > 1
        assert peak_concurrent > 1, (
            f"has_plan_for_today 应并行执行，但峰值并发为 {peak_concurrent}（预期 > 1）"
        )

    @pytest.mark.asyncio
    async def test_memory_preload_runs_concurrently_in_morning_planning(self):
        """run_morning_planning 中记忆预加载应并行执行。"""
        from app.sim.day_boundary import run_morning_planning
        from app.sim.world import WorldState
        from datetime import datetime

        world = MagicMock(spec=WorldState)
        world.current_time = datetime(2026, 3, 10, 6, 0)
        world.tick_minutes = 5
        world._time_period = MagicMock(return_value="morning")
        world._weekday_name = MagicMock(return_value="周一")

        agents_data = [
            {"id": f"agent-mem-{i}", "name": f"Agent{i}", "profile": {}, "personality": {}}
            for i in range(4)
        ]

        mem_load_concurrent = 0
        mem_load_peak = 0

        async def slow_load_memories(session, run_id, agent_id, limit=5):
            nonlocal mem_load_concurrent, mem_load_peak
            mem_load_concurrent += 1
            mem_load_peak = max(mem_load_peak, mem_load_concurrent)
            await asyncio.sleep(0.04)  # 40ms
            mem_load_concurrent -= 1
            return []

        async def mock_list_for_run(run_id):
            return [
                MagicMock(
                    id=d["id"],
                    name=d["name"],
                    profile=d["profile"],
                    personality=d["personality"],
                )
                for d in agents_data
            ]

        async def mock_load_yesterday_execution(
            session,
            run_id,
            agent_id,
            yesterday,
            current_tick,
            ticks_per_day,
        ):
            return ""

        mock_agent_repo = AsyncMock()
        mock_agent_repo.list_for_run = mock_list_for_run

        mock_runtime = AsyncMock()
        mock_runtime.run_planner = AsyncMock(return_value=None)

        mock_engine = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session_ctx)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_session_ctx.get = AsyncMock(return_value=None)
        mock_session_ctx.add = MagicMock()
        mock_session_ctx.commit = AsyncMock()

        import time

        with (
            patch("app.sim.day_boundary.AgentRepository", return_value=mock_agent_repo),
            patch("app.sim.day_boundary.MemoryRepository") as mock_mem_repo_cls,
            patch("app.sim.day_boundary.has_plan_for_today", AsyncMock(return_value=False)),
            patch("app.sim.day_boundary._load_recent_memories", slow_load_memories),
            patch(
                "app.sim.day_boundary._load_yesterday_plan_execution", mock_load_yesterday_execution
            ),
            patch("sqlalchemy.ext.asyncio.AsyncSession", return_value=mock_session_ctx),
        ):
            mock_mem_repo = AsyncMock()
            mock_mem_repo.create_many = AsyncMock()
            mock_mem_repo_cls.return_value = mock_mem_repo

            t0 = time.monotonic()
            await run_morning_planning(
                run_id="perf-day-boundary-mem",
                tick_no=5,
                world=world,
                engine=mock_engine,
                agent_runtime=mock_runtime,
            )
            elapsed = time.monotonic() - t0

        # 4 个 agent 各 40ms，串行需 160ms+，并行应 < 80ms
        assert elapsed < 0.10, (
            f"_load_recent_memories 应并行执行，但耗时 {elapsed:.3f}s（预期 < 0.10s）"
        )
        assert mem_load_peak > 1, (
            f"_load_recent_memories 应并行执行，但峰值并发为 {mem_load_peak}（预期 > 1）"
        )


# ---------------------------------------------------------------------------
# 5. persistence.py: persist_tick_memories agents+locations 并行查询
# ---------------------------------------------------------------------------


class TestPersistTickMemoriesParallelQueries:
    """persist_tick_memories 中 agents 和 locations 的查询应并行执行。"""

    @pytest.mark.asyncio
    async def test_agents_and_locations_queried_in_parallel(self, db_session):
        """agents 和 locations 两个独立 DB 查询应并行执行，不串行。"""
        from app.sim.persistence import PersistenceManager
        from app.store.repositories import AgentRepository, LocationRepository

        call_log: list[tuple[str, float]] = []

        real_agent_list = AgentRepository.list_for_run
        real_loc_list = LocationRepository.list_for_run

        async def slow_agent_list(self, run_id):
            import time

            call_log.append(("agent", time.monotonic()))
            await asyncio.sleep(0.05)
            return await real_agent_list(self, run_id)

        async def slow_loc_list(self, run_id):
            import time

            call_log.append(("location", time.monotonic()))
            await asyncio.sleep(0.05)
            return await real_loc_list(self, run_id)

        run_id = "perf-persist-parallel"
        run = _make_run(run_id)
        loc = _make_location(f"{run_id}-loc", run_id)
        agent = _make_agent(f"{run_id}-agent-0", run_id, loc.id)
        db_session.add_all([run, loc, agent])
        await db_session.commit()

        import time

        with (
            patch.object(AgentRepository, "list_for_run", slow_agent_list),
            patch.object(LocationRepository, "list_for_run", slow_loc_list),
        ):
            pm = PersistenceManager(db_session)
            t0 = time.monotonic()
            await pm.persist_tick_memories(run_id, [])
            elapsed = time.monotonic() - t0

        # 串行需要 100ms+，并行应 < 80ms
        assert elapsed < 0.08, f"agents+locations 应并行查询，但耗时 {elapsed:.3f}s（预期 < 0.08s）"
        # 两个查询都应被调用
        call_types = {c[0] for c in call_log}
        assert call_types == {"agent", "location"}, f"两个查询都应被调用，实际: {call_types}"
        # 两个查询应几乎同时开始（时间差 < 30ms）
        if len(call_log) >= 2:
            sorted_log = sorted(call_log, key=lambda x: x[1])
            time_diff = sorted_log[1][1] - sorted_log[0][1]
            assert time_diff < 0.03, (
                f"两个查询应并行开始，但时间差为 {time_diff:.3f}s（预期 < 0.03s）"
            )


# ---------------------------------------------------------------------------
# 6. context.py: load_world locations+agents 并行查询
# ---------------------------------------------------------------------------


class TestLoadWorldParallelQueries:
    """ContextBuilder.load_world 中 locations 和 agents 的查询应并行执行。"""

    @pytest.mark.asyncio
    async def test_load_world_queries_parallel(self, db_session):
        """load_world 的 locations 和 agents 查询应并行，不串行。"""
        from app.sim.context import ContextBuilder
        from app.store.repositories import AgentRepository, LocationRepository

        call_log: list[tuple[str, float]] = []
        real_agent_list = AgentRepository.list_for_run
        real_loc_list = LocationRepository.list_for_run

        async def slow_agent_list(self, run_id):
            import time

            call_log.append(("agent", time.monotonic()))
            await asyncio.sleep(0.05)
            return await real_agent_list(self, run_id)

        async def slow_loc_list(self, run_id):
            import time

            call_log.append(("location", time.monotonic()))
            await asyncio.sleep(0.05)
            return await real_loc_list(self, run_id)

        run_id = "perf-load-world-parallel"
        run = _make_run(run_id)
        loc = _make_location(f"{run_id}-loc", run_id)
        agent = _make_agent(f"{run_id}-agent-0", run_id, loc.id)
        db_session.add_all([run, loc, agent])
        await db_session.commit()

        import time

        with (
            patch.object(AgentRepository, "list_for_run", slow_agent_list),
            patch.object(LocationRepository, "list_for_run", slow_loc_list),
        ):
            cb = ContextBuilder(db_session)
            t0 = time.monotonic()
            await cb.load_world(run_id, run, tick_minutes=5)
            elapsed = time.monotonic() - t0

        assert elapsed < 0.08, (
            f"load_world locations+agents 应并行查询，但耗时 {elapsed:.3f}s（预期 < 0.08s）"
        )
        call_types = {c[0] for c in call_log}
        assert call_types == {"agent", "location"}
        if len(call_log) >= 2:
            sorted_log = sorted(call_log, key=lambda x: x[1])
            time_diff = sorted_log[1][1] - sorted_log[0][1]
            assert time_diff < 0.03, (
                f"两个查询应并行开始，但时间差为 {time_diff:.3f}s（预期 < 0.03s）"
            )


# ---------------------------------------------------------------------------
# 7. coordinator.py: observe_run agents+events 并行查询
# ---------------------------------------------------------------------------


class TestObserveRunParallelQueries:
    """observe_run 中 agents 和 events 查询应并行执行。"""

    @pytest.mark.asyncio
    async def test_observe_run_queries_parallel(self, db_session):
        """observe_run 的 agents 和 events 查询应并行，不串行。"""
        from app.scenario.truman_world.coordinator import TrumanWorldCoordinator
        from app.store.repositories import AgentRepository, EventRepository

        call_log: list[tuple[str, float]] = []
        real_agent_list = AgentRepository.list_for_run
        real_event_list = EventRepository.list_for_run

        async def slow_agent_list(self, run_id):
            import time

            call_log.append(("agent", time.monotonic()))
            await asyncio.sleep(0.05)
            return await real_agent_list(self, run_id)

        async def slow_event_list(self, run_id, limit=None, **kwargs):
            import time

            call_log.append(("event", time.monotonic()))
            await asyncio.sleep(0.05)
            return await real_event_list(self, run_id, limit=limit, **kwargs)

        run_id = "perf-observe-run-parallel"
        run = _make_run(run_id)
        loc = _make_location(f"{run_id}-loc", run_id)
        agent = _make_agent(f"{run_id}-agent-0", run_id, loc.id)
        db_session.add_all([run, loc, agent])
        await db_session.commit()

        import time

        with (
            patch.object(AgentRepository, "list_for_run", slow_agent_list),
            patch.object(EventRepository, "list_for_run", slow_event_list),
        ):
            coordinator = TrumanWorldCoordinator(db_session)
            t0 = time.monotonic()
            await coordinator.observe_run(run_id)
            elapsed = time.monotonic() - t0

        assert elapsed < 0.08, (
            f"observe_run agents+events 应并行查询，但耗时 {elapsed:.3f}s（预期 < 0.08s）"
        )
        call_types = {c[0] for c in call_log}
        assert "agent" in call_types and "event" in call_types
        if len(call_log) >= 2:
            sorted_log = sorted(call_log, key=lambda x: x[1])
            time_diff = sorted_log[1][1] - sorted_log[0][1]
            assert time_diff < 0.03, (
                f"两个查询应并行开始，但时间差为 {time_diff:.3f}s（预期 < 0.03s）"
            )


# ---------------------------------------------------------------------------
# 8. persistence.py: persist_tick_relationships 双向 upsert 正确性
# ---------------------------------------------------------------------------


class TestPersistRelationshipsCorrectness:
    """注： upsert_interaction 内部包含 session.commit()，
    同一 session 并发 commit 会导致 SQLAlchemy IllegalStateChangeError。
    因此该优化不适合并行，保d为串行。
    此测试验证双向 upsert 均被执行且数据正确。
    """

    @pytest.mark.asyncio
    async def test_bidirectional_upsert_both_executed(self, db_session):
        """对话事件的 actor→target 和 target→actor 两次 upsert 均被执行。"""
        from app.sim.persistence import PersistenceManager
        from app.store.repositories import RelationshipRepository

        upsert_calls: list[tuple[str, str]] = []
        real_upsert = RelationshipRepository.upsert_interaction

        async def tracking_upsert(self, run_id, agent_id, other_agent_id, **kwargs):
            upsert_calls.append((agent_id, other_agent_id))
            return await real_upsert(self, run_id, agent_id, other_agent_id, **kwargs)

        run_id = "perf-rel-correct"
        run = _make_run(run_id)
        loc = _make_location(f"{run_id}-loc", run_id)
        actor = _make_agent(f"{run_id}-actor", run_id, loc.id)
        target = _make_agent(f"{run_id}-target", run_id, loc.id)
        db_session.add_all([run, loc, actor, target])
        await db_session.commit()

        from app.store.models import Event as EventModel
        from uuid import uuid4
        from datetime import datetime, UTC

        talk_event = EventModel(
            id=str(uuid4()),
            run_id=run_id,
            tick_no=1,
            event_type="talk",
            actor_agent_id=actor.id,
            target_agent_id=target.id,
            world_time=datetime.now(UTC),
            payload={},
        )

        with patch.object(RelationshipRepository, "upsert_interaction", tracking_upsert):
            pm = PersistenceManager(db_session)
            await pm.persist_tick_relationships(run_id, [talk_event])

        assert len(upsert_calls) == 2, f"应执行两次 upsert，实际: {len(upsert_calls)}"
        # actor→target 和 target→actor 均存在
        assert (actor.id, target.id) in upsert_calls
        assert (target.id, actor.id) in upsert_calls
