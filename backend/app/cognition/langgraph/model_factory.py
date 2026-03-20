from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING, Any

from app.infra.logging import get_logger
from app.infra.settings import Settings

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

logger = get_logger(__name__)

try:
    import langchain_anthropic as _langchain_anthropic  # type: ignore[import-not-found]
except ModuleNotFoundError:
    _langchain_anthropic = types.ModuleType("langchain_anthropic")

    class _MissingChatAnthropic:
        def __init__(self, *args, **kwargs) -> None:
            msg = "langchain_anthropic is not installed"
            raise ModuleNotFoundError(msg)

    _langchain_anthropic.ChatAnthropic = _MissingChatAnthropic
    sys.modules["langchain_anthropic"] = _langchain_anthropic

try:
    import langchain_openai as _langchain_openai  # type: ignore[import-not-found]
except ModuleNotFoundError:
    _langchain_openai = types.ModuleType("langchain_openai")

    class _MissingChatOpenAI:
        def __init__(self, *args, **kwargs) -> None:
            msg = "langchain_openai is not installed"
            raise ModuleNotFoundError(msg)

    _langchain_openai.ChatOpenAI = _MissingChatOpenAI
    sys.modules["langchain_openai"] = _langchain_openai


def build_langgraph_chat_model(
    settings: Settings,
    *,
    model_name: str | None = None,
) -> BaseChatModel | None:
    provider = settings.llm_provider
    resolved_model_name = model_name or settings.llm_model
    api_key = settings.llm_api_key
    if not resolved_model_name or not api_key:
        return None

    model_kwargs: dict[str, Any] = {
        "model": resolved_model_name,
        "api_key": api_key,
        "temperature": 0,
    }
    if settings.llm_base_url:
        model_kwargs["base_url"] = settings.llm_base_url
    if provider == "openai":
        extra_body: dict[str, Any] = {}
        if settings.llm_enable_thinking is not None:
            extra_body["enable_thinking"] = settings.llm_enable_thinking
        if settings.llm_thinking_budget is not None:
            extra_body["thinking_budget"] = settings.llm_thinking_budget
        if extra_body:
            model_kwargs["extra_body"] = extra_body
        if settings.llm_session_cache_enabled:
            model_kwargs["default_headers"] = {
                "x-dashscope-session-cache": "enable",
            }

    try:
        if provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(**model_kwargs)

        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(**model_kwargs)
    except ModuleNotFoundError:
        logger.warning(
            "%s is unavailable; LangGraph backend will use fallback mode",
            ("langchain_openai" if provider == "openai" else "langchain_anthropic"),
        )
        return None
