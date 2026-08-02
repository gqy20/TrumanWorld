from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    GCCollector,
    Histogram,
    PlatformCollector,
    ProcessCollector,
    generate_latest,
)

from app.cognition.claude.connection_pool import peek_connection_pool
from app.infra.settings import get_settings
from app.sim.scheduler import get_scheduler

REGISTRY = CollectorRegistry()
ProcessCollector(registry=REGISTRY)
PlatformCollector(registry=REGISTRY)
GCCollector(registry=REGISTRY)

TICK_TOTAL = Counter(
    "trumanworld_tick_total",
    "Total number of simulation ticks executed.",
    labelnames=("mode", "status"),
    registry=REGISTRY,
)

TICK_DURATION_SECONDS = Histogram(
    "trumanworld_tick_duration_seconds",
    "Simulation tick execution duration in seconds.",
    labelnames=("mode",),
    registry=REGISTRY,
)

DATABASE_QUERIES_PER_OPERATION = Histogram(
    "trumanworld_database_queries_per_operation",
    "Number of database queries executed by one measured operation.",
    labelnames=("operation",),
    buckets=(0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144),
    registry=REGISTRY,
)

DATABASE_DURATION_SECONDS = Histogram(
    "trumanworld_database_duration_seconds",
    "Total database execution time within one measured operation.",
    labelnames=("operation",),
    registry=REGISTRY,
)

HTTP_REQUEST_TOTAL = Counter(
    "trumanworld_http_request_total",
    "Total HTTP requests handled by the API.",
    labelnames=("method", "route", "status_code"),
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "trumanworld_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    labelnames=("method", "route"),
    registry=REGISTRY,
)

ACTIVE_RUNS = Gauge(
    "trumanworld_active_runs",
    "Number of currently scheduled runs.",
    registry=REGISTRY,
)
ACTIVE_RUNS.set_function(lambda: get_scheduler().running_count())

CLAUDE_REACTOR_POOL_ENABLED = Gauge(
    "trumanworld_claude_reactor_pool_enabled",
    "Whether Claude reactor pooling is enabled in configuration (1=true, 0=false).",
    registry=REGISTRY,
)
CLAUDE_REACTOR_POOL_ENABLED.set_function(
    lambda: 1.0 if bool(getattr(get_settings(), "claude_sdk_reactor_pool_enabled", True)) else 0.0
)

CLAUDE_REACTOR_POOL_SIZE = Gauge(
    "trumanworld_claude_reactor_pool_size",
    "Current number of pooled Claude reactor clients.",
    registry=REGISTRY,
)
CLAUDE_REACTOR_POOL_SIZE.set_function(
    lambda: float(peek_connection_pool().size) if peek_connection_pool() is not None else 0.0
)

CLAUDE_REACTOR_POOL_ACTIVE = Gauge(
    "trumanworld_claude_reactor_pool_active",
    "Current number of active Claude reactor clients in use.",
    registry=REGISTRY,
)
CLAUDE_REACTOR_POOL_ACTIVE.set_function(
    lambda: (
        float(peek_connection_pool().active_count) if peek_connection_pool() is not None else 0.0
    )
)

LLM_CALL_TOTAL = Counter(
    "trumanworld_llm_call_total",
    "Total persisted LLM calls.",
    labelnames=("backend", "provider", "task_type", "status"),
    registry=REGISTRY,
)

LLM_TOKENS_TOTAL = Counter(
    "trumanworld_llm_tokens_total",
    "Total persisted LLM tokens by type.",
    labelnames=("backend", "provider", "task_type", "token_type"),
    registry=REGISTRY,
)

LLM_COST_USD_TOTAL = Counter(
    "trumanworld_llm_cost_usd_total",
    "Total persisted LLM cost in USD.",
    labelnames=("backend", "provider", "task_type"),
    registry=REGISTRY,
)

LLM_CALL_DURATION_SECONDS = Histogram(
    "trumanworld_llm_call_duration_seconds",
    "LLM call duration in seconds.",
    labelnames=("backend", "provider", "task_type", "status"),
    registry=REGISTRY,
)

