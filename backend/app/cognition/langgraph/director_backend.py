from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.cognition.claude.director_agent import DirectorAgent
from app.cognition.protocols import ChatModelProtocol, DirectorIntervention
from app.cognition.types import DirectorDecisionInvocation
from app.infra.logging import get_logger
from app.infra.settings import Settings, get_settings

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

logger = get_logger(__name__)


class LangGraphDirectorBackend:
    """LangGraph-compatible one-shot director backend.

    The director remains a stateless text-generation task. We reuse the
    existing DirectorAgent prompt construction and response parsing so the
    LangGraph backend only swaps the underlying model transport.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        text_model: BaseChatModel | ChatModelProtocol | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._agent = DirectorAgent(self._settings)
        self._enabled = (
            self._agent._config.enabled and self._settings.director_backend == "langgraph"
        )
        self._decision_interval = self._agent._config.decision_interval
        self._text_model: BaseChatModel | ChatModelProtocol | None = (
            text_model or self._build_default_model()
        )

    def is_enabled(self) -> bool:
        return self._enabled

    def should_decide(self, tick_no: int) -> bool:
        if not self._enabled:
            return False
        return tick_no % self._decision_interval == 0

    async def propose_intervention(
        self, invocation: DirectorDecisionInvocation
    ) -> DirectorIntervention | None:
        if not self._enabled or self._text_model is None:
            return None

        context = invocation.context
        cast_agents = [
            a for a in context.agents if a.get("profile", {}).get("world_role") == "cast"
        ]
        if not cast_agents or context.assessment.truman_agent_id is None:
            return None

        prompt = self._agent._build_decision_prompt(context, cast_agents, invocation.recent_goals)
        full_prompt = f"{prompt}\n\n重要：你必须只返回一个有效的 JSON 对象，不要有其他任何文本。"

        try:
            response = await self._text_model.ainvoke(full_prompt)
        except Exception as exc:
            logger.warning(f"LangGraph director decision failed: {exc}")
            return None

        return self._agent._parse_response(
            self._extract_text_content(response),
            context,
            cast_agents,
        )

    def _build_default_model(self) -> BaseChatModel | None:
        model_name = (
            self._settings.director_agent_model
            or self._settings.langgraph_model
            or self._settings.agent_model
        )
        api_key = self._settings.langgraph_api_key
        if not model_name or not api_key:
            return None

        from langchain_anthropic import ChatAnthropic

        model_kwargs: dict[str, Any] = {
            "model": model_name,
            "api_key": api_key,
            "temperature": 0,
        }
        if self._settings.langgraph_base_url:
            model_kwargs["base_url"] = self._settings.langgraph_base_url
        return ChatAnthropic(**model_kwargs)

    def _extract_text_content(self, response: object) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                else:
                    text = getattr(item, "text", None)
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts).strip()
        return ""
