from __future__ import annotations

from app.cognition.types import DirectorDecisionInvocation


class HeuristicDirectorBackend:
    def is_enabled(self) -> bool:
        return False

    def should_decide(self, tick_no: int) -> bool:
        return False

    async def propose_intervention(self, invocation: DirectorDecisionInvocation) -> None:
        return None
