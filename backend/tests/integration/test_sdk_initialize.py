"""Live diagnostic test for Claude SDK client initialization.

This isolates SDK/client startup from the full simulation tick flow so
`Control request timeout: initialize` can be reproduced directly.

Run with:
    cd backend
    TRUMANWORLD_RUN_LIVE_SDK_TESTS=1 pytest tests/integration/test_sdk_initialize.py -q -s
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest

# The Claude SDK rejects nested Claude Code sessions by default.
# This test is a live diagnostic, so clear the marker before importing SDK.
os.environ.pop("CLAUDECODE", None)

pytest.importorskip("claude_agent_sdk")

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from app.cognition.claude.sdk_options import build_sdk_options
from app.infra.settings import get_settings


LIVE_SDK_TESTS_ENABLED = os.getenv("TRUMANWORLD_RUN_LIVE_SDK_TESTS") == "1"
LIVE_SDK_SKIP_REASON = "设置 TRUMANWORLD_RUN_LIVE_SDK_TESTS=1 后才运行真实 SDK 初始化测试"
INITIALIZE_TIMEOUT_SECONDS = 20


def build_live_options() -> ClaudeAgentOptions:
    settings = get_settings()
    return build_sdk_options(
        settings,
        max_turns=1,
        max_budget_usd=0.05,
        model=settings.agent_model,
        cwd=str(settings.project_root),
        permission_mode="bypassPermissions",
    )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skipif(not LIVE_SDK_TESTS_ENABLED, reason=LIVE_SDK_SKIP_REASON)
async def test_claude_sdk_client_initialize() -> None:
    settings = get_settings()
    client = ClaudeSDKClient(options=build_live_options())
    started_at = time.perf_counter()

    try:
        await asyncio.wait_for(client.connect(), timeout=INITIALIZE_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - started_at
        pytest.fail(
            "Claude SDK initialize failed "
            f"after {elapsed:.2f}s with model={settings.agent_model!r}, "
            f"base_url={settings.anthropic_base_url!r}: {exc}"
        )
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
