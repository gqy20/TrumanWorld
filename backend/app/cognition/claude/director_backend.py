from __future__ import annotations

from app.cognition.types import DirectorDecisionInvocation
from app.director.agent import DirectorAgent


class ClaudeSdkDirectorBackend:
    def __init__(self) -> None:
        self._agent = DirectorAgent()

    def is_enabled(self) -> bool:
        return self._agent.is_enabled()

    def should_decide(self, tick_no: int) -> bool:
        return self._agent.should_decide(tick_no)

    async def propose_intervention(self, invocation: DirectorDecisionInvocation):
        return await self._agent.decide(invocation.context, invocation.recent_goals)
