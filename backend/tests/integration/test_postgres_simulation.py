from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime, RuntimeInvocation
from app.cognition.claude.decision_provider import AgentDecisionProvider
from app.cognition.claude.decision_utils import RuntimeDecision
from app.cognition.heuristic.agent_backend import HeuristicAgentBackend
from app.infra.db import Base
from app.infra.settings import get_settings
from app.sim.action_resolver import ActionIntent
from app.sim.service import SimulationService
from app.store.models import Agent, Location, SimulationRun
from app.store.repositories import EventRepository, LlmCallRepository, RunRepository


pytestmark = pytest.mark.integration


class TokenProvider(AgentDecisionProvider):
    async def decide(self, invocation: RuntimeInvocation, runtime_ctx=None):
        if runtime_ctx and runtime_ctx.on_llm_call:
            runtime_ctx.on_llm_call(
                agent_id=invocation.agent_id,
                task_type=invocation.task,
                usage={"input_tokens": 21, "output_tokens": 34, "cache_read_input_tokens": 5},
                total_cost_usd=0.02,
                duration_ms=120,
            )
        return RuntimeDecision(action_type="rest")


def _admin_url() -> str:
    configured = os.getenv("TRUMANWORLD_TEST_POSTGRES_URL")
    if configured:
        return configured
    base = make_url(get_settings().database_url)
    return base.set(database="postgres").render_as_string(hide_password=False)


@pytest_asyncio.fixture
async def postgres_session():
    db_name = f"trumanworld_it_{uuid4().hex[:8]}"
    admin_url = make_url(_admin_url())
    app_url = admin_url.set(database=db_name)
    sync_admin_url = admin_url.render_as_string(hide_password=False).replace("+psycopg", "")

    try:
        with psycopg.connect(sync_admin_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f'CREATE DATABASE "{db_name}"')
    except psycopg.Error as exc:
        pytest.skip(f"PostgreSQL not available for integration tests: {exc}")

    engine = create_async_engine(app_url.render_as_string(hide_password=False), echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            yield session, engine
    finally:
        await engine.dispose()
        with psycopg.connect(sync_admin_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
                    (db_name,),
                )
                cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')


@pytest.mark.asyncio
async def test_postgres_run_tick_persists_events_and_time(postgres_session):
    session, _engine = postgres_session
    run = SimulationRun(id="pg-run-1", name="pg", status="running", current_tick=0, tick_minutes=5)
    session.add(run)
    await session.commit()

    home = Location(id="pg-home-1", run_id=run.id, name="Home", location_type="home", capacity=2)
    park = Location(id="pg-park-1", run_id=run.id, name="Park", location_type="park", capacity=2)
    session.add_all([home, park])
    await session.commit()

    agent = Agent(
        id="pg-agent-1",
        run_id=run.id,
        name="Alice",
        occupation="resident",
        home_location_id=home.id,
        current_location_id=home.id,
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    session.add(agent)
    await session.commit()

    result = await SimulationService(session).run_tick(
        run.id,
        [ActionIntent(agent_id=agent.id, action_type="move", target_location_id=park.id)],
    )

    updated_run = await RunRepository(session).get(run.id)
    events = await EventRepository(session).list_for_run(run.id)

    assert result.tick_no == 1
    assert result.world_time == "2026-03-02T06:05:00+00:00"
    assert updated_run is not None
    assert updated_run.current_tick == 1
    assert len(events) == 1
    assert events[0].payload["to_location_id"] == park.id


@pytest.mark.asyncio
async def test_postgres_run_tick_isolated_persists_llm_calls(postgres_session, tmp_path: Path):
    session, engine = postgres_session
    run = SimulationRun(id="pg-run-2", name="pg", status="running", current_tick=0, tick_minutes=5)
    session.add(run)
    await session.commit()

    home = Location(id="pg-home-2", run_id=run.id, name="Home", location_type="home", capacity=2)
    session.add(home)
    await session.commit()

    agent = Agent(
        id="pg-agent-2",
        run_id=run.id,
        name="Alice",
        occupation="resident",
        home_location_id=home.id,
        current_location_id=home.id,
        personality={},
        profile={"agent_config_id": "alice"},
        status={},
        current_plan={},
    )
    session.add(agent)
    await session.commit()

    agent_dir = tmp_path / "alice"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "id: alice\nname: Alice\noccupation: resident\nhome: pg-home-2\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")

    runtime = AgentRuntime(
        registry=AgentRegistry(tmp_path),
        backend=HeuristicAgentBackend(TokenProvider()),
    )
    result = await SimulationService.create_for_scheduler(runtime).run_tick_isolated(run.id, engine)
    totals = await LlmCallRepository(session).get_token_totals(run.id)

    assert result.tick_no == 1
    assert totals["input_tokens"] == 21
    assert totals["output_tokens"] == 34
    assert totals["cache_read_tokens"] == 5
