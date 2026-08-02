from __future__ import annotations

from app.infra.metrics import REGISTRY, observe_langgraph_retry, observe_llm_records
from app.store.models import LlmCall


def test_llm_metrics_are_partitioned_by_backend_task_and_status() -> None:
    labels = {
        "backend": "langgraph",
        "provider": "test-provider",
        "task_type": "reactor",
        "status": "invalid_output",
    }
    before = REGISTRY.get_sample_value("trumanworld_llm_call_total", labels) or 0
    record = LlmCall(
        run_id="run-metrics",
        task_type="reactor",
        backend="langgraph",
        provider="test-provider",
        status="invalid_output",
        input_tokens=3,
        output_tokens=2,
        duration_ms=250,
    )

    observe_llm_records([record])

    after = REGISTRY.get_sample_value("trumanworld_llm_call_total", labels)
    assert after == before + 1


def test_langgraph_retry_metric_uses_bounded_labels() -> None:
    labels = {
        "graph": "agent_reactor_test",
        "node": "model_decide",
        "exception_type": "RuntimeError",
    }
    before = REGISTRY.get_sample_value("trumanworld_langgraph_retry_total", labels) or 0

    observe_langgraph_retry(**labels)

    after = REGISTRY.get_sample_value("trumanworld_langgraph_retry_total", labels)
    assert after == before + 1
