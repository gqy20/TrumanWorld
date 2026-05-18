from __future__ import annotations

from typing import TYPE_CHECKING

from app.cognition.claude.director_agent import DirectorAgent
from app.cognition.errors import UpstreamApiUnavailableError, is_upstream_api_unavailable_error
from app.cognition.langgraph.model_factory import build_langgraph_chat_model
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
        if not self._enabled:
            return None
        if self._text_model is None:
            msg = "LangGraph director model is not configured or unavailable"
            raise UpstreamApiUnavailableError(msg)

        context = invocation.context
        support_agents = self._agent._select_support_agents(context)
        if not support_agents or context.assessment.subject_agent_id is None:
            return None

        prompt = self._agent._build_decision_prompt(
            context, support_agents, invocation.recent_goals
        )
        full_prompt = f"{prompt}\n\n重要：你必须只返回一个有效的 JSON 对象，不要有其他任何文本。"

        try:
            response = await self._text_model.ainvoke(full_prompt)
        except Exception as exc:
            if is_upstream_api_unavailable_error(exc):
                raise UpstreamApiUnavailableError(str(exc)) from exc
            raise

        return self._agent._parse_response(
            self._extract_text_content(response),
            context,
            support_agents,
        )

    def _build_default_model(self) -> BaseChatModel | None:
        model_name = self._settings.director_agent_model or self._settings.llm_model
        return build_langgraph_chat_model(self._settings, model_name=model_name)

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
