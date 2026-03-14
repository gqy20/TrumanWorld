from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from app.store.models import LlmCall


class LlmCallCollector:
    def __init__(self) -> None:
        self.records: list[LlmCall] = []

    @staticmethod
    def _extract_cache_tokens(usage: dict | None) -> tuple[int, int]:
        usage = usage or {}
        input_token_details = usage.get("input_token_details")
        if isinstance(input_token_details, dict):
            return (
                int(input_token_details.get("cache_read", 0) or 0),
                int(input_token_details.get("cache_creation", 0) or 0),
            )
        return (
            int(usage.get("cache_read_input_tokens", 0) or 0),
            int(usage.get("cache_creation_input_tokens", 0) or 0),
        )

    def build_callback(
        self,
        *,
        run_id: str,
        db_agent_id: str,
        tick_no: int,
    ) -> Callable[..., None]:
        def on_llm_call(
            agent_id: str,
            task_type: str,
            usage: dict | None,
            total_cost_usd: float | None,
            duration_ms: int,
        ) -> None:
            cache_read_tokens, cache_creation_tokens = self._extract_cache_tokens(usage)
            self.records.append(
                LlmCall(
                    id=str(uuid4()),
                    run_id=run_id,
                    agent_id=db_agent_id,
                    task_type=task_type,
                    tick_no=tick_no,
                    input_tokens=int((usage or {}).get("input_tokens", 0)),
                    output_tokens=int((usage or {}).get("output_tokens", 0)),
                    cache_read_tokens=cache_read_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                    total_cost_usd=total_cost_usd,
                    duration_ms=duration_ms or 0,
                )
            )

        return on_llm_call
