from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from app.agent.config_loader import AgentConfig
from app.agent.connection_pool import AgentConnectionPool
from app.agent.context_builder import ContextBuilder
from app.agent.providers import (
    AgentDecisionProvider,
    ClaudeSDKDecisionProvider,
    HeuristicDecisionProvider,
)
from app.agent.prompt_loader import PromptLoader
from app.agent.registry import AgentRegistry
from app.infra.logging import get_logger
from app.infra.settings import get_settings
from app.sim.action_resolver import ActionIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.agent.memory_cache import MemoryCache

logger = get_logger(__name__)


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
    """Facade over Claude Agent SDK for TrumanWorld agents."""

    def __init__(
        self,
        registry: AgentRegistry,
        context_builder: ContextBuilder | None = None,
        prompt_loader: PromptLoader | None = None,
        decision_provider: AgentDecisionProvider | None = None,
        connection_pool: AgentConnectionPool | None = None,
    ) -> None:
        self.registry = registry
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_loader = prompt_loader or PromptLoader()
        self._connection_pool = connection_pool
        self._allowed_actions = ["move", "talk", "work", "rest"]
        self.decision_provider = decision_provider or self._build_default_provider()

    def configure_allowed_actions(self, allowed_actions: list[str]) -> None:
        self._allowed_actions = list(allowed_actions)

    def _build_default_provider(self) -> AgentDecisionProvider:
        settings = get_settings()
        if settings.agent_provider == "claude":
            return ClaudeSDKDecisionProvider(settings, connection_pool=self._connection_pool)
        return HeuristicDecisionProvider()

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
        decision = await self.decision_provider.decide(invocation, runtime_ctx=runtime_ctx)
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
        return await self._run_free_text_llm(agent_id, "planner", prompt, runtime_ctx=runtime_ctx)

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
        return await self._run_free_text_llm(agent_id, "reflector", prompt, runtime_ctx=runtime_ctx)

    async def _run_free_text_llm(
        self,
        agent_id: str,
        task: str,
        prompt: str,
        runtime_ctx: "RuntimeContext | None" = None,
    ) -> dict | None:
        """Call the LLM with the given prompt and extract JSON from the response."""
        settings = get_settings()
        if settings.agent_provider != "claude":
            logger.debug(f"Skipping {task} for {agent_id}: provider is not claude")
            return None
        if shutil.which("claude") is None:
            logger.warning(f"Skipping {task} for {agent_id}: claude CLI not available")
            return None

        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        env: dict[str, str] = {}
        if settings.anthropic_api_key:
            env["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.anthropic_base_url:
            env["ANTHROPIC_BASE_URL"] = settings.anthropic_base_url

        from app.agent.system_prompt import build_system_prompt

        options = ClaudeAgentOptions(
            max_turns=4,
            max_budget_usd=0.05,
            model=settings.agent_model,
            cwd=str(settings.project_root),
            env=env,
            system_prompt=build_system_prompt(),
        )

        full_prompt = f"{prompt}\n\n重要：只返回 JSON，不要有任何其他文字。"

        result_text: str | None = None
        gen = None
        try:
            gen = query(prompt=full_prompt, options=options)
            async for message in gen:
                if isinstance(message, ResultMessage):
                    if message.is_error:
                        logger.warning(f"{task} LLM error for {agent_id}: {message.result}")
                        return None
                    # Record token usage if callback is provided
                    if runtime_ctx and runtime_ctx.on_llm_call:
                        runtime_ctx.on_llm_call(
                            agent_id=agent_id,
                            task_type=task,
                            usage=message.usage,
                            total_cost_usd=message.total_cost_usd,
                            duration_ms=message.duration_ms,
                        )
                    result_text = message.result
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"{task} LLM call failed for {agent_id}: {exc}")
            return None
        finally:
            if gen is not None:
                try:
                    await gen.aclose()
                except RuntimeError:
                    pass

        if not result_text:
            return None

        parsed = PromptLoader.extract_json_from_text(result_text)
        if parsed is None:
            logger.warning(f"{task} could not parse JSON for {agent_id}: {result_text[:200]}")
        return parsed
