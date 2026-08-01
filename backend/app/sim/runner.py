from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.sim.action_resolver import ActionIntent, ActionResolver, ActionResult
from app.sim.conversation_scheduler import (
    ConversationAssignment,
    ConversationScheduler,
    ConversationSession,
)
from app.sim.governance_consequences import (
    apply_governance_attention_decay,
    apply_governance_consequences,
)
from app.sim.world import ActiveConversationState, InteractionEdgeState, WorldState


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
        previous_day_index = self.world.current_time.toordinal()
        policy_values = self._policy_values()

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
                "participant_ids": participants_by_conversation_id.get(
                    assignment.conversation_id, []
                ),
            }
            for assignment in assignments.values()
        }
        self.resolver.prefill_conversation_assignments(conversation_assignments)
        accepted.extend(self._build_conversation_structure_results(sessions, assignments))
        for intent in intent_list:
            if self._should_skip_intent(intent, assignments):
                continue
            result = self.resolver.resolve(self.world, intent)
            apply_governance_consequences(self.world, result, policy_values=policy_values)
            if result.accepted:
                accepted.append(result)
            else:
                rejected.append(result)
        accepted.extend(self._build_listen_results(sessions, assignments))

        advanced = self.world.advance_tick()
        accepted.extend(
            ActionResult(
                accepted=True,
                action_type="move_arrived",
                reason="arrived",
                event_payload={
                    **movement.to_event_payload(),
                    "state": "arrived",
                    "location_id": movement.to_location_id,
                },
            )
            for movement in advanced.completed_movements
        )
        self._store_active_conversations(
            sessions,
            accepted=accepted,
            tick_no=self.tick_no + advanced.tick_delta,
        )
        self._store_interaction_edges(accepted=accepted, tick_no=self.tick_no + advanced.tick_delta)
        days_elapsed = advanced.current_time.toordinal() - previous_day_index
        apply_governance_attention_decay(
            self.world,
            days_elapsed=days_elapsed,
            policy_values=policy_values,
        )
        world_time = advanced.current_time.isoformat()
        self.tick_no += advanced.tick_delta
        return TickResult(
            tick_no=self.tick_no,
            world_time=world_time,
            tick_delta=advanced.tick_delta,
            accepted=accepted,
            rejected=rejected,
        )

    def _policy_values(self) -> dict[str, object]:
        package = getattr(self.resolver, "_world_design_package", None)
        if package is None:
            return {}
        return dict(package.policy_config.values or {})

    @staticmethod
    def _should_skip_intent(
        intent: ActionIntent,
        assignments: dict[str, ConversationAssignment],
    ) -> bool:
        assignment = assignments.get(intent.agent_id)
        if assignment is None:
            return False
        # A joiner already produces conversation_joined + listen events.
        # Re-processing the original talk intent would turn a successful join
        # into a synthetic talk_rejected, which pollutes rejection metrics.
        return intent.action_type == "talk" and assignment.reason in {
            "conversation_joiner",
            "reciprocal_talk_listener",
        }

    def _build_conversation_structure_results(
        self,
        sessions: list[ConversationSession],
        assignments: dict[str, ConversationAssignment],
    ) -> list[ActionResult]:
        structure_results: list[ActionResult] = []

        for session in sessions:
            if not session.is_new:
                continue
            primary_listener_id = next(
                (
                    participant_id
                    for participant_id in session.participant_ids
                    if participant_id != session.active_speaker_id
                ),
                None,
            )
            structure_results.append(
                ActionResult(
                    accepted=True,
                    action_type="conversation_started",
                    reason="accepted",
                    event_payload={
                        "agent_id": session.active_speaker_id,
                        "target_agent_id": primary_listener_id,
                        "location_id": session.location_id,
                        "conversation_id": session.id,
                        "conversation_event_type": "conversation_started",
                        "speaker_agent_id": session.active_speaker_id,
                        "participant_ids": list(session.participant_ids),
                    },
                )
            )

        session_by_id = {session.id: session for session in sessions}
        for assignment in assignments.values():
            if assignment.reason != "conversation_joiner" or assignment.conversation_id is None:
                continue
            session = session_by_id.get(assignment.conversation_id)
            if session is None:
                continue
            structure_results.append(
                ActionResult(
                    accepted=True,
                    action_type="conversation_joined",
                    reason="accepted",
                    event_payload={
                        "agent_id": assignment.agent_id,
                        "target_agent_id": session.active_speaker_id,
                        "location_id": session.location_id,
                        "conversation_id": session.id,
                        "conversation_event_type": "conversation_joined",
                        "speaker_agent_id": session.active_speaker_id,
                        "participant_ids": list(session.participant_ids),
                    },
                )
            )

        return structure_results

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

    def _store_active_conversations(
        self,
        sessions: list[ConversationSession],
        *,
        accepted: list[ActionResult],
        tick_no: int,
    ) -> None:
        accepted_speeches_by_conversation_id = {
            item.event_payload["conversation_id"]: item
            for item in accepted
            if item.action_type == "talk"
            and isinstance(item.event_payload.get("conversation_id"), str)
        }
        self.world.active_conversations = {
            session.id: ActiveConversationState(
                id=session.id,
                location_id=session.location_id,
                participant_ids=list(session.participant_ids),
                active_speaker_id=session.active_speaker_id,
                last_tick_no=tick_no,
                last_message_summary=self._conversation_message_for_session(
                    session.id,
                    accepted_speeches_by_conversation_id,
                    "message",
                ),
                last_proposal=self._conversation_last_proposal_for_session(
                    session.id,
                    accepted_speeches_by_conversation_id,
                ),
                open_question=self._conversation_open_question_for_session(
                    session.id,
                    accepted_speeches_by_conversation_id,
                ),
                repeat_count=self._conversation_repeat_count_for_session(
                    session.id,
                    accepted_speeches_by_conversation_id,
                ),
            )
            for session in sessions
        }

    def _store_interaction_edges(
        self,
        *,
        accepted: list[ActionResult],
        tick_no: int,
    ) -> None:
        interaction_edges = dict(getattr(self.world, "interaction_edges", {}))

        for item in accepted:
            if item.action_type != "talk":
                continue
            source_agent_id = item.event_payload.get("agent_id")
            target_agent_id = item.event_payload.get("target_agent_id")
            conversation_id = item.event_payload.get("conversation_id")
            message = item.event_payload.get("message")
            if not all(
                isinstance(value, str) and value
                for value in (source_agent_id, target_agent_id, conversation_id, message)
            ):
                continue

            source_key = f"{source_agent_id}->{target_agent_id}"
            reverse_key = f"{target_agent_id}->{source_agent_id}"
            source_edge = interaction_edges.get(source_key) or InteractionEdgeState(
                conversation_id=conversation_id,
                source_agent_id=source_agent_id,
                target_agent_id=target_agent_id,
            )
            reverse_edge = interaction_edges.get(reverse_key) or InteractionEdgeState(
                conversation_id=conversation_id,
                source_agent_id=target_agent_id,
                target_agent_id=source_agent_id,
            )

            source_edge.conversation_id = conversation_id
            reverse_edge.conversation_id = conversation_id

            source_edge.last_outgoing_message = message
            source_edge.last_outgoing_tick_no = tick_no
            source_edge.last_outgoing_act = self._infer_interaction_act(message)

            reverse_edge.last_incoming_message = message
            reverse_edge.last_incoming_tick_no = tick_no
            reverse_edge.last_incoming_act = source_edge.last_outgoing_act

            self._refresh_interaction_edge_state(source_edge)
            self._refresh_interaction_edge_state(reverse_edge)

            interaction_edges[source_key] = source_edge
            interaction_edges[reverse_key] = reverse_edge

        self.world.interaction_edges = interaction_edges

    def _conversation_message_for_session(
        self,
        conversation_id: str,
        accepted_speeches_by_conversation_id: dict[str, ActionResult],
        key: str,
    ) -> str | None:
        speech = accepted_speeches_by_conversation_id.get(conversation_id)
        if speech is None:
            previous = self.world.active_conversations.get(conversation_id)
            return getattr(previous, key, None) if previous is not None else None
        value = speech.event_payload.get("message")
        return value if isinstance(value, str) and value.strip() else None

    def _conversation_last_proposal_for_session(
        self,
        conversation_id: str,
        accepted_speeches_by_conversation_id: dict[str, ActionResult],
    ) -> str | None:
        message = self._conversation_message_for_session(
            conversation_id,
            accepted_speeches_by_conversation_id,
            "last_proposal",
        )
        if message and self._looks_like_proposal_or_question(message):
            return message
        previous = self.world.active_conversations.get(conversation_id)
        return previous.last_proposal if previous is not None else None

    def _conversation_open_question_for_session(
        self,
        conversation_id: str,
        accepted_speeches_by_conversation_id: dict[str, ActionResult],
    ) -> str | None:
        message = self._conversation_message_for_session(
            conversation_id,
            accepted_speeches_by_conversation_id,
            "open_question",
        )
        if message and self._looks_like_question(message):
            return message
        return None

    def _conversation_repeat_count_for_session(
        self,
        conversation_id: str,
        accepted_speeches_by_conversation_id: dict[str, ActionResult],
    ) -> int:
        speech = accepted_speeches_by_conversation_id.get(conversation_id)
        previous = self.world.active_conversations.get(conversation_id)
        if speech is None:
            return previous.repeat_count if previous is not None else 0

        message = speech.event_payload.get("message")
        if not isinstance(message, str) or not message.strip():
            return 0
        normalized_message = self._normalize_conversation_text(message)
        previous_message = previous.last_proposal if previous is not None else None
        if (
            isinstance(previous_message, str)
            and self._normalize_conversation_text(previous_message) == normalized_message
        ):
            return (previous.repeat_count if previous is not None else 1) + 1
        return 1

    def _refresh_interaction_edge_state(self, edge: InteractionEdgeState) -> None:
        latest_message, latest_act, latest_direction = self._latest_interaction_components(edge)
        edge.novelty_since_last_turn = self._interaction_novelty_since_last_turn(edge)
        edge.redundancy_risk = self._interaction_redundancy_risk(edge)
        edge.unresolved_item = self._interaction_unresolved_item(edge, latest_act, latest_direction)
        edge.closure_state = self._interaction_closure_state(
            edge=edge,
            latest_message=latest_message,
            latest_act=latest_act,
            latest_direction=latest_direction,
        )

    def _latest_interaction_components(
        self,
        edge: InteractionEdgeState,
    ) -> tuple[str | None, str | None, str | None]:
        outgoing_tick = (
            edge.last_outgoing_tick_no if isinstance(edge.last_outgoing_tick_no, int) else -1
        )
        incoming_tick = (
            edge.last_incoming_tick_no if isinstance(edge.last_incoming_tick_no, int) else -1
        )
        if outgoing_tick >= incoming_tick:
            return edge.last_outgoing_message, edge.last_outgoing_act, "outgoing"
        return edge.last_incoming_message, edge.last_incoming_act, "incoming"

    def _interaction_unresolved_item(
        self,
        edge: InteractionEdgeState,
        latest_act: str | None,
        latest_direction: str | None,
    ) -> str | None:
        if latest_act not in {"question", "proposal"}:
            return None
        if latest_direction == "incoming":
            return edge.last_incoming_message
        if latest_direction == "outgoing":
            return edge.last_outgoing_message
        return None

    def _interaction_closure_state(
        self,
        *,
        edge: InteractionEdgeState,
        latest_message: str | None,
        latest_act: str | None,
        latest_direction: str | None,
    ) -> str:
        if latest_act in {"question", "proposal"}:
            return "awaiting_response"
        if latest_act == "closing":
            if edge.redundancy_risk >= 0.6:
                return "closed"
            return "soft_closed"
        if latest_direction == "incoming" and edge.last_outgoing_act in {"question", "proposal"}:
            return "open"
        if latest_message:
            return "open"
        return "open"

    def _interaction_novelty_since_last_turn(self, edge: InteractionEdgeState) -> bool:
        if not edge.last_outgoing_message or not edge.last_incoming_message:
            return True
        return (
            self._conversation_overlap_score(
                edge.last_outgoing_message,
                edge.last_incoming_message,
            )
            < 0.45
        )

    def _interaction_redundancy_risk(self, edge: InteractionEdgeState) -> float:
        scores = [
            self._conversation_overlap_score(
                edge.last_outgoing_message, edge.last_incoming_message
            ),
        ]
        if edge.last_outgoing_act == "closing" and edge.last_incoming_act == "closing":
            scores.append(0.7)
        return max(scores)

    @staticmethod
    def _normalize_conversation_text(text: str) -> str:
        return "".join(text.split()).strip("，。！？,.!?：:;；\"'“”‘’").lower()

    @staticmethod
    def _conversation_overlap_score(left: str | None, right: str | None) -> float:
        if not left or not right:
            return 0.0
        normalized_left = SimulationRunner._normalize_conversation_text(left)
        normalized_right = SimulationRunner._normalize_conversation_text(right)
        if not normalized_left or not normalized_right:
            return 0.0

        def _char_windows(text: str, width: int = 8) -> set[str]:
            if len(text) <= width:
                return {text}
            return {text[idx : idx + width] for idx in range(len(text) - width + 1)}

        left_windows = _char_windows(normalized_left)
        right_windows = _char_windows(normalized_right)
        if not left_windows or not right_windows:
            return 0.0
        return len(left_windows & right_windows) / min(len(left_windows), len(right_windows))

    @staticmethod
    def _infer_interaction_act(message: str) -> str:
        normalized = SimulationRunner._normalize_conversation_text(message)
        if any(token in message for token in ("？", "?", "吗", "要不要", "可以吗", "方便吗")):
            return "question"
        if any(
            token in normalized
            for token in ("下午见", "回头见", "回头再聊", "下次再聊", "先忙", "中午见")
        ):
            return "closing"
        if any(
            token in message
            for token in ("中午", "下午", "晚上", "碰头", "见面", "一起去", "咖啡馆")
        ):
            return "coordination"
        if any(token in message for token in ("一起", "要不", "不如")):
            return "proposal"
        return "social"

    @staticmethod
    def _looks_like_question(message: str) -> bool:
        return any(token in message for token in ("？", "?", "要不要", "可以吗", "方便吗", "吗"))

    @staticmethod
    def _looks_like_proposal_or_question(message: str) -> bool:
        return SimulationRunner._looks_like_question(message) or any(
            token in message for token in ("一起", "先花十分钟", "要不", "不如")
        )
