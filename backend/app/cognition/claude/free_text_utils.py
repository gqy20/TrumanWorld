from __future__ import annotations

from collections.abc import Callable
from typing import Any

from claude_agent_sdk import ResultMessage


async def run_text_query(
    *,
    prompt: str,
    options: Any,
    on_usage: Callable[[Any, float | None, int | None], None] | None = None,
) -> str:
    from claude_agent_sdk import query

    gen = None
    try:
        gen = query(prompt=prompt, options=options)
        async for message in gen:
            if isinstance(message, ResultMessage):
                if message.is_error:
                    msg = message.result or "Claude SDK call failed"
                    raise RuntimeError(msg)
                if on_usage is not None:
                    on_usage(
                        message.usage,
                        message.total_cost_usd,
                        message.duration_ms,
                    )
                if message.result:
                    return message.result
        raise RuntimeError("Claude SDK returned no result")
    finally:
        if gen is not None:
            try:
                await gen.aclose()
            except RuntimeError:
                pass
