from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.sim.action_resolver import ActionIntent, ActionResolver, ActionResult
from app.sim.conversation_scheduler import ConversationAssignment, ConversationScheduler, ConversationSession
from app.sim.world import WorldState


@dataclass
class TickResult:
    tick_no: int
    world_time: str
    tick_delta: int
    accepted: list[ActionResult]
    rejected: list[ActionResult]


class SimulationRunner:
    """Coordinates simulation ticks for a run."""

    def __init__(self, world: WorldState, resolver: ActionResolver | None = None) -> None:
        self.world = world
        self.resolver = resolver or ActionResolver()
        self.conversation_scheduler = ConversationScheduler()
        self.tick_no = 0

    def tick(self, intents: Iterable[ActionIntent]) -> TickResult:
        accepted: list[ActionResult] = []
        rejected: list[ActionResult] = []

        intent_list = list(intents)
        self.resolver.reset_tick()
        sessions, assignments = self.conversation_scheduler.schedule(intent_list, self.world)
        participants_by_conversation_id = {
            session.id: list(session.participant_ids) for session in sessions
        }
        conversation_assignments = {
            assignment.agent_id: {
                "role": assignment.role,
                "conversation_id": assignment.conversation_id,
                "participant_ids": participants_by_conversation_id.get(assignment.conversation_id, []),
            }
            for assignment in assignments.values()
        }
        self.resolver.prefill_conversation_assignments(conversation_assignments)
        for intent in intent_list:
            result = self.resolver.resolve(self.world, intent)
            if result.accepted:
                accepted.append(result)
            else:
                rejected.append(result)
        accepted.extend(self._build_listen_results(sessions, assignments))

        advanced = self.world.advance_tick()
        world_time = advanced.current_time.isoformat()
        self.tick_no += advanced.tick_delta
        return TickResult(
            tick_no=self.tick_no,
            world_time=world_time,
            tick_delta=advanced.tick_delta,
            accepted=accepted,
            rejected=rejected,
        )

    def _build_listen_results(
        self,
        sessions: list[ConversationSession],
        assignments: dict[str, ConversationAssignment],
    ) -> list[ActionResult]:
        session_by_id = {session.id: session for session in sessions}
        listen_results: list[ActionResult] = []

        for assignment in assignments.values():
            if assignment.role != "listener" or assignment.conversation_id is None:
                continue

            session = session_by_id.get(assignment.conversation_id)
            if session is None:
                continue

            listen_results.append(
                ActionResult(
                    accepted=True,
                    action_type="listen",
                    reason="accepted",
                    event_payload={
                        "agent_id": assignment.agent_id,
                        "target_agent_id": session.active_speaker_id,
                        "location_id": session.location_id,
                        "conversation_id": session.id,
                        "conversation_role": "listener",
                        "conversation_event_type": "listen",
                        "speaker_agent_id": session.active_speaker_id,
                        "participant_ids": list(session.participant_ids),
                    },
                )
            )

        return listen_results
