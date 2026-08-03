from datetime import datetime

from app.scenario.bundle_world.types import build_bundle_world_guidance
from app.scenario.runtime_config import RuntimeRoleSemantics
from app.sim.runtime_context_utils import (
    build_agent_world_context,
    extract_encounter_opportunity,
    extract_subject_alert_from_agent_data,
)
from app.sim.action_resolver import ActionIntent
from app.sim.tick_orchestrator import TickOrchestrator
from app.sim.types import AgentDecisionSnapshot
from app.sim.world import (
    ActiveConversationState,
    AgentState,
    InteractionEdgeState,
    LocationState,
    WorldState,
)


def _build_world() -> WorldState:
    return WorldState(
        current_time=datetime(2026, 1, 5, 9, 30),
        tick_minutes=5,
        locations={
            "home": LocationState(id="home", name="Home", location_type="home"),
            "cafe": LocationState(
                id="cafe",
                name="Cafe",
                location_type="cafe",
                occupants={"alice", "bob"},
            ),
        },
        agents={
            "alice": AgentState(
                id="alice",
                name="Alice",
                location_id="cafe",
                occupation="barista",
                status={"mood": "calm", "governance_attention_score": 0.0},
            ),
            "bob": AgentState(
                id="bob",
                name="Bob",
                location_id="cafe",
                occupation="friend",
                status={"mood": "busy"},
            ),
            "truman": AgentState(
                id="truman",
                name="Truman",
                location_id="home",
                status={"suspicion_score": 0.75},
            ),
        },
    )


def test_build_agent_world_context_includes_location_occupants_and_guidance():
    world = _build_world()
    world.world_effects = {
        "location_shutdowns": [
            {
                "location_id": "cafe",
                "start_tick": 0,
                "end_tick": 3,
                "message": "Cafe temporarily closed",
            }
        ],
        "power_outages": [
            {
                "location_id": "cafe",
                "start_tick": 0,
                "end_tick": 3,
                "message": "Cafe blackout",
            }
        ],
    }

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="talk",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        subject_alert_score=0.25,
        world_role="cast",
        director_guidance=build_bundle_world_guidance(
            scene_goal="soft_check_in",
            priority=None,
            message_hint="keep it casual",
            target_agent_id="truman",
            location_hint="cafe",
            reason="watch suspicion",
        ),
        workplace_location_id="cafe",
        relationship_context={
            "bob": {
                "relationship_level": "friend",
                "familiarity": 0.7,
                "trust": 0.4,
                "affinity": 0.6,
            }
        },
    )

    assert context["current_location_name"] == "Cafe"
    assert context["current_location_type"] == "cafe"
    assert {occupant["id"] for occupant in context["location_occupants"]} == {"alice", "bob"}
    assert any(occupant["name"] == "Alice" for occupant in context["location_occupants"])
    assert context["nearby_agent"]["name"] == "Bob"
    assert context["nearby_relationship"]["relationship_level"] == "friend"
    assert context["nearby_relationship"]["familiarity"] == 0.7
    assert context["director_scene_goal"] == "soft_check_in"
    assert context["director_priority"] == "advisory"
    assert context["director_message_hint"] == "keep it casual"
    assert context["subject_alert_score"] == 0.25
    assert "truman_suspicion_score" not in context
    assert context["workplace_location_id"] == "cafe"
    assert context["active_world_effects"] == ["location_shutdown", "power_outage"]
    assert context["current_location_power_status"] == "off"
    assert context["current_location_effects"][0]["effect_type"] == "power_outage"
    assert context["current_location_effects"][1]["effect_type"] == "location_shutdown"


def test_build_agent_world_context_includes_minimal_world_rules_summary():
    world = _build_world()
    world.world_effects = {
        "power_outages": [
            {
                "location_id": "cafe",
                "start_tick": 0,
                "end_tick": 3,
                "message": "Cafe blackout",
            }
        ]
    }

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="talk",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        recent_events=[
            {
                "event_type": "move_rejected",
                "tick_no": 3,
                "payload": {
                    "reason": "location_closed",
                    "governance_execution": {
                        "decision": "block",
                        "reason": "location_closed",
                        "enforcement_action": "intercept",
                        "matched_signals": [],
                    },
                    "rule_evaluation": {
                        "decision": "violates_rule",
                        "primary_rule_id": "closed_location",
                        "reason": "location_closed",
                    },
                },
            }
        ],
    )

    assert context["world_rules_summary"]["policy_notices"] == ["Cafe blackout"]
    assert context["world_rules_summary"]["blocked_constraints"] == ["location_closed"]
    assert context["world_rules_summary"]["current_risks"] == []
    assert context["world_rules_summary"]["recent_rule_feedback"] == [
        "location_closed",
    ]


