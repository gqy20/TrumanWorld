from __future__ import annotations

from app.sim.llm_call_collector import LlmCallCollector


def test_llm_call_collector_reads_langchain_standard_cache_token_fields() -> None:
    collector = LlmCallCollector()
    callback = collector.build_callback(run_id="run-1", db_agent_id="agent-1", tick_no=12)

    callback(
        agent_id="alice",
        task_type="reactor",
        usage={
            "input_tokens": 120,
            "output_tokens": 30,
            "input_token_details": {
                "cache_read": 45,
                "cache_creation": 15,
            },
        },
        total_cost_usd=0.0,
        duration_ms=1234,
    )

    assert len(collector.records) == 1
    record = collector.records[0]
    assert record.input_tokens == 120
    assert record.output_tokens == 30
    assert record.cache_read_tokens == 45
    assert record.cache_creation_tokens == 15


def test_llm_call_collector_keeps_legacy_cache_token_field_compatibility() -> None:
    collector = LlmCallCollector()
    callback = collector.build_callback(run_id="run-1", db_agent_id="agent-1", tick_no=12)

    callback(
        agent_id="alice",
        task_type="planner",
        usage={
            "input_tokens": 80,
            "output_tokens": 12,
            "cache_read_input_tokens": 7,
            "cache_creation_input_tokens": 3,
        },
        total_cost_usd=0.0,
        duration_ms=456,
    )

    assert len(collector.records) == 1
    record = collector.records[0]
    assert record.input_tokens == 80
    assert record.output_tokens == 12
    assert record.cache_read_tokens == 7
    assert record.cache_creation_tokens == 3
