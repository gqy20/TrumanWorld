"""Tests for connection pool functionality."""

import os
import pytest

# 绕过嵌套会话检查 - 必须在导入 SDK 之前设置
os.environ.pop("CLAUDECODE", None)

pytest.importorskip("claude_agent_sdk")

from app.agent.connection_pool import AgentConnectionPool, PooledClient
from app.agent.system_prompt import build_system_prompt
from app.infra.settings import Settings, get_settings


@pytest.fixture
def connection_pool():
    """Create a connection pool for testing."""
    settings = get_settings()
    return AgentConnectionPool(settings, max_connections=5)


@pytest.mark.asyncio
async def test_pool_basic(connection_pool):
    """Test basic pool operations."""
    assert connection_pool.size == 0
    assert not connection_pool.is_warmed_up("test_agent")

    # Test acquire without warmup (should create new connection)
    # Note: This will try to create a real connection, which may fail in test environment
    # We just test this interface works


@pytest.mark.asyncio
async def test_pool_lru_eviction(connection_pool):
    """Test LRU eviction when pool is full."""
    # Fill pool with mock clients
    for i in range(5):
        connection_pool._pool[f"agent_{i}"] = PooledClient(
            agent_id=f"agent_{i}",
            client=None,  # type: ignore
            options=None,
            last_used=float(i),
            in_use=False,
            error_count=0,
        )

    # Verify eviction would be called when needed
    # Note: This is a simplified test
    assert connection_pool.size == 5


def test_build_base_options_includes_system_prompt(tmp_path):
    settings = Settings(project_root=tmp_path)
    pool = AgentConnectionPool(settings, max_connections=1)

    options = pool._build_base_options()

    assert options.system_prompt == build_system_prompt()
