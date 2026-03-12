"""Tests for connection pool functionality."""

import os
from dataclasses import dataclass

import pytest

# 绕过嵌套会话检查 - 必须在导入 SDK 之前设置
os.environ.pop("CLAUDECODE", None)

pytest.importorskip("claude_agent_sdk")

import app.cognition.claude.connection_pool as connection_pool_module
from app.cognition.claude.connection_pool import (
    AgentConnectionPool,
    PooledClient,
    close_connection_pool,
    get_connection_pool,
)
from app.agent.system_prompt import build_system_prompt
from app.infra.settings import Settings


@dataclass
class FakeClient:
    options: object
    connect_calls: int = 0
    disconnect_calls: int = 0

    async def connect(self) -> None:
        self.connect_calls += 1

    async def disconnect(self) -> None:
        self.disconnect_calls += 1


@pytest.fixture(autouse=True)
async def reset_global_pool():
    await close_connection_pool()
    yield
    await close_connection_pool()


@pytest.fixture
def fake_client_factory(monkeypatch: pytest.MonkeyPatch):
    created_clients: list[FakeClient] = []

    def factory(*, options):
        client = FakeClient(options=options)
        created_clients.append(client)
        return client

    monkeypatch.setattr(connection_pool_module, "ClaudeSDKClient", factory)
    return created_clients


@pytest.fixture
def pool() -> AgentConnectionPool:
    settings = Settings(
        project_root="/tmp/trumanworld-test",
        anthropic_api_key="test-key",
        anthropic_base_url="https://example.invalid",
        agent_model="fake-model",
        agent_budget_usd=2.5,
    )
    return AgentConnectionPool(settings, max_connections=2, idle_timeout_seconds=10)


def _pooled(
    agent_id: str, client: FakeClient, *, last_used: float, in_use: bool = False
) -> PooledClient:
    return PooledClient(
        agent_id=agent_id,
        client=client,  # type: ignore[arg-type]
        options=client.options,  # type: ignore[arg-type]
        last_used=last_used,
        in_use=in_use,
    )


def test_build_base_options_includes_system_prompt_and_env(pool):
    options = pool._build_base_options()

    assert options.system_prompt == build_system_prompt()
    assert options.max_budget_usd == 2.5
    assert options.model == "fake-model"
    assert options.cwd == "/tmp/trumanworld-test"
    assert options.env["ANTHROPIC_API_KEY"] == "test-key"
    assert options.env["ANTHROPIC_BASE_URL"] == "https://example.invalid"


@pytest.mark.asyncio
async def test_warmup_creates_clients_and_marks_them_idle(pool, fake_client_factory):
    warmed = await pool.warmup(["agent-a", "agent-b"])

    assert warmed == 2
    assert pool.size == 2
    assert pool.active_count == 0
    assert pool.is_warmed_up("agent-a")
    assert all(client.connect_calls == 1 for client in fake_client_factory)
    assert not pool._pool["agent-a"].in_use


@pytest.mark.asyncio
async def test_acquire_reuses_existing_idle_client(pool, fake_client_factory):
    await pool.warmup(["agent-a"])

    client = await pool.acquire("agent-a")

    assert client is fake_client_factory[0]
    assert pool.active_count == 1
    assert fake_client_factory[0].connect_calls == 1


@pytest.mark.asyncio
async def test_release_tracks_session_and_resets_error_count(pool, fake_client_factory):
    client = await pool.acquire("agent-a")

    await pool.release("agent-a", had_error=True)
    assert pool._pool["agent-a"].error_count == 1

    await pool.release("agent-a", had_error=False, session_id="session-123")

    assert pool._pool["agent-a"].in_use is False
    assert pool._pool["agent-a"].error_count == 0
    assert pool.get_session_id("agent-a") == "session-123"
    assert client is fake_client_factory[0]


@pytest.mark.asyncio
async def test_acquire_reconnects_after_too_many_errors(pool, fake_client_factory):
    client = await pool.acquire("agent-a")
    await pool.release("agent-a", had_error=True)
    await pool.release("agent-a", had_error=True)
    await pool.release("agent-a", had_error=True)

    replacement = await pool.acquire("agent-a")

    assert replacement is not client
    assert client.disconnect_calls == 1
    assert len(fake_client_factory) == 2
    assert pool._pool["agent-a"].error_count == 0


@pytest.mark.asyncio
async def test_acquire_evicts_lru_idle_client_when_pool_is_full(pool, fake_client_factory):
    first = FakeClient(options=object())
    second = FakeClient(options=object())
    pool._pool = {
        "agent-old": _pooled("agent-old", first, last_used=1.0),
        "agent-new": _pooled("agent-new", second, last_used=5.0, in_use=True),
    }

    acquired = await pool.acquire("agent-extra")

    assert acquired is fake_client_factory[0]
    assert "agent-old" not in pool._pool
    assert "agent-extra" in pool._pool
    assert first.disconnect_calls == 1
    assert second.disconnect_calls == 0


@pytest.mark.asyncio
async def test_cleanup_idle_removes_only_expired_idle_clients(pool):
    stale = FakeClient(options=object())
    fresh = FakeClient(options=object())
    active = FakeClient(options=object())
    pool._pool = {
        "stale": _pooled("stale", stale, last_used=1.0),
        "fresh": _pooled("fresh", fresh, last_used=95.0),
        "active": _pooled("active", active, last_used=1.0, in_use=True),
    }

    original_time = connection_pool_module.time.time
    connection_pool_module.time.time = lambda: 100.0
    try:
        cleaned = await pool.cleanup_idle()
    finally:
        connection_pool_module.time.time = original_time

    assert cleaned == 1
    assert "stale" not in pool._pool
    assert "fresh" in pool._pool
    assert "active" in pool._pool
    assert stale.disconnect_calls == 1


@pytest.mark.asyncio
async def test_cleanup_run_removes_only_matching_run_connections(pool):
    run_client = FakeClient(options=object())
    other_client = FakeClient(options=object())
    pool._pool = {
        "run-1:agent-a": _pooled("run-1:agent-a", run_client, last_used=1.0),
        "run-2:agent-b": _pooled("run-2:agent-b", other_client, last_used=1.0),
    }

    cleaned = await pool.cleanup_run("run-1")

    assert cleaned == 1
    assert "run-1:agent-a" not in pool._pool
    assert "run-2:agent-b" in pool._pool
    assert run_client.disconnect_calls == 1
    assert other_client.disconnect_calls == 0


@pytest.mark.asyncio
async def test_close_all_marks_pool_closed_and_disconnects_clients(pool):
    first = FakeClient(options=object())
    second = FakeClient(options=object())
    pool._pool = {
        "agent-a": _pooled("agent-a", first, last_used=1.0),
        "agent-b": _pooled("agent-b", second, last_used=2.0),
    }

    await pool.close_all()

    assert pool.size == 0
    assert pool._closed is True
    assert first.disconnect_calls == 1
    assert second.disconnect_calls == 1

    with pytest.raises(RuntimeError, match="Connection pool is closed"):
        await pool.acquire("agent-c")


@pytest.mark.asyncio
async def test_get_connection_pool_returns_singleton():
    first = await get_connection_pool()
    second = await get_connection_pool()

    assert first is second
    assert isinstance(first, AgentConnectionPool)
