"""TDD: 测试 TrumanWorldCoordinator.build_director_plan 不在 read_session 中写 DB

Bug 描述:
    _build_auto_plan 在 read_session 上下文内调用 director_memory_repo.create()（写操作），
    违反了 run_tick_isolated 的三段式读写分离设计，触发 greenlet_spawn 错误。

修复目标:
    1. build_director_plan 在 read_session 中被调用时，不产生任何 DB 写入
    2. director plan 的持久化改由 run_tick_isolated Phase 3 (write_session) 负责
    3. run_tick_isolated 完成后，director_memories 表中应存在对应记录
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from app.scenario.truman_world.coordinator import TrumanWorldCoordinator
from app.scenario.truman_world.scenario import TrumanWorldScenario
from app.sim.world_loader import load_tick_data
from app.store.models import Agent, Base, DirectorMemory, Location, SimulationRun


# ---------------------------------------------------------------------------
# 辅助工具
# ---------------------------------------------------------------------------

def _make_run(run_id: str, current_tick: int = 3) -> SimulationRun:
    return SimulationRun(
        id=run_id,
        name="test-run",
        status="running",
        current_tick=current_tick,
        tick_minutes=5,
    )


def _make_location(loc_id: str, run_id: str) -> Location:
    return Location(
        id=loc_id,
        run_id=run_id,
        name="Town Square",
        location_type="plaza",
        capacity=10,
    )


def _make_cast(agent_id: str, run_id: str, loc_id: str) -> Agent:
    return Agent(
        id=agent_id,
        run_id=run_id,
        name="Meryl",
        occupation="resident",
        home_location_id=loc_id,
        current_location_id=loc_id,
        current_goal="rest",
        personality={},
        profile={"agent_config_id": "spouse", "world_role": "cast"},
        status={},
        current_plan={},
    )


def _make_truman(agent_id: str, run_id: str, loc_id: str, suspicion: float = 0.9) -> Agent:
    """高怀疑度 Truman —— 确保策略会被触发"""
    return Agent(
        id=agent_id,
        run_id=run_id,
        name="Truman",
        occupation="resident",
        home_location_id=loc_id,
        current_location_id=loc_id,
        current_goal="rest",
        personality={},
        profile={"agent_config_id": "truman", "world_role": "truman"},
        status={"suspicion_score": suspicion},
        current_plan={},
    )


# ---------------------------------------------------------------------------
# 测试 1（红灯）: build_director_plan 在 read_session 中不应写 DB
# 修复后：director_memory_repo.create() 从 _build_auto_plan 中移除，不再在此阶段写入
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_director_plan_does_not_write_db_in_read_phase(db_session):
    """TDD 红灯: build_director_plan 不能在 read_session 中产生任何 DB 写入。

    当前实现会在 _build_auto_plan 末尾调用 director_memory_repo.create()，
    此行为违反读写分离原则，会触发 greenlet 错误。
    修复后，调用 build_director_plan 不应在 director_memories 表中产生新记录。
    """
    run_id = "run-coord-read-phase"
    loc_id = f"{run_id}-loc"
    cast_id = f"{run_id}-cast"
    truman_id = f"{run_id}-truman"

    run = _make_run(run_id, current_tick=3)
    loc = _make_location(loc_id, run_id)
    cast = _make_cast(cast_id, run_id, loc_id)
    # 高怀疑度，确保策略触发，产生 plan（而非 None）
    truman = _make_truman(truman_id, run_id, loc_id, suspicion=0.9)

    db_session.add_all([run, loc, cast, truman])
    await db_session.commit()

    # 统计调用前的 director_memories 行数
    count_before = (
        await db_session.execute(
            select(func.count(DirectorMemory.id)).where(DirectorMemory.run_id == run_id)
        )
    ).scalar_one()

    coordinator = TrumanWorldCoordinator(db_session)
    agents = [cast, truman]

    # 在 "read_session" 内调用 build_director_plan（模拟 Phase 1 的调用路径）
    plan = await coordinator.build_director_plan(run_id, agents)

    # 统计调用后的 director_memories 行数
    count_after = (
        await db_session.execute(
            select(func.count(DirectorMemory.id)).where(DirectorMemory.run_id == run_id)
        )
    ).scalar_one()

    # 关键断言：高怀疑度应触发策略并返回 plan，但不应写 DB
    assert plan is not None, "高怀疑度应触发策略并返回非空 plan"
    assert count_after == count_before, (
        f"build_director_plan 在 read_session 中产生了 {count_after - count_before} 条写入，"
        "这会导致 greenlet_spawn 错误。director plan 的持久化应移至 Phase 3 (write_session)。"
    )


# ---------------------------------------------------------------------------
# 测试 2（红灯）: run_tick_isolated 完成后，plan 应被持久化
# 修复后：Phase 3 write_session 中保存 director plan
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_tick_isolated_persists_director_plan_after_tick(db_session):
    """TDD 红灯: run_tick_isolated 完成后，触发的 director plan 应被持久化到 DB。

    修复方案：
    - _build_auto_plan 只返回 plan，不写 DB
    - load_tick_data 返回的 TickData 携带 director_plan
    - run_tick_isolated Phase 3 (write_session) 负责持久化 director plan
    """
    from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionType

    from app.agent.providers import HeuristicDecisionProvider
    from app.agent.registry import AgentRegistry
    from app.agent.runtime import AgentRuntime
    from app.sim.service import SimulationService

    import tempfile
    from pathlib import Path
    import shutil

    # 为 run_tick_isolated 创建独立 engine（隔离 session）
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    run_id = "run-coord-write-phase"
    loc_id = f"{run_id}-loc"
    cast_id = f"{run_id}-cast"
    truman_id = f"{run_id}-truman"

    async with AsyncSessionType(engine, expire_on_commit=False) as setup_session:
        run = _make_run(run_id, current_tick=3)
        run.scenario_type = "truman_world"
        loc = _make_location(loc_id, run_id)
        cast = _make_cast(cast_id, run_id, loc_id)
        truman = _make_truman(truman_id, run_id, loc_id, suspicion=0.9)
        setup_session.add_all([run, loc, cast, truman])
        await setup_session.commit()

    # 创建 AgentRuntime（使用 heuristic provider，不调用外部 SDK）
    tmp_path = Path(tempfile.mkdtemp())
    try:
        registry = AgentRegistry(tmp_path)
        runtime = AgentRuntime(registry=registry, decision_provider=HeuristicDecisionProvider())
        service = SimulationService.create_for_scheduler(runtime)

        await service.run_tick_isolated(run_id, engine)

        # 验证：Phase 3 应该已将触发的 director plan 写入 director_memories
        async with AsyncSessionType(engine, expire_on_commit=False) as verify_session:
            count = (
                await verify_session.execute(
                    select(func.count(DirectorMemory.id)).where(DirectorMemory.run_id == run_id)
                )
            ).scalar_one()

        assert count >= 1, (
            "run_tick_isolated 完成后，触发的 director plan 应被持久化到 director_memories 表。"
            f"当前记录数：{count}，预期 >= 1。"
        )
    finally:
        await engine.dispose()
        shutil.rmtree(tmp_path)


# ---------------------------------------------------------------------------
# 测试 3: load_tick_data 应返回 director_plan（修复后的接口合约）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_tick_data_returns_director_plan_for_high_suspicion(db_session):
    """TDD 红灯: load_tick_data 应在返回的 TickData 中包含 director_plan。

    修复后，load_tick_data 的返回值 TickData 需要携带 director_plan 字段，
    以便 run_tick_isolated Phase 3 可以持久化它。
    当高怀疑度触发策略时，director_plan 应为非 None。
    """
    run_id = "run-tick-data-plan"
    loc_id = f"{run_id}-loc"
    cast_id = f"{run_id}-cast"
    truman_id = f"{run_id}-truman"

    run = _make_run(run_id, current_tick=3)
    loc = _make_location(loc_id, run_id)
    cast = _make_cast(cast_id, run_id, loc_id)
    truman = _make_truman(truman_id, run_id, loc_id, suspicion=0.9)

    db_session.add_all([run, loc, cast, truman])
    await db_session.commit()

    scenario = TrumanWorldScenario(db_session)
    loaded = await load_tick_data(
        session=db_session,
        run_id=run_id,
        scenario=scenario,
    )

    # 修复后，TickData 应包含 director_plan 字段
    assert hasattr(loaded, "director_plan"), (
        "TickData 应包含 director_plan 字段，以便 Phase 3 可以持久化。"
        "修复方法：在 TickData dataclass 中增加 director_plan: DirectorPlan | None 字段，"
        "并在 load_tick_data 中赋值。"
    )
    assert loaded.director_plan is not None, (
        "高怀疑度（0.9）应触发策略，director_plan 应为非 None。"
    )
