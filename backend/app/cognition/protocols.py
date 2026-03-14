"""Protocol definitions for cognition layer type safety.

This module defines protocols and type aliases to replace Any types
in the cognition layer, improving type checking and IDE support.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class LLMCallRecord(BaseModel):
    """Record of an LLM API call for tracking and observability."""

    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    latency_ms: float | None = None
    error: str | None = None


# Type alias for LLM call callback
# Receives the call record and can be used for logging, metrics, or caching
LLMCallCallback = Callable[[LLMCallRecord], Awaitable[None]] | None


@runtime_checkable
class MemoryCacheProtocol(Protocol):
    """Protocol for memory cache implementations.

    Defines the minimal interface required for memory caching
    in the cognition layer.
    """

    async def get(self, key: str) -> str | None:
        """Retrieve cached value by key."""
        ...

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Store value with optional TTL."""
        ...

    async def delete(self, key: str) -> None:
        """Remove cached value."""
        ...


@runtime_checkable
class ChatModelProtocol(Protocol):
    """Protocol for chat model implementations.

    This protocol matches the interface used by langchain_core.language_models.chat_models.
    Using a protocol instead of importing BaseChatModel directly avoids tight coupling.
    """

    @property
    def model_name(self) -> str:
        """Return the model name/identifier."""
        ...

    async def ainvoke(self, input: list, **kwargs) -> object:
        """Asynchronously invoke the model."""
        ...


@runtime_checkable
class StructuredModelProtocol(Protocol):
    """Protocol for models that support structured output."""

    def with_structured_output(self, schema: type[BaseModel]) -> StructuredModelProtocol:
        """Return a model wrapper that outputs structured data."""
        ...

    async def ainvoke(self, input: list, **kwargs) -> BaseModel:
        """Asynchronously invoke with structured output."""
        ...


# Director intervention result type
class DirectorIntervention(BaseModel):
    """Structured result from director decision making."""

    action: str  # "inject_event", "adjust_schedule", "none"
    target_agent_id: str | None = None
    event_type: str | None = None
    payload: dict[str, object] | None = None
    reasoning: str | None = None