LANGGRAPH_RUN_TOTAL = Counter(
    "trumanworld_langgraph_run_total",
    "Total LangGraph runs by graph and status.",
    labelnames=("graph", "status"),
    registry=REGISTRY,
)

LANGGRAPH_NODE_DURATION_SECONDS = Histogram(
    "trumanworld_langgraph_node_duration_seconds",
    "LangGraph node duration in seconds.",
    labelnames=("graph", "node", "status"),
    registry=REGISTRY,
)

LANGGRAPH_RETRY_TOTAL = Counter(
    "trumanworld_langgraph_retry_total",
    "Total LangGraph node retries.",
    labelnames=("graph", "node", "exception_type"),
    registry=REGISTRY,
)

LANGGRAPH_FALLBACK_TOTAL = Counter(
    "trumanworld_langgraph_fallback_total",
    "Total LangGraph model-path fallbacks.",
    labelnames=("task_type", "from_path", "to_path", "reason"),
    registry=REGISTRY,
)


def observe_tick(*, mode: str, status: str, duration_seconds: float) -> None:
    TICK_TOTAL.labels(mode=mode, status=status).inc()
    TICK_DURATION_SECONDS.labels(mode=mode).observe(duration_seconds)


def observe_database_operation(
    *,
    operation: str,
    query_count: int,
    duration_seconds: float,
) -> None:
    DATABASE_QUERIES_PER_OPERATION.labels(operation=operation).observe(query_count)
    DATABASE_DURATION_SECONDS.labels(operation=operation).observe(duration_seconds)


def observe_http_request(
    *, method: str, route: str, status_code: int, duration_seconds: float
) -> None:
    """Record bounded-cardinality request metrics using the route template."""
    HTTP_REQUEST_TOTAL.labels(
        method=method,
        route=route,
        status_code=str(status_code),
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, route=route).observe(duration_seconds)


def observe_llm_records(llm_records: list) -> None:
    for record in llm_records:
        labels = {
            "backend": record.backend or "unknown",
            "provider": record.provider or "unknown",
            "task_type": record.task_type,
        }
        status = record.status or "success"
        LLM_CALL_TOTAL.labels(**labels, status=status).inc()
        LLM_CALL_DURATION_SECONDS.labels(**labels, status=status).observe(
            (record.duration_ms or 0) / 1000
        )
        LLM_TOKENS_TOTAL.labels(**labels, token_type="input").inc(record.input_tokens or 0)
        LLM_TOKENS_TOTAL.labels(**labels, token_type="output").inc(record.output_tokens or 0)
        LLM_TOKENS_TOTAL.labels(**labels, token_type="cache_read").inc(
            record.cache_read_tokens or 0
        )
        LLM_TOKENS_TOTAL.labels(**labels, token_type="cache_creation").inc(
            record.cache_creation_tokens or 0
        )
        if record.total_cost_usd:
            LLM_COST_USD_TOTAL.labels(**labels).inc(record.total_cost_usd)


def observe_langgraph_run(*, graph: str, status: str) -> None:
    LANGGRAPH_RUN_TOTAL.labels(graph=graph, status=status).inc()


def observe_langgraph_node(*, graph: str, node: str, status: str, duration_seconds: float) -> None:
    LANGGRAPH_NODE_DURATION_SECONDS.labels(graph=graph, node=node, status=status).observe(
        duration_seconds
    )


def observe_langgraph_retry(*, graph: str, node: str, exception_type: str) -> None:
    LANGGRAPH_RETRY_TOTAL.labels(
        graph=graph,
        node=node,
        exception_type=exception_type,
    ).inc()


def observe_langgraph_fallback(
    *, task_type: str, from_path: str, to_path: str, reason: str
) -> None:
    LANGGRAPH_FALLBACK_TOTAL.labels(
        task_type=task_type,
        from_path=from_path,
        to_path=to_path,
        reason=reason,
    ).inc()


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
