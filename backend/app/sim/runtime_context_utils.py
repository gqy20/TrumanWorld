from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.scenario.runtime_config import ScenarioRuntimeConfig
from app.scenario.types import ScenarioGuidance, get_world_role
from app.sim.types import AgentDecisionSnapshot, RuntimeWorldContext
from app.sim.world_queries import get_agent, get_location, get_location_occupants

if TYPE_CHECKING:
    from app.store.models import Agent
    from app.sim.world import WorldState


_QUESTION_REPLY_PATTERNS = (
    "？",
    "?",
    "要不要",
    "要一起",
    "能不能",
    "你觉得",
    "要吗",
    "方便吗",
    "可以吗",
)
_CLOSING_REPLY_PATTERNS = (
    "下午见",
    "回头见",
    "回头再聊",
    "回头再联系",
    "碰头",
    "中午见",
    "你先忙",
    "先忙你的",
    "各自忙",
    "下次再聊",
    "等会儿见",
)
_PENDING_REPLY_MAX_TICK_AGE = 1
_ENCOUNTER_MAX_TICK_AGE = 1


def extract_encounter_opportunity(
    *,
    recent_events: list[dict],
    self_agent_id: str | None,
    current_tick: int,
) -> dict[str, object] | None:
    if not self_agent_id:
        return None
    for event in recent_events:
        if event.get("event_type") != "encounter_candidate_created":
            continue
        event_tick = event.get("tick_no")
        if not isinstance(event_tick, int) or current_tick - event_tick > _ENCOUNTER_MAX_TICK_AGE:
            continue
        actor_id = event.get("actor_agent_id")
        target_id = event.get("target_agent_id")
        if self_agent_id != actor_id:
            continue
        other_agent_id = target_id
        encounter_id = event.get("encounter_id")
        if not isinstance(other_agent_id, str) or not isinstance(encounter_id, str):
            continue
        return {
            "encounter_id": encounter_id,
            "other_agent_id": other_agent_id,
            "distance_meters": event.get("distance_meters"),
            "zone_id": event.get("zone_id"),
            "expires_at_world_time": event.get("expires_at_world_time"),
            "response_options": ["ignore", "greet", "stop_and_talk"],
        }
    return None