def test_build_agent_world_context_includes_available_actions_for_stable_context():
    world = _build_world()

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="talk",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        workplace_location_id="cafe",
        recent_events=[],
    )

    assert context["world_rules_summary"]["available_actions"] == [
        "move",
        "talk",
        "rest",
        "work",
    ]


def test_build_agent_world_context_removes_work_from_available_actions_during_power_outage():
    world = _build_world()
    world.world_effects = {
        "power_outages": [
            {
                "location_id": "cafe",
                "start_tick": 0,
                "end_tick": 3,
                "message": "Cafe blackout",
            }
        ]
    }

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="work",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        workplace_location_id="cafe",
        recent_events=[],
    )

    assert context["world_rules_summary"]["available_actions"] == [
        "move",
        "talk",
        "rest",
    ]


def test_build_agent_world_context_removes_talk_and_work_from_available_actions_during_shutdown():
    world = _build_world()
    world.world_effects = {
        "location_shutdowns": [
            {
                "location_id": "cafe",
                "start_tick": 0,
                "end_tick": 3,
                "message": "Cafe temporarily closed",
            }
        ]
    }

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="talk",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        workplace_location_id="cafe",
        recent_events=[],
    )

    assert context["world_rules_summary"]["available_actions"] == [
        "move",
        "rest",
    ]


def test_build_agent_world_context_prefers_governance_warning_feedback():
    world = _build_world()

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="talk",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        recent_events=[
            {
                "event_type": "talk",
                "tick_no": 4,
                "payload": {
                    "governance_execution": {
                        "decision": "warn",
                        "reason": "high_attention_warning",
                        "enforcement_action": "warning",
                        "matched_signals": ["high_attention_location"],
                    },
                    "rule_evaluation": {
                        "decision": "soft_risk",
                        "primary_rule_id": "late_night_stranger_talk_risk",
                        "reason": "late_night_talk_risk",
                    },
                },
            }
        ],
    )

    assert context["world_rules_summary"]["blocked_constraints"] == []
    assert context["world_rules_summary"]["current_risks"] == []
    assert context["world_rules_summary"]["recent_rule_feedback"] == [
        "high_attention_warning",
        "late_night_talk_risk",
    ]


def test_build_agent_world_context_includes_governance_record_only_feedback():
    world = _build_world()

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="talk",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        recent_events=[
            {
                "event_type": "talk",
                "tick_no": 4,
                "payload": {
                    "governance_execution": {
                        "decision": "record_only",
                        "reason": "late_night_talk_risk",
                        "enforcement_action": "record",
                        "matched_signals": ["social"],
                    },
                    "rule_evaluation": {
                        "decision": "soft_risk",
                        "primary_rule_id": "late_night_stranger_talk_risk",
                        "reason": "late_night_talk_risk",
                    },
                },
            }
        ],
    )

    assert context["world_rules_summary"]["recent_rule_feedback"] == [
        "late_night_talk_risk",
    ]


def test_build_agent_world_context_derives_current_risks_from_governance_attention():
    world = _build_world()
    world.agents["alice"].status["governance_attention_score"] = 0.6

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="rest",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        recent_events=[],
    )

    assert context["world_rules_summary"]["blocked_constraints"] == []
    assert context["world_rules_summary"]["recent_rule_feedback"] == []
    assert context["world_rules_summary"]["current_risks"] == [
        "你最近更容易受到注意，异常行为风险正在升高"
    ]


def test_build_agent_world_context_includes_shutdown_notice_in_world_rules_summary():
    world = _build_world()
    world.current_tick = 2
    world.world_effects = {
        "location_shutdowns": [
            {
                "location_id": "cafe",
                "start_tick": 1,
                "end_tick": 5,
                "message": "Cafe temporarily closed",
            }
        ]
    }

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="rest",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        recent_events=[],
    )

    assert context["world_rules_summary"]["policy_notices"] == ["Cafe temporarily closed"]
    assert context["world_rules_summary"]["blocked_constraints"] == []
    assert context["world_rules_summary"]["recent_rule_feedback"] == []


def test_build_agent_world_context_ignores_expired_shutdown_notice():
    world = _build_world()
    world.current_tick = 6
    world.world_effects = {
        "location_shutdowns": [
            {
                "location_id": "cafe",
                "start_tick": 1,
                "end_tick": 5,
                "message": "Cafe temporarily closed",
            }
        ]
    }

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="rest",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        recent_events=[],
    )

    assert context["world_rules_summary"]["available_actions"] == [
        "move",
        "talk",
        "rest",
        "work",
    ]
    assert context["world_rules_summary"]["policy_notices"] == []


