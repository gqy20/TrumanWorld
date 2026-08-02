from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.director.types import DirectorActorCandidate

if TYPE_CHECKING:
    from app.store.models import Agent, Event


def build_actor_candidates(
    *,
    agents: list[Agent],
    events: list[Event],
    current_tick: int,
    subject_agent_id: str | None,
) -> dict[str, DirectorActorCandidate]:
    """Build deterministic actor availability from persisted world state."""

    active_by_conversation: dict[str, tuple[int, tuple[str, ...]]] = {}
    for event in sorted(events, key=lambda item: item.tick_no):
        if event.tick_no < max(0, current_tick - 1):
            continue
        payload = event.payload or {}
        conversation_id = payload.get("conversation_id")
        if not isinstance(conversation_id, str):
            continue
        if event.event_type == "conversation_closed":
            active_by_conversation.pop(conversation_id, None)
            continue
        participants = payload.get("participant_ids")
        if not isinstance(participants, list):
            continue
        normalized = tuple(item for item in participants if isinstance(item, str))
        if len(normalized) < 2:
            continue
        active_by_conversation[conversation_id] = (event.tick_no, normalized)

    recent_participants = {
        participant_id: participants
        for _tick_no, participants in active_by_conversation.values()
        for participant_id in participants
    }

    subject = next((agent for agent in agents if agent.id == subject_agent_id), None)
    subject_location_id = subject.current_location_id if subject is not None else None
    candidates: dict[str, DirectorActorCandidate] = {}
    for agent in agents:
        participants = recent_participants.get(agent.id, ())
        movement = agent.movement or {}
        if movement:
            availability = "moving"
            eligible = False
        elif participants and subject_agent_id in participants:
            availability = "engaged_with_subject"
            eligible = True
        elif participants:
            availability = "in_conversation"
            eligible = False
        else:
            availability = "available"
            eligible = True
        candidates[agent.id] = DirectorActorCandidate(
            agent_id=agent.id,
            name=agent.name,
            profile=dict(agent.profile or {}),
            current_location_id=agent.current_location_id,
            current_goal=agent.current_goal,
            availability=availability,
            eligible=eligible,
            conversation_participant_ids=participants,
            same_location_as_subject=(
                bool(subject_location_id) and agent.current_location_id == subject_location_id
            ),
        )
    return candidates


def rank_eligible_candidates(
    candidates: dict[str, DirectorActorCandidate],
    *,
    excluded_agent_ids: set[str] | None = None,
) -> list[DirectorActorCandidate]:
    excluded = excluded_agent_ids or set()
    return sorted(
        (
            candidate
            for candidate in candidates.values()
            if candidate.eligible and candidate.agent_id not in excluded
        ),
        key=lambda candidate: (
            not candidate.same_location_as_subject,
            candidate.availability != "engaged_with_subject",
            candidate.name,
        ),
    )


def format_recent_event(
    event: Event,
    *,
    agent_names: dict[str, str],
    location_names: dict[str, str],
) -> dict[str, Any]:
    payload = event.payload or {}
    message = payload.get("message") or payload.get("utterance")
    return {
        "tick_no": event.tick_no,
        "event_type": event.event_type,
        "actor_agent_id": event.actor_agent_id,
        "actor_name": agent_names.get(event.actor_agent_id or ""),
        "target_agent_id": event.target_agent_id,
        "target_name": agent_names.get(event.target_agent_id or ""),
        "location_id": event.location_id,
        "location_name": location_names.get(event.location_id or ""),
        "conversation_id": payload.get("conversation_id"),
        "participant_ids": payload.get("participant_ids") or [],
        "summary": str(message or payload.get("reason") or event.event_type)[:160],
    }
