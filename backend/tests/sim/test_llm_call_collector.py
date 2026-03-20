from __future__ import annotations

from app.sim.llm_call_collector import LlmCallCollector


def test_llm_call_collector_reads_langchain_standard_cache_token_fields() -> None:
    collector = LlmCallCollector()
    callback = collector.build_callback(
        run_id="run-1",
        db_agent_id="agent-1",
        tick_no=12,
        provider="openai",
        model="qwen-test",
    )

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
            "output_token_details": {
                "reasoning": 18,
            },
        },
        total_cost_usd=0.0,
        duration_ms=1234,
    )

    assert len(collector.records) == 1
    record = collector.records[0]
    assert record.provider == "openai"
    assert record.model == "qwen-test"
    assert record.input_tokens == 120
    assert record.output_tokens == 30
    assert record.reasoning_tokens == 18
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


def test_llm_call_collector_reads_openai_reasoning_token_fields() -> None:
    collector = LlmCallCollector()
    callback = collector.build_callback(run_id="run-1", db_agent_id="agent-1", tick_no=12)

    callback(
        agent_id="alice",
        task_type="reactor",
        usage={
            "input_tokens": 90,
            "output_tokens": 40,
            "completion_tokens_details": {
                "reasoning_tokens": 22,
            },
        },
        total_cost_usd=0.0,
        duration_ms=789,
    )

    assert len(collector.records) == 1
    assert collector.records[0].reasoning_tokens == 22


def test_llm_call_collector_reads_dashscope_cache_token_fields() -> None:
    collector = LlmCallCollector()
    callback = collector.build_callback(run_id="run-1", db_agent_id="agent-1", tick_no=12)

    callback(
        agent_id="alice",
        task_type="reactor",
        usage={
            "input_tokens": 90,
            "output_tokens": 40,
            "prompt_tokens_details": {
                "cached_tokens": 33,
            },
            "cache_creation": 11,
        },
        total_cost_usd=0.0,
        duration_ms=789,
    )

    assert len(collector.records) == 1
    assert collector.records[0].cache_read_tokens == 33
    assert collector.records[0].cache_creation_tokens == 11