def test_build_agent_world_context_omits_subject_alert_score_when_disabled():
    world = _build_world()

    context = build_agent_world_context(
        agent_id="truman",
        world=world,
        current_goal="rest",
        current_location_id="home",
        home_location_id="home",
        nearby_agent_id=None,
        current_status={"energy": 0.8},
        subject_alert_score=None,
        world_role="protagonist",
    )

    assert "subject_alert_score" not in context


def test_build_agent_world_context_includes_pending_reply_for_recent_question():
    world = _build_world()
    world.current_tick = 6

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="rest",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        recent_events=[
            {
                "event_type": "speech",
                "tick_no": 5,
                "actor_agent_id": "bob",
                "actor_name": "Bob",
                "target_agent_id": "alice",
                "message": "要不要一起去喝杯咖啡？",
            }
        ],
    )

    assert context["pending_reply"]["from_agent_id"] == "bob"
    assert context["pending_reply"]["is_question"] is True
    assert context["pending_reply"]["priority"] == "high"


def test_build_agent_world_context_omits_pending_reply_for_closing_message():
    world = _build_world()
    world.current_tick = 6

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="rest",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        recent_events=[
            {
                "event_type": "speech",
                "tick_no": 5,
                "actor_agent_id": "bob",
                "actor_name": "Bob",
                "target_agent_id": "alice",
                "message": "那你先忙，下午见。",
            }
        ],
    )

    assert "pending_reply" not in context


def test_build_agent_world_context_includes_conversation_state_for_active_nearby_dialogue():
    world = _build_world()
    world.current_tick = 6
    world.active_conversations = {
        "conv-1": ActiveConversationState(
            id="conv-1",
            location_id="cafe",
            participant_ids=["alice", "bob"],
            active_speaker_id="bob",
            last_tick_no=5,
            last_message_summary="要不要一起去喝杯咖啡？",
            last_proposal="要不要一起去喝杯咖啡？",
            open_question="要不要一起去喝杯咖啡？",
            repeat_count=2,
        )
    }

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="rest",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        recent_events=[],
    )

    assert context["conversation_state"]["conversation_id"] == "conv-1"
    assert context["conversation_state"]["repeat_count"] == 2
    assert context["conversation_state"]["open_question"] == "要不要一起去喝杯咖啡？"


def test_build_agent_world_context_includes_conversation_diagnostics_for_active_dialogue():
    world = _build_world()
    world.current_tick = 6
    world.active_conversations = {
        "conv-1": ActiveConversationState(
            id="conv-1",
            location_id="cafe",
            participant_ids=["alice", "bob"],
            active_speaker_id="bob",
            last_tick_no=5,
            last_message_summary="那我们中午在咖啡馆碰头吧。",
            last_proposal="要不要一起去喝杯咖啡？",
            open_question="要不要一起去喝杯咖啡？",
            repeat_count=2,
        )
    }

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="rest",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        recent_events=[],
    )

    diagnostics = context["conversation_diagnostics"]
    assert diagnostics["conversation_focus"] == "要不要一起去喝杯咖啡？"
    assert diagnostics["other_party_latest_new_info"] == "那我们中午在咖啡馆碰头吧。"
    assert diagnostics["other_party_latest_intent"] == "coordination"
    assert diagnostics["conversation_phase"] == "closing"
    assert diagnostics["self_recent_repetition"]["is_repeating"] is True
    assert diagnostics["self_recent_repetition"]["repeat_span"] == 2


def test_build_agent_world_context_prefers_partner_interaction_edge_diagnostics():
    world = _build_world()
    world.current_tick = 6
    world.active_conversations = {
        "conv-1": ActiveConversationState(
            id="conv-1",
            location_id="cafe",
            participant_ids=["alice", "bob"],
            active_speaker_id="bob",
            last_tick_no=5,
            last_message_summary="那我们中午在咖啡馆碰头吧。",
            last_proposal="要不要一起去喝杯咖啡？",
            open_question="要不要一起去喝杯咖啡？",
            repeat_count=2,
        )
    }
    world.interaction_edges = {
        "alice->bob": InteractionEdgeState(
            conversation_id="conv-1",
            source_agent_id="alice",
            target_agent_id="bob",
            last_outgoing_message="好，那就中午见。",
            last_incoming_message="那我们中午在咖啡馆碰头吧。",
            last_outgoing_tick_no=6,
            last_incoming_tick_no=5,
            last_outgoing_act="closing",
            last_incoming_act="coordination",
            unresolved_item=None,
            closure_state="soft_closed",
            novelty_since_last_turn=True,
            redundancy_risk=0.1,
        )
    }

    context = build_agent_world_context(
        agent_id="alice",
        world=world,
        current_goal="rest",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        recent_events=[],
    )

    diagnostics = context["conversation_diagnostics"]
    assert context["interaction_edge"]["closure_state"] == "soft_closed"
    assert diagnostics["conversation_focus"] == "那我们中午在咖啡馆碰头吧。"
    assert diagnostics["other_party_latest_new_info"] == "那我们中午在咖啡馆碰头吧。"
    assert diagnostics["other_party_latest_intent"] == "coordination"
    assert diagnostics["conversation_phase"] == "soft_closed"
    assert diagnostics["unresolved_item"] is None


