"""TDD: ClaudeSDKDecisionProvider 重试机制

重试契约：
- 默认最多重试 2 次（共 3 次尝试）
- 可重试异常：RuntimeError、ValueError（LLM 内容/解析错误）
- 不可重试：CancelledError、cancel scope 错误（SDK 已知问题，静默处理）
- 每次失败记录 warning，耗尽后抛出最后一次异常
"""

from __future__ import annotations

import pytest
from app.agent.runtime import RuntimeInvocation
import app.cognition.claude.decision_provider as provider_module
from app.cognition.claude.decision_provider import ClaudeSDKDecisionProvider
from app.infra.settings import get_settings


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_invocation() -> RuntimeInvocation:
    return RuntimeInvocation(
        agent_id="alice",
        task="reactor",
        prompt="What should Alice do?",
        context={},
        max_turns=2,
        max_budget_usd=0.1,
    )


def _make_result_message(result: str, is_error: bool = False):
    return provider_module.ResultMessage(
        subtype="result",
        duration_ms=1,
        duration_api_ms=1,
        is_error=is_error,
        num_turns=1,
        session_id="session-retry-test",
        result=result,
    )


def _make_provider(monkeypatch) -> ClaudeSDKDecisionProvider:
    monkeypatch.setenv("TRUMANWORLD_AGENT_BACKEND", "claude_sdk")
    get_settings.cache_clear()
    monkeypatch.setattr(provider_module.shutil, "which", lambda _: "/usr/bin/claude")
    return ClaudeSDKDecisionProvider(get_settings())


# ---------------------------------------------------------------------------
# 红灯测试1: 首次失败，第2次成功 → 返回决策（当前无重试，会直接抛出）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt(monkeypatch):
    """首次 LLM 调用失败（RuntimeError），第2次成功 → 最终返回正确决策。"""
    provider = _make_provider(monkeypatch)
    invocation = _make_invocation()

    call_count = 0

    async def fake_query(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # 第1次：返回错误
            yield _make_result_message("internal error", is_error=True)
        else:
            # 第2次：返回合法决策
            yield _make_result_message('{"action_type": "rest"}')

    monkeypatch.setattr(provider_module, "query", fake_query)

    result = await provider.decide(invocation)

    assert result.action_type == "rest"
    assert call_count == 2  # 确认触发了重试


# ---------------------------------------------------------------------------
# 红灯测试2: 全部3次均失败 → 抛出最后一次异常
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_exhausted_raises_last_error(monkeypatch):
    """3次全部失败 → 抛出最后一次 RuntimeError，而非静默返回。"""
    provider = _make_provider(monkeypatch)
    invocation = _make_invocation()

    call_count = 0

    async def fake_query(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield _make_result_message(f"error attempt {call_count}", is_error=True)

    monkeypatch.setattr(provider_module, "query", fake_query)

    with pytest.raises(RuntimeError, match="error attempt 3"):
        await provider.decide(invocation)

    assert call_count == 3  # 尝试了3次


# ---------------------------------------------------------------------------
# 红灯测试3: JSON 解析失败也触发重试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_on_json_parse_failure(monkeypatch):
    """LLM 返回非法 JSON → ValueError → 触发重试，第2次返回合法 JSON。"""
    provider = _make_provider(monkeypatch)
    invocation = _make_invocation()

    call_count = 0

    async def fake_query(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield _make_result_message("this is not json at all!!!")
        else:
            yield _make_result_message('{"action_type": "work"}')

    monkeypatch.setattr(provider_module, "query", fake_query)

    result = await provider.decide(invocation)

    assert result.action_type == "work"
    assert call_count == 2


# ---------------------------------------------------------------------------
# 红灯测试4: CancelledError 不触发重试，直接静默返回 rest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancelled_error_not_retried(monkeypatch):
    """CancelledError 属于正常取消，不应触发重试，静默返回 rest。"""
    import asyncio

    provider = _make_provider(monkeypatch)
    invocation = _make_invocation()

    call_count = 0

    async def fake_query(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise asyncio.CancelledError
        if False:
            yield None

    monkeypatch.setattr(provider_module, "query", fake_query)

    result = await provider.decide(invocation)

    assert result.action_type == "rest"
    assert call_count == 1  # 只调用了1次，没有重试


# ---------------------------------------------------------------------------
# 红灯测试5: max_retries=0 时直接失败，不重试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_max_retries_zero_raises_immediately(monkeypatch):
    """max_retries=0 时不重试，直接抛出异常。"""
    provider = _make_provider(monkeypatch)
    provider.max_retries = 0
    invocation = _make_invocation()

    call_count = 0

    async def fake_query(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield _make_result_message("fail immediately", is_error=True)

    monkeypatch.setattr(provider_module, "query", fake_query)

    with pytest.raises(RuntimeError):
        await provider.decide(invocation)

    assert call_count == 1  # 只调用1次