def build_agent_world_context(
    *,
    agent_id: str | None = None,
    world: WorldState,
    current_goal: str | None,
    current_location_id: str | None,
    home_location_id: str | None,
    nearby_agent_id: str | None,
    current_status: dict | None = None,
    subject_alert_score: float | None = 0.0,
    world_role: str | None = None,
    director_guidance: ScenarioGuidance | None = None,
    director_directives: list[dict] | None = None,
    workplace_location_id: str | None = None,
    current_plan: dict | None = None,
    relationship_context: dict[str, dict[str, object]] | None = None,
    recent_events: list[dict] | None = None,
) -> RuntimeWorldContext:
    # Identify social locations (plaza / cafe) for talk-goal navigation
    social_location_ids = [
        loc_id for loc_id, loc in world.locations.items() if loc.location_type in {"plaza", "cafe"}
    ]

    context = {
        "current_goal": current_goal,
        "current_location_id": current_location_id,
        "home_location_id": home_location_id,
        "workplace_location_id": workplace_location_id,
        "known_location_ids": sorted(world.locations.keys()),
        "social_location_ids": social_location_ids,
        "nearby_agent_id": nearby_agent_id,
        "self_status": current_status or {},
        **world.time_context(),
    }
    encounter_opportunity = extract_encounter_opportunity(
        recent_events=recent_events or [],
        self_agent_id=agent_id,
        current_tick=getattr(world, "current_tick", 0),
    )
    if encounter_opportunity is not None:
        context["encounter_opportunity"] = encounter_opportunity
    if world.embodiment_catalog is not None:
        context["available_activities"] = [
            {
                "activity_type": activity_type,
                "target_location_ids": sorted(
                    location_id
                    for location_id, location in world.locations.items()
                    if not definition.requirements.location_types
                    or location.location_type in definition.requirements.location_types
                ),
                "steps": [step.action for step in definition.steps],
            }
            for activity_type, definition in sorted(
                world.embodiment_catalog.activities.activities.items()
            )
        ]
    if subject_alert_score is not None:
        context["subject_alert_score"] = subject_alert_score

    # Inject daily schedule so LLM can self-determine appropriate behavior per time period
    if current_plan:
        context["daily_schedule"] = current_plan

    if current_location_id:
        location = get_location(world, current_location_id)
        if location:
            context["current_location_name"] = location.name
            context["current_location_type"] = location.location_type

    # Add all occupants at current location (for multi-agent awareness)
    if current_location_id:
        context["location_occupants"] = get_location_occupants(
            world, current_location_id, exclude_agent_id=None
        )

    if nearby_agent_id:
        nearby_agent = get_agent(world, nearby_agent_id)
        if nearby_agent:
            context["nearby_agent"] = {
                "id": nearby_agent.id,
                "name": nearby_agent.name,
                "occupation": nearby_agent.occupation,
            }
            if relationship_context and nearby_agent.id in relationship_context:
                context["nearby_relationship"] = dict(relationship_context[nearby_agent.id])

    pending_reply = extract_pending_reply(
        recent_events=recent_events or [],
        self_agent_id=agent_id,
        current_tick=getattr(world, "current_tick", 0),
        nearby_agent_id=nearby_agent_id,
    )
    if pending_reply is not None:
        context["pending_reply"] = pending_reply

    conversation_state = extract_active_conversation_state(
        world=world,
        self_agent_id=agent_id,
        nearby_agent_id=nearby_agent_id,
    )
    interaction_edge = extract_interaction_edge_state(
        world=world,
        self_agent_id=agent_id,
        nearby_agent_id=nearby_agent_id,
    )
    if conversation_state is not None:
        context["conversation_state"] = conversation_state
        context["conversation_diagnostics"] = extract_conversation_diagnostics(
            conversation_state,
            interaction_edge_state=interaction_edge,
        )
    if interaction_edge is not None:
        context["interaction_edge"] = interaction_edge

    if world_role:
        context["world_role"] = world_role
    _inject_world_effects(context, world, current_location_id)
    _inject_world_rules_summary(
        context,
        world,
        agent_id,
        current_location_id,
        nearby_agent_id,
        workplace_location_id,
        recent_events or [],
    )
    if director_guidance:
        context.update(_normalize_director_guidance(director_guidance))
    if director_directives:
        context["director_directives"] = list(director_directives)

    return context


def extract_active_conversation_state(
    *,
    world: WorldState,
    self_agent_id: str | None,
    nearby_agent_id: str | None,
) -> dict[str, object] | None:
    if not self_agent_id or not nearby_agent_id:
        return None

    for conversation in getattr(world, "active_conversations", {}).values():
        participants = conversation.participant_ids
        if self_agent_id not in participants or nearby_agent_id not in participants:
            continue
        return {
            "conversation_id": conversation.id,
            "participant_ids": list(participants),
            "active_speaker_id": conversation.active_speaker_id,
            "last_tick_no": conversation.last_tick_no,
            "last_message_summary": conversation.last_message_summary,
            "last_proposal": conversation.last_proposal,
            "open_question": conversation.open_question,
            "repeat_count": conversation.repeat_count,
            "started_tick_no": getattr(conversation, "started_tick_no", 0),
            "turn_count": getattr(conversation, "turn_count", 0),
            "phase": getattr(conversation, "phase", "open"),
        }
    return None


