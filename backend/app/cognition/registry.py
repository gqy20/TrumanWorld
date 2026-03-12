from __future__ import annotations

from functools import lru_cache

from app.agent.connection_pool import AgentConnectionPool, close_connection_pool, get_connection_pool
from app.cognition.claude.agent_backend import ClaudeSdkAgentBackend
from app.cognition.claude.director_backend import ClaudeSdkDirectorBackend
from app.cognition.heuristic.agent_backend import HeuristicAgentBackend
from app.cognition.heuristic.director_backend import HeuristicDirectorBackend
from app.infra.settings import Settings, get_settings
from app.scenario.types import get_agent_config_id
from app.store.repositories import AgentRepository


class CognitionRegistry:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._claude_pool: AgentConnectionPool | None = None

    def build_agent_backend(self):
        agent_backend = getattr(self._settings, "agent_backend", None)
        if agent_backend is None:
            agent_backend = (
                "claude_sdk"
                if getattr(self._settings, "agent_provider", "heuristic") == "claude"
                else "heuristic"
            )
        if agent_backend == "claude_sdk":
            return ClaudeSdkAgentBackend(self._settings, connection_pool=self._claude_pool)
        return HeuristicAgentBackend()

    def build_director_backend(self):
        director_backend = getattr(self._settings, "director_backend", None)
        if director_backend is None:
            director_backend = (
                "claude_sdk"
                if getattr(self._settings, "director_agent_enabled", False)
                else "heuristic"
            )
        if director_backend == "claude_sdk":
            return ClaudeSdkDirectorBackend()
        return HeuristicDirectorBackend()

    async def warmup_for_run(self, session, run_id: str) -> None:
        if self._settings.agent_backend != "claude_sdk":
            return
        if self._claude_pool is None:
            self._claude_pool = await get_connection_pool()

        agents = await AgentRepository(session).list_for_run(run_id)
        pool_keys = sorted(
            {f"{run_id}:{get_agent_config_id(agent.profile) or agent.id}" for agent in agents}
        )
        if pool_keys:
            await self._claude_pool.warmup(pool_keys)

    async def cleanup(self) -> None:
        await close_connection_pool()
        self._claude_pool = None

    async def cleanup_idle(self) -> None:
        if self._claude_pool is not None:
            await self._claude_pool.cleanup_idle()


@lru_cache(maxsize=1)
def get_cognition_registry() -> CognitionRegistry:
    return CognitionRegistry()
