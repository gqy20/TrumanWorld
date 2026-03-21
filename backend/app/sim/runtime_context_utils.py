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
    "你先忙",
    "先忙你的",
    "各自忙",
    "下次再聊",
    "等会儿见",
)
_PENDING_REPLY_MAX_TICK_AGE = 1


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
    if conversation_state is not None:
        context["conversation_state"] = conversation_state

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
        }
    return None


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

        if event_type == "speech" and actor_agent_id == self_agent_id and isinstance(
            target_agent_id, str
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

    newest_direct_speech["priority"] = (
        "high" if newest_direct_speech["is_question"] else "medium"
    )
    return newest_direct_speech


def _looks_like_reply_seeking_message(message: str) -> bool:
    return any(pattern in message for pattern in _QUESTION_REPLY_PATTERNS)


def _looks_like_closing_message(message: str) -> bool:
    normalized = re.sub(r"\s+", "", message)
    return any(pattern in normalized for pattern in _CLOSING_REPLY_PATTERNS)


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
                ((agent.status or {}).get("governance_attention_score", 0.0) or 0.0)
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
            if governance_decision == "block" and isinstance(governance_reason, str) and governance_reason:
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

    if available_actions or policy_notices or blocked_constraints or current_risks or recent_rule_feedback:
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

    if (is_at_workplace or work_friendly_location) and not location_has_power_outage and not location_has_shutdown:
        actions.append("work")

    return actions
