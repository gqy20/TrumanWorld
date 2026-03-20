from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from app.store.models import LlmCall


class LlmCallCollector:
    def __init__(self) -> None:
        self.records: list[LlmCall] = []

    @staticmethod
    def _extract_reasoning_tokens(usage: dict | None) -> int:
        usage = usage or {}
        output_token_details = usage.get("output_token_details")
        if isinstance(output_token_details, dict):
            return int(output_token_details.get("reasoning", 0) or 0)
        completion_token_details = usage.get("completion_tokens_details")
        if isinstance(completion_token_details, dict):
            return int(completion_token_details.get("reasoning_tokens", 0) or 0)
        return int(usage.get("reasoning_tokens", 0) or 0)

    @staticmethod
    def _extract_cache_tokens(usage: dict | None) -> tuple[int, int]:
        usage = usage or {}
        input_token_details = usage.get("input_token_details")
        if isinstance(input_token_details, dict):
            cache_read = int(input_token_details.get("cache_read", 0) or 0)
            cache_creation = int(input_token_details.get("cache_creation", 0) or 0)
            if cache_read or cache_creation:
                return (cache_read, cache_creation)
        prompt_token_details = usage.get("prompt_tokens_details")
        if isinstance(prompt_token_details, dict):
            cache_read = int(prompt_token_details.get("cached_tokens", 0) or 0)
            if cache_read:
                return (
                    cache_read,
                    int(usage.get("cache_creation", 0) or 0),
                )
        return (
            int(usage.get("cache_read_input_tokens", 0) or 0),
            int(
                usage.get("cache_creation_input_tokens", 0)
                or usage.get("cache_creation", 0)
                or 0
            ),
        )

    def build_callback(
        self,
        *,
        run_id: str,
        db_agent_id: str,
        tick_no: int,
        provider: str | None = None,
        model: str | None = None,
    ) -> Callable[..., None]:
        def on_llm_call(
            agent_id: str,
            task_type: str,
            usage: dict | None,
            total_cost_usd: float | None,
            duration_ms: int,
        ) -> None:
            cache_read_tokens, cache_creation_tokens = self._extract_cache_tokens(usage)
            reasoning_tokens = self._extract_reasoning_tokens(usage)
            self.records.append(
                LlmCall(
                    id=str(uuid4()),
                    run_id=run_id,
                    agent_id=db_agent_id,
                    task_type=task_type,
                    provider=provider,
                    model=model,
                    tick_no=tick_no,
                    input_tokens=int((usage or {}).get("input_tokens", 0)),
                    output_tokens=int((usage or {}).get("output_tokens", 0)),
                    reasoning_tokens=reasoning_tokens,
                    cache_read_tokens=cache_read_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                    total_cost_usd=total_cost_usd,
                    duration_ms=duration_ms or 0,
                )
            )

        return on_llm_call
