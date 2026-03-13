from __future__ import annotations

from uuid import uuid4

from app.protocol.simulation import ActionType, build_rejected_event_type
from app.sim.memory_constants import calculate_event_importance
from app.store.models import Event


def build_event(
    run_id: str,
    tick_no: int,
    world_time: str,
    action_type: ActionType,
    payload: dict,
    accepted: bool,
    importance: float | None = None,
) -> Event:
    visibility = "public" if accepted else "system"
    event_type = action_type if accepted else build_rejected_event_type(action_type)
    if accepted and action_type == "talk" and payload.get("conversation_event_type") == "speech":
        event_type = "speech"

    # Calculate importance if not provided
    if importance is None:
        importance = calculate_event_importance(
            event_type=event_type,
            payload=payload,
        )

    return Event(
        id=str(uuid4()),
        run_id=run_id,
        tick_no=tick_no,
        event_type=event_type,
        actor_agent_id=payload.get("agent_id"),
        target_agent_id=payload.get("target_agent_id"),
        location_id=payload.get("location_id") or payload.get("to_location_id"),
        visibility=visibility,
        payload=payload,
        importance=importance,
    )


def format_event_for_context(
    evt: Event,
    agent_states: dict,
    location_states: dict,
) -> dict:
    result = {
        "event_type": evt.event_type,
        "tick_no": evt.tick_no,
    }

    if evt.actor_agent_id and evt.actor_agent_id in agent_states:
        result["actor_name"] = agent_states[evt.actor_agent_id].name
    else:
        result["actor_name"] = "某人"

    if evt.target_agent_id and evt.target_agent_id in agent_states:
        result["target_name"] = agent_states[evt.target_agent_id].name

    if evt.location_id and evt.location_id in location_states:
        result["location_name"] = location_states[evt.location_id].name

    payload = evt.payload or {}
    if "message" in payload:
        result["message"] = payload["message"]
    if "conversation_id" in payload:
        result["conversation_id"] = payload["conversation_id"]
    if "conversation_role" in payload:
        result["conversation_role"] = payload["conversation_role"]
    if "conversation_event_type" in payload:
        result["conversation_event_type"] = payload["conversation_event_type"]
    if "speaker_agent_id" in payload:
        result["speaker_agent_id"] = payload["speaker_agent_id"]
        speaker_agent_id = payload["speaker_agent_id"]
        if speaker_agent_id in agent_states:
            result["speaker_name"] = agent_states[speaker_agent_id].name
    if "participant_ids" in payload:
        result["participant_ids"] = payload["participant_ids"]

    return result