def extract_conversation_diagnostics(
    conversation_state: dict[str, object],
    *,
    interaction_edge_state: dict[str, object] | None = None,
) -> dict[str, object]:
    if interaction_edge_state:
        return extract_interaction_edge_diagnostics(
            conversation_state=conversation_state,
            interaction_edge_state=interaction_edge_state,
        )

    last_message_summary = _clean_optional_text(conversation_state.get("last_message_summary"))
    last_proposal = _clean_optional_text(conversation_state.get("last_proposal"))
    open_question = _clean_optional_text(conversation_state.get("open_question"))
    repeat_count = conversation_state.get("repeat_count")
    normalized_repeat_count = (
        repeat_count if isinstance(repeat_count, int) and repeat_count > 0 else 0
    )

    diagnostics: dict[str, object] = {
        "conversation_focus": last_proposal or open_question or last_message_summary,
        "other_party_latest_new_info": last_message_summary,
        "other_party_latest_intent": _infer_conversation_intent(
            last_message_summary, last_proposal
        ),
        "conversation_phase": _infer_conversation_phase(last_message_summary, open_question),
        "self_recent_repetition": {
            "is_repeating": normalized_repeat_count >= 2,
            "type": "proposal" if last_proposal else "paraphrase",
            "repeat_span": normalized_repeat_count,
        },
        "unresolved_item": open_question or last_proposal,
    }
    return diagnostics


def extract_interaction_edge_state(
    *,
    world: WorldState,
    self_agent_id: str | None,
    nearby_agent_id: str | None,
) -> dict[str, object] | None:
    if not self_agent_id or not nearby_agent_id:
        return None

    edge = getattr(world, "interaction_edges", {}).get(f"{self_agent_id}->{nearby_agent_id}")
    if edge is None:
        return None
    return {
        "conversation_id": edge.conversation_id,
        "source_agent_id": edge.source_agent_id,
        "target_agent_id": edge.target_agent_id,
        "last_outgoing_message": edge.last_outgoing_message,
        "last_incoming_message": edge.last_incoming_message,
        "last_outgoing_tick_no": edge.last_outgoing_tick_no,
        "last_incoming_tick_no": edge.last_incoming_tick_no,
        "last_outgoing_act": edge.last_outgoing_act,
        "last_incoming_act": edge.last_incoming_act,
        "unresolved_item": edge.unresolved_item,
        "closure_state": edge.closure_state,
        "novelty_since_last_turn": edge.novelty_since_last_turn,
        "redundancy_risk": edge.redundancy_risk,
    }


def extract_interaction_edge_diagnostics(
    *,
    conversation_state: dict[str, object],
    interaction_edge_state: dict[str, object],
) -> dict[str, object]:
    repeat_count = conversation_state.get("repeat_count")
    normalized_repeat_count = (
        repeat_count if isinstance(repeat_count, int) and repeat_count > 0 else 0
    )
    last_incoming_message = _clean_optional_text(
        interaction_edge_state.get("last_incoming_message")
    )
    last_outgoing_message = _clean_optional_text(
        interaction_edge_state.get("last_outgoing_message")
    )
    closure_state = _clean_optional_text(interaction_edge_state.get("closure_state")) or "open"
    unresolved_item = _clean_optional_text(interaction_edge_state.get("unresolved_item"))
    latest_focus = unresolved_item or last_incoming_message or last_outgoing_message
    last_incoming_act = (
        _clean_optional_text(interaction_edge_state.get("last_incoming_act")) or "social"
    )
    redundancy_risk = interaction_edge_state.get("redundancy_risk")
    redundancy_value = redundancy_risk if isinstance(redundancy_risk, (int, float)) else 0.0

    return {
        "conversation_focus": latest_focus,
        "other_party_latest_new_info": last_incoming_message,
        "other_party_latest_intent": last_incoming_act,
        "conversation_phase": closure_state,
        "self_recent_repetition": {
            "is_repeating": normalized_repeat_count >= 2 or redundancy_value >= 0.6,
            "type": "proposal" if conversation_state.get("last_proposal") else "paraphrase",
            "repeat_span": normalized_repeat_count,
        },
        "unresolved_item": unresolved_item,
    }


