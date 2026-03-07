"""Tests for SDK session persistence and continuity.

This module contains tests that verify the Claude SDK session functionality,
including session ID handling, resumption, and connection pool integration.
"""

import pytest

import app.agent.providers as provider_module
from app.agent.providers import ClaudeSDKDecisionProvider
from app.agent.runtime import RuntimeInvocation
from app.infra.settings import get_settings


# ============================================================
# Session Persistence Tests - 验证 SDK session 功能
# ============================================================


@pytest.mark.asyncio
async def test_sdk_returns_session_id_in_result_message(monkeypatch: pytest.MonkeyPatch):
    """验证 SDK ResultMessage 中包含 session_id 字段。

    这是 session 持久化的前提条件。
    """
    monkeypatch.setenv("TRUMANWORLD_AGENT_PROVIDER", "claude")
    get_settings.cache_clear()
    monkeypatch.setattr(provider_module.shutil, "which", lambda _: "/usr/bin/claude")

    captured_session_id: str | None = None

    async def fake_query(*args, **kwargs):
        nonlocal captured_session_id
        msg = provider_module.ResultMessage(
            subtype="result",
            duration_ms=100,
            duration_api_ms=50,
            is_error=False,
            num_turns=1,
            session_id="test-session-abc123",
            result='{"action_type":"rest"}',
        )
        captured_session_id = msg.session_id
        yield msg

    monkeypatch.setattr(provider_module, "query", fake_query)

    provider = ClaudeSDKDecisionProvider(get_settings())
    invocation = RuntimeInvocation(
        agent_id="alice",
        task="reactor",
        prompt="test",
        context={},
        max_turns=1,
        max_budget_usd=0.1,
    )

    result = await provider.decide(invocation)
    assert result.action_type == "rest"
    assert captured_session_id == "test-session-abc123"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_runtime_invocation_can_carry_session_id():
    """验证 RuntimeInvocation 可以携带 session_id。

    这是 session 传递的基础设施。
    """
    invocation = RuntimeInvocation(
        agent_id="alice",
        task="reactor",
        prompt="test",
        context={},
        max_turns=1,
        max_budget_usd=0.1,
        session_id="previous-session-xyz789",  # 如果支持的话
    )

    # 验证 session_id 能被正确存储
    assert invocation.session_id == "previous-session-xyz789"


