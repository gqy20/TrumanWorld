from __future__ import annotations

from app.infra.metrics import (
    REGISTRY,
    observe_director_decision,
    observe_director_directive,
    observe_langgraph_retry,
    observe_llm_records,
)
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


def test_director_business_metrics_track_outcomes_and_response_lag() -> None:
    decision_labels = {"outcome": "repaired_test"}
    directive_labels = {"outcome": "acknowledged_test", "mode": "priority"}
    before_decisions = (
        REGISTRY.get_sample_value("trumanworld_director_decision_total", decision_labels) or 0
    )
    before_directives = (
        REGISTRY.get_sample_value("trumanworld_director_directive_total", directive_labels) or 0
    )

    observe_director_decision(outcome="repaired_test")
    observe_director_directive(outcome="acknowledged_test", mode="priority", response_ticks=2)

    assert (
        REGISTRY.get_sample_value("trumanworld_director_decision_total", decision_labels)
        == before_decisions + 1
    )
    assert (
        REGISTRY.get_sample_value("trumanworld_director_directive_total", directive_labels)
        == before_directives + 1
    )