def extract_pending_reply(
    *,
    recent_events: list[dict],
    self_agent_id: str | None,
    current_tick: int,
    nearby_agent_id: str | None = None,
) -> dict[str, object] | None:
    """Return the newest direct speech that should likely be answered next tick."""
    if not recent_events or not self_agent_id:
        return None

    latest_outgoing_tick_by_target: dict[str, int] = {}
    newest_direct_speech: dict[str, object] | None = None

    for event in recent_events:
        event_type = event.get("event_type")
        actor_agent_id = event.get("actor_agent_id")
        target_agent_id = event.get("target_agent_id")
        tick_no = event.get("tick_no")
        if not isinstance(tick_no, int):
            continue

        if (
            event_type == "speech"
            and actor_agent_id == self_agent_id
            and isinstance(target_agent_id, str)
        ):
            previous_tick = latest_outgoing_tick_by_target.get(target_agent_id, -1)
            latest_outgoing_tick_by_target[target_agent_id] = max(previous_tick, tick_no)
            continue

        if event_type != "speech":
            continue
        if target_agent_id != self_agent_id or not isinstance(actor_agent_id, str):
            continue
        if nearby_agent_id is not None and actor_agent_id != nearby_agent_id:
            continue
        if current_tick - tick_no > _PENDING_REPLY_MAX_TICK_AGE:
            continue
        if latest_outgoing_tick_by_target.get(actor_agent_id, -1) >= tick_no:
            continue
        if newest_direct_speech is None or tick_no > newest_direct_speech["tick_no"]:
            message = event.get("message")
            if not isinstance(message, str) or not message.strip():
                continue
            newest_direct_speech = {
                "from_agent_id": actor_agent_id,
                "from_agent_name": event.get("actor_name"),
                "message": message.strip(),
                "tick_no": tick_no,
                "is_question": _looks_like_reply_seeking_message(message),
                "is_closing": _looks_like_closing_message(message),
            }

    if newest_direct_speech is None or newest_direct_speech["is_closing"]:
        return None

    newest_direct_speech["priority"] = "high" if newest_direct_speech["is_question"] else "medium"
    return newest_direct_speech


def _looks_like_reply_seeking_message(message: str) -> bool:
    return any(pattern in message for pattern in _QUESTION_REPLY_PATTERNS)


def _looks_like_closing_message(message: str) -> bool:
    normalized = re.sub(r"\s+", "", message)
    return any(pattern in normalized for pattern in _CLOSING_REPLY_PATTERNS)


def _clean_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _infer_conversation_intent(
    latest_message: str | None,
    last_proposal: str | None,
) -> str:
    if latest_message and _looks_like_coordination_message(latest_message):
        return "coordination"
    if latest_message and _looks_like_reply_seeking_message(latest_message):
        return "question"
    if last_proposal:
        return "proposal"
    return "social"


def _infer_conversation_phase(
    latest_message: str | None,
    open_question: str | None,
) -> str:
    if latest_message and (
        _looks_like_closing_message(latest_message)
        or _looks_like_coordination_message(latest_message)
    ):
        return "closing"
    if open_question:
        return "coordination"
    return "exploring"


def _looks_like_coordination_message(message: str) -> bool:
    return any(
        token in message
        for token in (
            "中午",
            "下午",
            "晚上",
            "碰头",
            "见面",
            "见吧",
            "咖啡馆",
            "一起去",
        )
    )


def inject_profile_fields_into_context(
    context: dict,
    profile: dict | None,
) -> None:
    """Inject selected agent profile fields into the world context dict.

    Currently injects: schedule_type (for heuristics shift detection).
    Called by service after build_agent_world_context.
    """
    if not profile:
        return
    schedule_type = profile.get("schedule_type")
    if schedule_type:
        context["schedule_type"] = schedule_type


