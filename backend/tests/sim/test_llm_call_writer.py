from __future__ import annotations

import pytest

from app.sim.llm_call_writer import LlmCallWriter
from app.store.models import LlmCall


@pytest.mark.asyncio
async def test_llm_call_writer_treats_persistence_failures_as_best_effort():
    writer = LlmCallWriter()
    record = LlmCall(
        run_id="run-llm-best-effort",
        agent_id="agent-llm-best-effort",
        tick_no=1,
        task_type="planner",
        provider="test",
        model="test-model",
        input_tokens=1,
        output_tokens=1,
    )

    await writer.persist(
        run_id="run-llm-best-effort",
        llm_records=[record],
        engine=object(),
    )
