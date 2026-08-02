from __future__ import annotations

import inspect
from dataclasses import dataclass
from time import perf_counter
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from app.infra.logging import get_logger
from app.infra.metrics import observe_langgraph_node, observe_langgraph_run

logger = get_logger(__name__)


@dataclass(frozen=True)
class LangGraphTrace:
    trace_id: str
    graph_run_id: UUID
    graph_name: str
    simulation_run_id: str | None
    tick_no: int | None
    agent_id: str | None
    task_type: str
    provider: str | None
    model: str | None

    def fields(self) -> dict[str, Any]:
        return {
            "backend": "langgraph",
            "trace_id": self.trace_id,
            "graph_run_id": str(self.graph_run_id),
            "graph_name": self.graph_name,
            "simulation_run_id": self.simulation_run_id,
            "tick_no": self.tick_no,
            "agent_id": self.agent_id,
            "task_type": self.task_type,
            "provider": self.provider,
            "model": self.model,
        }

    def runnable_config(self, callback: BaseCallbackHandler | None = None) -> dict[str, Any]:
        config: dict[str, Any] = {
            "run_name": self.graph_name,
            "run_id": self.graph_run_id,
            "tags": ["langgraph", self.task_type],
            "metadata": self.fields(),
        }
        if callback is not None:
            config["callbacks"] = [callback]
        return config


class LangGraphLoggingCallback(BaseCallbackHandler):
    """Bridge LangGraph lifecycle callbacks into the application log schema."""

    run_inline = True

    def __init__(self, trace: LangGraphTrace) -> None:
        self.trace = trace
        self._started_at: dict[UUID, float] = {}
        self._nodes: dict[UUID, str] = {}

    @property
    def ignore_llm(self) -> bool:
        # LLM calls are recorded at the model boundary where normalized usage and
        # domain-specific status are available.
        return True

    def on_chain_start(
        self,
        serialized: dict[str, Any] | None,
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del serialized, inputs, tags, kwargs
        if run_id == self.trace.graph_run_id and parent_run_id is None:
            self._started_at[run_id] = perf_counter()
            logger.debug(
                "LangGraph run started",
                extra={"event": "langgraph_run_started", **self.trace.fields()},
            )
            return

        node = (metadata or {}).get("langgraph_node")
        if parent_run_id != self.trace.graph_run_id or not isinstance(node, str):
            return
        self._started_at[run_id] = perf_counter()
        self._nodes[run_id] = node
        logger.debug(
            "LangGraph node started",
            extra={
                "event": "langgraph_node_started",
                **self.trace.fields(),
                "graph_node": node,
                "graph_task_run_id": str(run_id),
            },
        )

    def on_chain_end(
        self,
        outputs: dict[str, Any] | Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        del outputs, parent_run_id, kwargs
        if run_id == self.trace.graph_run_id:
            duration = self._duration(run_id)
            observe_langgraph_run(graph=self.trace.graph_name, status="success")
            logger.debug(
                "LangGraph run completed",
                extra={
                    "event": "langgraph_run_completed",
                    **self.trace.fields(),
                    "status": "success",
                    "duration_ms": round(duration * 1000, 2),
                },
            )
            return
        self._finish_node(run_id, status="success")

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        del parent_run_id, kwargs
        if run_id == self.trace.graph_run_id:
            duration = self._duration(run_id)
            observe_langgraph_run(graph=self.trace.graph_name, status="error")
            logger.error(
                "LangGraph run failed",
                extra={
                    "event": "langgraph_run_failed",
                    **self.trace.fields(),
                    "status": "error",
                    "duration_ms": round(duration * 1000, 2),
                    "exception_type": type(error).__name__,
                },
            )
            return
        self._finish_node(run_id, status="error", error=error)

    def _finish_node(
        self,
        run_id: UUID,
        *,
        status: str,
        error: BaseException | None = None,
    ) -> None:
        node = self._nodes.pop(run_id, None)
        if node is None:
            return
        duration = self._duration(run_id)
        observe_langgraph_node(
            graph=self.trace.graph_name,
            node=node,
            status=status,
            duration_seconds=duration,
        )
        fields = {
            "event": "langgraph_node_completed" if status == "success" else "langgraph_node_failed",
            **self.trace.fields(),
            "graph_node": node,
            "graph_task_run_id": str(run_id),
            "status": status,
            "duration_ms": round(duration * 1000, 2),
        }
        if error is not None:
            fields["exception_type"] = type(error).__name__
        logger.log(
            10 if status == "success" else 30,
            "LangGraph node completed" if status == "success" else "LangGraph node failed",
            extra=fields,
        )

    def _duration(self, run_id: UUID) -> float:
        started_at = self._started_at.pop(run_id, None)
        return perf_counter() - started_at if started_at is not None else 0.0


def notify_llm_call(callback, **fields: Any) -> None:
    """Call extended telemetry callbacks without breaking legacy five-argument hooks."""
    if callback is None:
        return
    try:
        parameters = inspect.signature(callback).parameters.values()
    except (TypeError, ValueError):
        callback(**fields)
        return
    accepts_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters
    )
    if accepts_kwargs:
        callback(**fields)
        return
    accepted_names = {parameter.name for parameter in parameters}
    callback(**{key: value for key, value in fields.items() if key in accepted_names})