def test_extract_subject_alert_from_agent_data_returns_first_subject_score():
    world = _build_world()
    agent_data = [
        AgentDecisionSnapshot(
            id="alice",
            profile={"world_role": "cast"},
            current_goal="work",
            home_location_id="home",
            current_location_id="cafe",
            recent_events=[],
        ),
        AgentDecisionSnapshot(
            id="truman",
            profile={"world_role": "truman"},
            current_goal="rest",
            home_location_id="home",
            current_location_id="home",
            recent_events=[],
        ),
    ]

    alert_score = extract_subject_alert_from_agent_data(agent_data, world)
    assert alert_score == 0.75


def test_extract_subject_alert_from_agent_data_returns_zero_without_matching_state():
    world = _build_world()
    agent_data = [
        AgentDecisionSnapshot(
            id="ghost-truman",
            profile={"world_role": "truman"},
            current_goal="rest",
            home_location_id="home",
            current_location_id="home",
            recent_events=[],
        )
    ]

    alert_score = extract_subject_alert_from_agent_data(agent_data, world)
    assert alert_score == 0.0


def test_extract_subject_alert_from_agent_data_supports_runtime_semantics():
    world = WorldState(
        current_time=datetime(2026, 1, 5, 9, 30),
        tick_minutes=5,
        locations={},
        agents={
            "hero": AgentState(
                id="hero",
                name="Hero",
                location_id="home",
                status={"anomaly_score": 0.55},
            )
        },
    )
    agent_data = [
        AgentDecisionSnapshot(
            id="hero",
            profile={"world_role": "protagonist"},
            current_goal="rest",
            home_location_id="home",
            current_location_id="home",
            recent_events=[],
        )
    ]

    alert_score = extract_subject_alert_from_agent_data(
        agent_data,
        world,
        semantics=RuntimeRoleSemantics(
            subject_role="protagonist",
            support_roles=["ally"],
            alert_metric="anomaly_score",
        ),
    )

    assert alert_score == 0.55


def test_encounter_opportunity_wakes_only_deterministic_initiator() -> None:
    event = {
        "event_type": "encounter_candidate_created",
        "tick_no": 4,
        "actor_agent_id": "alice",
        "target_agent_id": "bob",
        "encounter_id": "encounter-1",
        "distance_meters": 1.2,
        "zone_id": "quad.center",
    }

    opportunity = extract_encounter_opportunity(
        recent_events=[event], self_agent_id="alice", current_tick=5
    )

    assert opportunity == {
        "encounter_id": "encounter-1",
        "other_agent_id": "bob",
        "distance_meters": 1.2,
        "zone_id": "quad.center",
        "expires_at_world_time": None,
        "response_options": ["ignore", "greet", "stop_and_talk"],
    }
    assert (
        extract_encounter_opportunity(recent_events=[event], self_agent_id="bob", current_tick=5)
        is None
    )


def test_encounter_judgment_maps_talk_to_resolved_social_intent() -> None:
    intent = TickOrchestrator._apply_encounter_judgment(
        intent=ActionIntent(
            agent_id="alice",
            action_type="talk",
            target_agent_id="bob",
            payload={"message": "一起走走？"},
        ),
        world_ctx={
            "encounter_opportunity": {
                "encounter_id": "encounter-1",
                "other_agent_id": "bob",
            }
        },
    )

    assert intent.action_type == "talk"
    assert intent.payload["encounter_id"] == "encounter-1"
    assert intent.payload["encounter_outcome"] == "stop_and_talk"


def test_encounter_judgment_preserves_busy_task_as_ignore_outcome() -> None:
    intent = TickOrchestrator._apply_encounter_judgment(
        intent=ActionIntent(agent_id="alice", action_type="rest"),
        world_ctx={
            "encounter_opportunity": {
                "encounter_id": "encounter-1",
                "other_agent_id": "bob",
            }
        },
    )

    assert intent.action_type == "encounter_resolved"
    assert intent.target_agent_id == "bob"
    assert intent.payload["outcome"] == "ignore"
    assert intent.payload["original_action_type"] == "rest"
