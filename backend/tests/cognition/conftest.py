import pytest
from langgraph.types import RetryPolicy

from app.cognition.langgraph.agent_backend import LangGraphAgentBackend


@pytest.fixture(autouse=True)
def disable_langgraph_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep retry semantics without making unit tests wait for production backoff."""

    def build_retry_policy(_backend: LangGraphAgentBackend) -> RetryPolicy:
        def retry_on(exc: Exception) -> bool:
            return isinstance(exc, RuntimeError)

        return RetryPolicy(
            initial_interval=0.0,
            backoff_factor=1.0,
            max_interval=0.0,
            max_attempts=2,
            jitter=False,
            retry_on=retry_on,
        )

    monkeypatch.setattr(LangGraphAgentBackend, "_build_model_retry_policy", build_retry_policy)
