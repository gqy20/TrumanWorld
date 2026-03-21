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
    is_new: bool = True


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

        for conversation in world.active_conversations.values():
            if conversation.last_tick_no < max(0, world.current_tick - 1):
                continue
            session = ConversationSession(
                id=conversation.id,
                location_id=conversation.location_id,
                participant_ids=list(conversation.participant_ids),
                active_speaker_id=conversation.active_speaker_id,
                turn_order=list(conversation.participant_ids),
                is_new=False,
            )
            sessions.append(session)
            session_by_id[session.id] = session
            for participant_id in session.participant_ids:
                session_by_participant[participant_id] = session.id

        for intent in self._ordered_talk_intents(intents):
            actor = world.get_agent(intent.agent_id)
            target_id = intent.target_agent_id
            target = world.get_agent(target_id) if target_id else None
            if actor is None or target is None:
                continue
            if actor.location_id != target.location_id:
                continue
            target_session_id = session_by_participant.get(target.id)
            actor_session_id = session_by_participant.get(actor.id)
            if actor.id in occupied_agents:
                existing_assignment = assignments.get(actor.id)
                if (
                    existing_assignment is not None
                    and existing_assignment.role == "listener"
                    and existing_assignment.conversation_id is not None
                    and existing_assignment.conversation_id == target_session_id
                ):
                    assignments[actor.id] = ConversationAssignment(
                        agent_id=actor.id,
                        conversation_id=existing_assignment.conversation_id,
                        role="listener",
                        reason="reciprocal_talk_listener",
                    )
                    continue
                if actor.id not in assignments:
                    assignments[actor.id] = ConversationAssignment(
                        agent_id=actor.id,
                        conversation_id=None,
                        role="none",
                        reason="participant_busy",
                    )
                continue

            if (
                actor_session_id is not None
                and actor_session_id == target_session_id
                and actor_session_id in session_by_id
            ):
                session = session_by_id[actor_session_id]
                session.active_speaker_id = actor.id
                occupied_agents.add(actor.id)
                assignments[actor.id] = ConversationAssignment(
                    agent_id=actor.id,
                    conversation_id=session.id,
                    role="speaker",
                    reason="conversation_continues",
                )
                for participant_id in session.participant_ids:
                    if participant_id == actor.id:
                        continue
                    occupied_agents.add(participant_id)
                    assignments[participant_id] = ConversationAssignment(
                        agent_id=participant_id,
                        conversation_id=session.id,
                        role="listener",
                        reason="conversation_continuation_listener",
                    )
                continue

            if target_session_id is not None:
                session = session_by_id[target_session_id]
                # If actor is already the active speaker in this session (e.g., Lin
                # continues talking to Mei across ticks), keep them as speaker so their
                # talk intent is not wrongly rejected.
                if session.active_speaker_id == actor.id:
                    assignments[actor.id] = ConversationAssignment(
                        agent_id=actor.id,
                        conversation_id=session.id,
                        role="speaker",
                        reason="active_speaker_continues",
                    )
                else:
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

    @staticmethod
    def _ordered_talk_intents(intents: list[ActionIntent]) -> list[ActionIntent]:
        talk_intents = [intent for intent in intents if intent.action_type == "talk"]
        return sorted(
            talk_intents,
            key=lambda intent: (
                0
                if intent.payload.get("intent_source") == "pending_reply_bias"
                else 1
            ),
        )
