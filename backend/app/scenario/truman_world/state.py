from __future__ import annotations

from typing import TYPE_CHECKING

from app.protocol.simulation import (
    DIRECTOR_EVENT_PREFIX,
    EVENT_LISTEN,
    EVENT_MOVE,
    EVENT_REST,
    EVENT_SPEECH,
    EVENT_TALK,
    EVENT_WORK,
)
from app.scenario.runtime_config import (
    ScenarioRuntimeConfig,
    build_scenario_runtime_config,
)
from app.scenario.truman_world.types import get_world_role
from app.store.repositories import AgentRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.store.models import Event

AlertStateSemantics = ScenarioRuntimeConfig


class TrumanWorldStateUpdater:
    """Updates Truman-world specific state such as suspicion."""

    def __init__(
        self,
        session: AsyncSession,
        semantics: AlertStateSemantics | None = None,
    ) -> None:
        self.session = session
        self.agent_repo = AgentRepository(session)
        self._semantics = semantics or AlertStateSemantics()

    async def persist_truman_suspicion(self, run_id: str, events: list[Event]) -> None:
        """Legacy alias for persist_subject_alert."""
        await self.persist_subject_alert(run_id, events)

    async def persist_subject_alert(self, run_id: str, events: list[Event]) -> None:
        agents = await self.agent_repo.list_for_run(run_id)
        changed = False
        for agent in agents:
            if get_world_role(agent.profile) != self._semantics.subject_role:
                continue
            delta = self.calculate_suspicion_delta(agent.id, events)
            if delta == 0.0:
                continue
            status = dict(agent.status or {})
            current = float(status.get(self._semantics.alert_metric, 0.0))
            status[self._semantics.alert_metric] = max(0.0, min(1.0, round(current + delta, 4)))
            agent.status = status
            changed = True
        if changed:
            await self.session.commit()

    @staticmethod
    def calculate_suspicion_delta(agent_id: str, events: list[Event]) -> float:
        delta = 0.0
        for event in events:
            payload = event.payload or {}
            involved = event.actor_agent_id == agent_id or event.target_agent_id == agent_id
            if not involved and payload.get("agent_id") != agent_id:
                continue

            if event.event_type.endswith("_rejected"):
                delta += 0.12
            elif event.event_type.startswith(DIRECTOR_EVENT_PREFIX):
                delta += 0.2
            elif event.event_type in {EVENT_TALK, EVENT_SPEECH, EVENT_LISTEN}:
                delta -= 0.02
            elif event.event_type in {EVENT_REST, EVENT_WORK}:
                delta -= 0.01
            elif event.event_type == EVENT_MOVE:
                delta -= 0.005
        return delta


def build_alert_state_semantics(scenario_id: str) -> AlertStateSemantics:
    return build_scenario_runtime_config(scenario_id)