@pytest.mark.asyncio
async def test_claude_provider_passes_resume_option_when_session_provided(
    monkeypatch: pytest.MonkeyPatch,
):
    """验证当提供 session_id 时，SDK 选项中包含 resume 参数。

    这是 session 恢复的核心逻辑。
    """
    monkeypatch.setenv("TRUMANWORLD_AGENT_PROVIDER", "claude")
    get_settings.cache_clear()
    monkeypatch.setattr(provider_module.shutil, "which", lambda _: "/usr/bin/claude")

    captured_options = None

    async def fake_query(*args, **kwargs):
        nonlocal captured_options
        captured_options = kwargs.get("options") or (args[0] if args else None)
        yield provider_module.ResultMessage(
            subtype="result",
            duration_ms=100,
            duration_api_ms=50,
            is_error=False,
            num_turns=1,
            session_id="resumed-session-id",
            result='{"action_type":"rest"}',
        )

    monkeypatch.setattr(provider_module, "query", fake_query)

    provider = ClaudeSDKDecisionProvider(get_settings())

    # 使用带有 session_id 的 invocation
    invocation = RuntimeInvocation(
        agent_id="alice",
        task="reactor",
        prompt="test",
        context={},
        max_turns=1,
        max_budget_usd=0.1,
        session_id="previous-session-to-resume",
    )

    result = await provider.decide(invocation)
    assert result.action_type == "rest"

    # 验证 resume 参数被正确传递
    assert captured_options is not None
    assert captured_options.resume == "previous-session-to-resume"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_claude_provider_no_resume_when_no_session(monkeypatch: pytest.MonkeyPatch):
    """验证当没有 session_id 时，SDK 选项中不包含 resume 参数。

    确保首次调用时不会错误地设置 resume。
    """
    monkeypatch.setenv("TRUMANWORLD_AGENT_PROVIDER", "claude")
    get_settings.cache_clear()
    monkeypatch.setattr(provider_module.shutil, "which", lambda _: "/usr/bin/claude")

    captured_options = None

    async def fake_query(*args, **kwargs):
        nonlocal captured_options
        captured_options = kwargs.get("options") or (args[0] if args else None)
        yield provider_module.ResultMessage(
            subtype="result",
            duration_ms=100,
            duration_api_ms=50,
            is_error=False,
            num_turns=1,
            session_id="new-session-id",
            result='{"action_type":"rest"}',
        )

    monkeypatch.setattr(provider_module, "query", fake_query)

    provider = ClaudeSDKDecisionProvider(get_settings())

    # 没有 session_id 的 invocation（首次调用）
    invocation = RuntimeInvocation(
        agent_id="alice",
        task="reactor",
        prompt="test",
        context={},
        max_turns=1,
        max_budget_usd=0.1,
        # 不设置 session_id
    )

    result = await provider.decide(invocation)
    assert result.action_type == "rest"

    # 验证 resume 参数为 None 或未设置
    assert captured_options is not None
    assert captured_options.resume is None

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_session_continuity_across_multiple_ticks(monkeypatch: pytest.MonkeyPatch):
    """验证跨多个 tick 的 session 连续性。

    模拟场景：
    1. Tick 1: 首次调用，获得 session_id
    2. Tick 2: 使用 resume 恢复 session
    3. 验证 agent 能"记住"之前的对话
    """
    monkeypatch.setenv("TRUMANWORLD_AGENT_PROVIDER", "claude")
    get_settings.cache_clear()
    monkeypatch.setattr(provider_module.shutil, "which", lambda _: "/usr/bin/claude")

    call_count = 0
    captured_session_ids: list[str | None] = []
    captured_resume_options: list[str | None] = []

    async def fake_query(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        options = kwargs.get("options") or (args[0] if args else None)

        # 记录每次调用的 resume 参数
        captured_resume_options.append(options.resume if options else None)

        # 返回不同的 session_id 来模拟新 session
        session_id = f"session-tick-{call_count}"
        captured_session_ids.append(session_id)

        yield provider_module.ResultMessage(
            subtype="result",
            duration_ms=100,
            duration_api_ms=50,
            is_error=False,
            num_turns=1,
            session_id=session_id,
            result='{"action_type":"rest"}',
        )

    monkeypatch.setattr(provider_module, "query", fake_query)

    provider = ClaudeSDKDecisionProvider(get_settings())

    # Tick 1: 首次调用
    invocation1 = RuntimeInvocation(
        agent_id="alice",
        task="reactor",
        prompt="Tick 1: 你刚起床",
        context={},
        max_turns=1,
        max_budget_usd=0.1,
    )
    result1 = await provider.decide(invocation1)
    assert result1.action_type == "rest"

    # Tick 2: 使用 Tick 1 的 session 恢复
    session_from_tick1 = captured_session_ids[0]
    invocation2 = RuntimeInvocation(
        agent_id="alice",
        task="reactor",
        prompt="Tick 2: 现在是上午",
        context={},
        max_turns=1,
        max_budget_usd=0.1,
        session_id=session_from_tick1,
    )
    result2 = await provider.decide(invocation2)
    assert result2.action_type == "rest"

    # 验证
    assert call_count == 2
    assert captured_resume_options[0] is None  # Tick 1 无 resume
    assert captured_resume_options[1] == session_from_tick1  # Tick 2 resume Tick 1 的 session

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_provider_auto_resumes_from_pool_session(monkeypatch: pytest.MonkeyPatch):
    """验证 _build_sdk_options 自动从连接池获取 session_id 并恢复。

    直接测试 _build_sdk_options 方法，验证它能从连接池获取 session_id。
    """
    from app.agent.connection_pool import AgentConnectionPool, PooledClient

    monkeypatch.setenv("TRUMANWORLD_AGENT_PROVIDER", "claude")
    get_settings.cache_clear()

    # 创建连接池并设置 session_id
    settings = get_settings()
    pool = AgentConnectionPool(settings)
    pool._pool["alice"] = PooledClient(
        agent_id="alice",
        client=None,
        options=None,
        last_used=0,
        in_use=False,
        error_count=0,
        session_id="saved-session-xyz",
    )

    provider = ClaudeSDKDecisionProvider(settings, connection_pool=pool)

    # 创建不含 session_id 的 invocation
    invocation = RuntimeInvocation(
        agent_id="alice",
        task="reactor",
        prompt="test",
        context={},
        max_turns=1,
        max_budget_usd=0.1,
        # 不指定 session_id
    )

    # 直接测试 _build_sdk_options
    options = provider._build_sdk_options(invocation)

    # 验证 session_id 被自动获取
    assert options.resume == "saved-session-xyz"

    get_settings.cache_clear()
