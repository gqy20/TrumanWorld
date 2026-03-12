from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from app.agent.config_loader import AgentConfig
from app.agent.context_builder import ContextBuilder
from app.agent.prompt_loader import PromptLoader
from app.agent.registry import AgentRegistry
from app.cognition.claude.connection_pool import AgentConnectionPool
from app.cognition.heuristic.agent_backend import HeuristicAgentBackend
from app.cognition.interfaces import AgentCognitionBackend
from app.cognition.registry import CognitionRegistry
from app.cognition.types import (
    AgentActionInvocation,
    BackendExecutionContext,
    PlanningInvocation,
    ReflectionInvocation,
)
from app.infra.logging import get_logger
from app.infra.settings import get_settings
from app.sim.action_resolver import ActionIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.agent.memory_cache import MemoryCache

logger = get_logger(__name__)

__all__ = ["AgentRuntime", "RuntimeContext", "RuntimeInvocation", "shutil"]


class _ProviderBackedAgentBackend:
    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def decide_action(
        self,
        invocation: AgentActionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ):
        adapted_invocation = type(
            "ProviderInvocation",
            (),
            {
                "agent_id": invocation.agent_id,
                "task": "reactor",
                "prompt": invocation.prompt,
                "context": invocation.context,
                "max_turns": invocation.max_turns,
                "max_budget_usd": invocation.max_budget_usd,
                "allowed_actions": list(invocation.allowed_actions),
                "run_id": runtime_ctx.run_id if runtime_ctx else None,
                "session_id": None,
            },
        )()
        decision = await self._provider.decide(adapted_invocation, runtime_ctx=runtime_ctx)
        return decision

    async def plan_day(
        self,
        invocation: PlanningInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> dict | None:
        return None

    async def reflect_day(
        self,
        invocation: ReflectionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> dict | None:
        return None


class RuntimeInvocation(BaseModel):
    """Serializable invocation parameters."""

    agent_id: str
    task: str
    prompt: str
    context: dict[str, Any]
    max_turns: int
    max_budget_usd: float
    allowed_actions: list[str] = []
    session_id: str | None = None  # 用于恢复 SDK session
    run_id: str | None = None  # 用于连接池隔离多个 run


@dataclass
class RuntimeContext:
    """Runtime context holding non-serializable resources.

    This class holds resources that cannot be serialized (like database engines)
    and should be passed alongside RuntimeInvocation.
    """

    db_engine: "AsyncEngine | None" = None
    run_id: str | None = None
    enable_memory_tools: bool = True
    # LLM 调用回调：(agent_id, task_type, usage, total_cost_usd, duration_ms) -> None
    on_llm_call: Callable[..., None] | None = field(default=None)
    # 预加载的记忆缓存，用于 in-process MCP 工具（避免 greenlet 冲突）
    memory_cache: "MemoryCache | None" = field(default=None)


class AgentRuntime:
    """Runtime facade over framework-neutral cognition backends."""

    def __init__(
        self,
        registry: AgentRegistry,
        context_builder: ContextBuilder | None = None,
        prompt_loader: PromptLoader | None = None,
        backend: AgentCognitionBackend | None = None,
        decision_provider: Any | None = None,
        connection_pool: AgentConnectionPool | None = None,
        cognition_registry: CognitionRegistry | None = None,
    ) -> None:
        self.registry = registry
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_loader = prompt_loader or PromptLoader()
        self._connection_pool = connection_pool
        self._cognition_registry = cognition_registry
        self._allowed_actions = ["move", "talk", "work", "rest"]
        self._decision_provider: Any | None = None
        if decision_provider is not None:
            self.decision_provider = decision_provider
        else:
            self.backend = backend or self._build_default_backend()
            self._decision_provider = getattr(self.backend, "_provider", None)

    def configure_allowed_actions(self, allowed_actions: list[str]) -> None:
        self._allowed_actions = list(allowed_actions)

    @property
    def decision_provider(self) -> Any | None:
        return self._decision_provider

    @decision_provider.setter
    def decision_provider(self, provider: Any | None) -> None:
        self._decision_provider = provider
        self.backend = (
            _ProviderBackedAgentBackend(provider)
            if provider is not None
            else HeuristicAgentBackend()
        )

    def _build_default_backend(self) -> AgentCognitionBackend:
        settings = get_settings()
        cognition_registry = self._cognition_registry or CognitionRegistry(settings)
        if self._connection_pool is not None:
            cognition_registry._claude_pool = self._connection_pool
        return cognition_registry.build_agent_backend()

    def _load_agent(self, agent_id: str) -> AgentConfig:
        config = self.registry.get_config(agent_id)
        if config is None:
            msg = f"Agent config not found for '{agent_id}'"
            raise ValueError(msg)
        return config

    def prepare_planner(
        self,
        agent_id: str,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
    ) -> RuntimeInvocation:
        config = self._load_agent(agent_id)
        context = self.context_builder.build_planner_context(config, world=world, memory=memory)
        base_prompt = self.registry.get_prompt(agent_id)
        prompt = self.prompt_loader.render(base_prompt or "", context=context)
        return RuntimeInvocation(
            agent_id=agent_id,
            task="planner",
            prompt=prompt or "",
            context=context,
            max_turns=config.model.max_turns,
            max_budget_usd=config.model.max_budget_usd,
        )

    def prepare_reactor(
        self,
        agent_id: str,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
        event: dict[str, Any] | None = None,
        recent_events: list[dict[str, Any]] | None = None,
    ) -> RuntimeInvocation:
        config = self._load_agent(agent_id)
        context = self.context_builder.build_reactor_context(
            config,
            world=world,
            memory=memory,
            event=event,
            recent_events=recent_events,
        )
        base_prompt = self.registry.get_prompt(agent_id)
        allowed_actions = list(self._allowed_actions)
        prompt = self.prompt_loader.render_decision_prompt(
            base_prompt or "",
            context=context,
            allowed_actions=allowed_actions,
        )
        return RuntimeInvocation(
            agent_id=agent_id,
            task="reactor",
            prompt=prompt or "",
            context=context,
            max_turns=config.model.max_turns,
            max_budget_usd=config.model.max_budget_usd,
            allowed_actions=allowed_actions,
        )

    def prepare_reflector(
        self,
        agent_id: str,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
        daily_summary: dict[str, Any] | None = None,
    ) -> RuntimeInvocation:
        config = self._load_agent(agent_id)
        context = self.context_builder.build_reflector_context(
            config,
            world=world,
            memory=memory,
            daily_summary=daily_summary,
        )
        base_prompt = self.registry.get_prompt(agent_id)
        prompt = self.prompt_loader.render(base_prompt or "", context=context)
        return RuntimeInvocation(
            agent_id=agent_id,
            task="reflector",
            prompt=prompt or "",
            context=context,
            max_turns=config.model.max_turns,
            max_budget_usd=config.model.max_budget_usd,
        )

    async def decide_intent(
        self,
        invocation: RuntimeInvocation,
        runtime_ctx: RuntimeContext | None = None,
    ) -> ActionIntent:
        backend_invocation = AgentActionInvocation(
            agent_id=invocation.agent_id,
            prompt=invocation.prompt,
            context=invocation.context,
            max_turns=invocation.max_turns,
            max_budget_usd=invocation.max_budget_usd,
            allowed_actions=list(invocation.allowed_actions),
        )
        backend_runtime_ctx = (
            BackendExecutionContext(
                run_id=runtime_ctx.run_id,
                enable_memory_tools=runtime_ctx.enable_memory_tools,
                on_llm_call=runtime_ctx.on_llm_call,
                memory_cache=runtime_ctx.memory_cache,
            )
            if runtime_ctx is not None
            else None
        )
        decision = await self.backend.decide_action(backend_invocation, runtime_ctx=backend_runtime_ctx)
        payload = dict(decision.payload)
        if decision.message:
            payload["message"] = decision.message
        # No default message injection — LLM must provide message content for talk actions
        return ActionIntent(
            agent_id=invocation.agent_id,
            action_type=decision.action_type,
            target_location_id=decision.target_location_id,
            target_agent_id=decision.target_agent_id,
            payload=payload,
        )

    async def react(
        self,
        agent_id: str,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
        event: dict[str, Any] | None = None,
        recent_events: list[dict[str, Any]] | None = None,
        runtime_ctx: RuntimeContext | None = None,
    ) -> ActionIntent:
        invocation = self.prepare_reactor(
            agent_id, world=world, memory=memory, event=event, recent_events=recent_events
        )
        # Set run_id from runtime_ctx for connection pool isolation
        if runtime_ctx and runtime_ctx.run_id and not invocation.run_id:
            invocation = invocation.model_copy(update={"run_id": runtime_ctx.run_id})
        return await self.decide_intent(invocation, runtime_ctx=runtime_ctx)

    async def run_planner(
        self,
        agent_id: str,
        agent_name: str,
        world_context: dict[str, Any],
        recent_memories: list[dict[str, Any]] | None = None,
        runtime_ctx: "RuntimeContext | None" = None,
    ) -> dict | None:
        """Run the daily planning LLM call and return parsed plan dict.

        Returns a dict with keys {morning, daytime, evening, intention} or None on failure.
        """
        context: dict[str, Any] = {**world_context}
        if recent_memories:
            context["recent_memories"] = recent_memories
        prompt = self.prompt_loader.render_planner_prompt(
            agent_name=agent_name,
            context=context,
        )
        backend_runtime_ctx = (
            BackendExecutionContext(
                run_id=runtime_ctx.run_id,
                enable_memory_tools=runtime_ctx.enable_memory_tools,
                on_llm_call=runtime_ctx.on_llm_call,
                memory_cache=runtime_ctx.memory_cache,
            )
            if runtime_ctx is not None
            else None
        )
        return await self.backend.plan_day(
            PlanningInvocation(
                agent_id=agent_id,
                agent_name=agent_name,
                prompt=prompt,
                context=context,
            ),
            runtime_ctx=backend_runtime_ctx,
        )

    async def run_reflector(
        self,
        agent_id: str,
        agent_name: str,
        world_context: dict[str, Any],
        daily_events: list[dict[str, Any]] | None = None,
        runtime_ctx: "RuntimeContext | None" = None,
    ) -> dict | None:
        """Run the daily reflection LLM call and return parsed reflection dict.

        Returns a dict with keys {reflection, mood, key_person, tomorrow_intention} or None on failure.
        """
        context: dict[str, Any] = {**world_context}
        prompt = self.prompt_loader.render_reflector_prompt(
            agent_name=agent_name,
            context=context,
            daily_events=daily_events or [],
        )
        backend_runtime_ctx = (
            BackendExecutionContext(
                run_id=runtime_ctx.run_id,
                enable_memory_tools=runtime_ctx.enable_memory_tools,
                on_llm_call=runtime_ctx.on_llm_call,
                memory_cache=runtime_ctx.memory_cache,
            )
            if runtime_ctx is not None
            else None
        )
        return await self.backend.reflect_day(
            ReflectionInvocation(
                agent_id=agent_id,
                agent_name=agent_name,
                prompt=prompt,
                context=context,
            ),
            runtime_ctx=backend_runtime_ctx,
        )