def extract_subject_alert_from_agent_data(
    agent_data: list[AgentDecisionSnapshot],
    world: WorldState,
    *,
    semantics: ScenarioRuntimeConfig | None = None,
) -> float:
    resolved = semantics or ScenarioRuntimeConfig()
    for agent_snapshot in agent_data:
        profile = agent_snapshot.profile or {}
        if get_world_role(profile) != resolved.subject_role:
            continue
        state = get_agent(world, agent_snapshot.id)
        if state is None:
            continue
        return float((state.status or {}).get(resolved.alert_metric, 0.0) or 0.0)
    return 0.0


def extract_subject_alert_from_agents(
    agents: list[Agent],
    world: WorldState,
    *,
    semantics: ScenarioRuntimeConfig | None = None,
) -> float:
    resolved = semantics or ScenarioRuntimeConfig()
    for agent in agents:
        if get_world_role(agent.profile) != resolved.subject_role:
            continue
        state = get_agent(world, agent.id)
        if state is None:
            continue
        return float((state.status or {}).get(resolved.alert_metric, 0.0) or 0.0)
    return 0.0


def _normalize_director_guidance(guidance: ScenarioGuidance) -> ScenarioGuidance:
    scene_goal = guidance.get("director_scene_goal")
    if scene_goal is None:
        return {}

    normalized: ScenarioGuidance = {"director_scene_goal": scene_goal}
    normalized["director_priority"] = guidance.get("director_priority") or "advisory"

    for key in (
        "director_message_hint",
        "director_target_agent_id",
        "director_location_hint",
        "director_reason",
    ):
        value = guidance.get(key)
        if value is not None:
            normalized[key] = value

    return normalized


def _inject_world_effects(
    context: dict,
    world: WorldState,
    current_location_id: str | None,
) -> None:
    world_effects = getattr(world, "world_effects", {}) or {}
    active_world_effects: list[str] = []
    current_location_effects: list[dict] = []

    for outage in _iter_active_location_effects(
        world,
        world_effects.get("power_outages"),
        current_location_id=None,
    ):
        active_world_effects.append("power_outage")
        if current_location_id and outage.get("location_id") == current_location_id:
            current_location_effects.append(
                {
                    "effect_type": "power_outage",
                    "location_id": outage.get("location_id"),
                    "message": outage.get("message"),
                    "end_tick": outage.get("end_tick"),
                }
            )

    for shutdown in _iter_active_location_effects(
        world,
        world_effects.get("location_shutdowns"),
        current_location_id=None,
    ):
        active_world_effects.append("location_shutdown")
        if current_location_id and shutdown.get("location_id") == current_location_id:
            current_location_effects.append(
                {
                    "effect_type": "location_shutdown",
                    "location_id": shutdown.get("location_id"),
                    "message": shutdown.get("message"),
                    "end_tick": shutdown.get("end_tick"),
                }
            )

    if active_world_effects:
        context["active_world_effects"] = sorted(set(active_world_effects))
    if current_location_effects:
        context["current_location_effects"] = current_location_effects
        context["current_location_power_status"] = "off"


