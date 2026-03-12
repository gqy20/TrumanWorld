import app.cognition.claude.decision_provider as _decision_provider
from app.cognition.claude.decision_provider import (
    AgentDecisionProvider,
    DEFAULT_TALK_MESSAGE,
    HeuristicDecisionHook,
    HeuristicDecisionProvider,
    build_default_talk_message,
)
from app.cognition.claude.decision_utils import RuntimeDecision

shutil = _decision_provider.shutil
query = _decision_provider.query
ResultMessage = _decision_provider.ResultMessage
ClaudeAgentOptions = _decision_provider.ClaudeAgentOptions


class ClaudeSDKDecisionProvider(_decision_provider.ClaudeSDKDecisionProvider):
    """Compatibility wrapper that preserves the old module patch surface."""

    async def decide(self, invocation, runtime_ctx=None):
        _decision_provider.query = query
        _decision_provider.shutil = shutil
        return await super().decide(invocation, runtime_ctx=runtime_ctx)

__all__ = [
    "AgentDecisionProvider",
    "ClaudeAgentOptions",
    "ClaudeSDKDecisionProvider",
    "DEFAULT_TALK_MESSAGE",
    "HeuristicDecisionHook",
    "HeuristicDecisionProvider",
    "ResultMessage",
    "RuntimeDecision",
    "build_default_talk_message",
    "query",
    "shutil",
]
