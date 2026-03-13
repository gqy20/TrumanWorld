from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from app.sim.action_resolver import ActionIntent
from app.sim.world import WorldState


@dataclass
class ConversationSession:
    id: str
    location_id: str
    participant_ids: list[str]
    active_speaker_id: str
    turn_order: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ConversationAssignment:
    agent_id: str
    conversation_id: str | None
    role: str
    reason: str


class ConversationScheduler:
    """Build minimal conversation sessions from talk intents.

    This first version preserves the current one-to-one talk semantics while
    moving reservation logic into an explicit scheduler that can later grow
    into small-group / group conversation assignment.
    """

    def schedule(
        self,
        intents: list[ActionIntent],
        world: WorldState,
    ) -> tuple[list[ConversationSession], dict[str, ConversationAssignment]]:
        sessions: list[ConversationSession] = []
        assignments: dict[str, ConversationAssignment] = {}
        occupied_agents: set[str] = set()
        session_by_id: dict[str, ConversationSession] = {}
        session_by_participant: dict[str, str] = {}

        for intent in intents:
            if intent.action_type != "talk":
                continue

            actor = world.get_agent(intent.agent_id)
            target_id = intent.target_agent_id
            target = world.get_agent(target_id) if target_id else None
            if actor is None or target is None:
                continue
            if actor.location_id != target.location_id:
                continue
            if actor.id in occupied_agents:
                if actor.id not in assignments:
                    assignments[actor.id] = ConversationAssignment(
                        agent_id=actor.id,
                        conversation_id=None,
                        role="none",
                        reason="participant_busy",
                    )
                continue

            target_session_id = session_by_participant.get(target.id)
            if target_session_id is not None:
                session = session_by_id[target_session_id]
                if actor.id not in session.participant_ids:
                    session.participant_ids.append(actor.id)
                    session.turn_order.append(actor.id)
                    occupied_agents.add(actor.id)
                    session_by_participant[actor.id] = session.id
                assignments[actor.id] = ConversationAssignment(
                    agent_id=actor.id,
                    conversation_id=session.id,
                    role="listener",
                    reason="conversation_joiner",
                )
                continue

            if target.id in occupied_agents:
                if actor.id not in assignments:
                    assignments[actor.id] = ConversationAssignment(
                        agent_id=actor.id,
                        conversation_id=None,
                        role="none",
                        reason="participant_busy",
                    )
                continue

            session = ConversationSession(
                id=str(uuid4()),
                location_id=actor.location_id,
                participant_ids=[actor.id, target.id],
                active_speaker_id=actor.id,
                turn_order=[actor.id, target.id],
            )
            sessions.append(session)
            session_by_id[session.id] = session
            occupied_agents.add(actor.id)
            occupied_agents.add(target.id)
            session_by_participant[actor.id] = session.id
            session_by_participant[target.id] = session.id
            assignments[actor.id] = ConversationAssignment(
                agent_id=actor.id,
                conversation_id=session.id,
                role="speaker",
                reason="talk_initiator",
            )
            assignments[target.id] = ConversationAssignment(
                agent_id=target.id,
                conversation_id=session.id,
                role="listener",
                reason="talk_target",
            )

        return sessions, assignments