def _inject_world_rules_summary(
    context: dict,
    world: WorldState,
    agent_id: str | None,
    current_location_id: str | None,
    nearby_agent_id: str | None,
    workplace_location_id: str | None,
    recent_events: list[dict],
) -> None:
    available_actions = _derive_available_actions(
        world,
        current_location_id=current_location_id,
        nearby_agent_id=nearby_agent_id,
        workplace_location_id=workplace_location_id,
    )
    policy_notices: list[str] = []
    blocked_constraints: list[str] = []
    current_risks: list[str] = []
    recent_rule_feedback: list[str] = []

    world_effects = getattr(world, "world_effects", {}) or {}
    for effect in _iter_active_location_effects(
        world,
        world_effects.get("power_outages"),
        current_location_id=current_location_id,
    ):
        message = effect.get("message")
        if isinstance(message, str) and message:
            policy_notices.append(message)

    for effect in _iter_active_location_effects(
        world,
        world_effects.get("location_shutdowns"),
        current_location_id=current_location_id,
    ):
        message = effect.get("message")
        if isinstance(message, str) and message:
            policy_notices.append(message)

    if agent_id:
        agent = get_agent(world, agent_id)
        if agent is not None:
            attention_score = float(
                (agent.status or {}).get("governance_attention_score", 0.0) or 0.0
            )
            if attention_score >= 0.8:
                current_risks.append("你正处于高关注状态，进一步试探边界的代价会更高")
            elif attention_score >= 0.5:
                current_risks.append("你最近更容易受到注意，异常行为风险正在升高")
            elif attention_score >= 0.2:
                current_risks.append("你最近有一定制度关注，行动需要更谨慎")

    for event in recent_events:
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        governance_execution = payload.get("governance_execution") or {}
        if isinstance(governance_execution, dict):
            governance_decision = governance_execution.get("decision")
            governance_reason = governance_execution.get("reason")
            if (
                governance_decision == "block"
                and isinstance(governance_reason, str)
                and governance_reason
            ):
                blocked_constraints.append(governance_reason)
            elif (
                governance_decision in {"warn", "record_only"}
                and isinstance(governance_reason, str)
                and governance_reason
            ):
                recent_rule_feedback.append(governance_reason)
        rule_evaluation = payload.get("rule_evaluation") or {}
        if not isinstance(rule_evaluation, dict):
            continue
        reason = rule_evaluation.get("reason") or payload.get("reason")
        if isinstance(reason, str) and reason and reason not in recent_rule_feedback:
            recent_rule_feedback.append(reason)

    if (
        available_actions
        or policy_notices
        or blocked_constraints
        or current_risks
        or recent_rule_feedback
    ):
        context["world_rules_summary"] = {
            "available_actions": available_actions,
            "policy_notices": policy_notices,
            "blocked_constraints": blocked_constraints,
            "current_risks": current_risks,
            "recent_rule_feedback": recent_rule_feedback,
        }


def _iter_active_location_effects(
    world: WorldState,
    effects: object,
    *,
    current_location_id: str | None,
) -> list[dict]:
    if not isinstance(effects, list):
        return []

    current_tick = getattr(world, "current_tick", 0)
    active_effects: list[dict] = []
    for effect in effects:
        if not isinstance(effect, dict):
            continue
        if current_location_id and effect.get("location_id") != current_location_id:
            continue
        start_tick = effect.get("start_tick")
        end_tick = effect.get("end_tick")
        if isinstance(start_tick, int) and current_tick < start_tick:
            continue
        if isinstance(end_tick, int) and current_tick >= end_tick:
            continue
        active_effects.append(effect)
    return active_effects


def _derive_available_actions(
    world: WorldState,
    *,
    current_location_id: str | None,
    nearby_agent_id: str | None,
    workplace_location_id: str | None,
) -> list[str]:
    actions: list[str] = ["move"]
    location_has_shutdown = any(
        effect.get("location_id") == current_location_id
        for effect in _iter_active_location_effects(
            world,
            (getattr(world, "world_effects", {}) or {}).get("location_shutdowns"),
            current_location_id=None,
        )
    )
    if nearby_agent_id and not location_has_shutdown:
        actions.append("talk")
    actions.append("rest")

    location = get_location(world, current_location_id) if current_location_id else None
    location_type = location.location_type if location is not None else None
    is_at_workplace = bool(workplace_location_id) and current_location_id == workplace_location_id
    work_friendly_location = location_type in {"office", "hospital", "cafe", "shop"}
    location_has_power_outage = any(
        effect.get("location_id") == current_location_id
        for effect in _iter_active_location_effects(
            world,
            (getattr(world, "world_effects", {}) or {}).get("power_outages"),
            current_location_id=None,
        )
    )

    if (
        (is_at_workplace or work_friendly_location)
        and not location_has_power_outage
        and not location_has_shutdown
    ):
        actions.append("work")

    return actions
