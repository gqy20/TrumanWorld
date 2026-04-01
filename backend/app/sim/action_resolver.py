from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.scenario.runtime.governance_executor import execute_governance
from app.scenario.runtime.rule_evaluator import evaluate_rules
from app.scenario.runtime.world_design_models import (
    GovernanceExecutionResult,
    RuleEvaluationResult,
    WorldDesignRuntimePackage,
)
from app.sim.world import WorldState


@dataclass
class PlanUpdate:
    """Represents a request to update the agent's current plan."""

    reason: str
    new_morning: str | None = None
    new_daytime: str | None = None
    new_evening: str | None = None


@dataclass
class ActionIntent:
    agent_id: str
    action_type: str
    target_location_id: str | None = None
    target_agent_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    plan_update: PlanUpdate | None = None  # Optional plan update request
    raw_intent: str | None = None  # Original intent description (for free actions)


@dataclass
class ActionResult:
    accepted: bool
    action_type: str
    reason: str
    event_payload: dict[str, Any] = field(default_factory=dict)
    rule_evaluation: RuleEvaluationResult | None = None
    governance_execution: GovernanceExecutionResult | None = None


class ActionResolver:
    """Validates and applies agent action intents.

    Maintains a per-tick set of agents already involved in a talk exchange
    to enforce turn-based conversation: within a single tick only one side
    of a pair may initiate talk, so the other side will see the message in
    their next-tick recent_events and can reply naturally.
    """

    STANDARD_ACTIONS = {"move", "rest", "work", "talk"}

    def __init__(self, world_design_package: WorldDesignRuntimePackage | None = None) -> None:
        # Agents that have completed (accepted) a talk this tick — blocks further talk.
        self._talked_agents: set[str] = set()
        # Agents pre-registered as talk targets this tick — blocks non-talk actions.
        self._prefilled_targets: set[str] = set()
        # Scheduler-provided conversation roles for this tick.
        self._conversation_roles: dict[str, str] = {}
        self._conversation_ids: dict[str, str] = {}
        self._conversation_participants: dict[str, list[str]] = {}
        self._world_design_package = world_design_package

    def reset_tick(self) -> None:
        """Clear per-tick state at the start of each tick."""
        self._talked_agents.clear()
        self._prefilled_targets.clear()
        self._conversation_roles.clear()
        self._conversation_ids.clear()
        self._conversation_participants.clear()

    def prefill_conversation_assignments(
        self,
        conversation_assignments: dict[str, dict[str, object]],
    ) -> None:
        """Register scheduler assignments, including role and conversation id."""
        for agent_id, assignment in conversation_assignments.items():
            role = assignment.get("role")
            if isinstance(role, str):
                self._conversation_roles[agent_id] = role
            conversation_id = assignment.get("conversation_id")
            if isinstance(conversation_id, str):
                self._conversation_ids[agent_id] = conversation_id
            participant_ids = assignment.get("participant_ids")
            if isinstance(participant_ids, list):
                self._conversation_participants[agent_id] = [
                    participant_id
                    for participant_id in participant_ids
                    if isinstance(participant_id, str)
                ]

        listener_agent_ids = {
            agent_id
            for agent_id, assignment in conversation_assignments.items()
            if assignment.get("role") == "listener"
        }
        self._prefilled_targets.update(listener_agent_ids)

    def resolve(self, world: WorldState, intent: ActionIntent) -> ActionResult:
        rule_evaluation = self._evaluate_rules(world, intent)
        governance_execution = self._execute_governance(world, intent, rule_evaluation)
        agent = world.get_agent(intent.agent_id)
        if agent is None:
            return self._build_result(
                accepted=False,
                action_type=intent.action_type,
                reason="agent_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": None,
                    **intent.payload,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        if governance_execution is not None and governance_execution.decision == "block":
            return self._build_rule_rejection(
                agent.location_id,
                intent,
                rule_evaluation,
                governance_execution,
            )

        # Standard actions: use dedicated resolvers
        if intent.action_type in self.STANDARD_ACTIONS:
            return self._resolve_standard(
                world,
                intent,
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        # Free actions: route to free action handler
        return self._resolve_free_action(
            world,
            intent,
            rule_evaluation=rule_evaluation,
            governance_execution=governance_execution,
        )

        # This code should never be reached since STANDARD_ACTIONS are handled above.
        # Redirect to standard resolver as a fallback.
        return self._resolve_standard(
            world,
            intent,
            rule_evaluation=rule_evaluation,
            governance_execution=governance_execution,
        )

    def _resolve_standard(
        self,
        world: WorldState,
        intent: ActionIntent,
        *,
        rule_evaluation: RuleEvaluationResult | None,
        governance_execution: GovernanceExecutionResult | None,
    ) -> ActionResult:
        """Route standard actions to their dedicated resolvers.

        Standard actions are: move, talk, work, rest.
        """
        # Check work_ban restriction
        if intent.action_type == "work" and world.has_restriction(
            intent.agent_id, "work_ban", scope_value="work"
        ):
            return self._build_result(
                False,
                intent.action_type,
                "work_ban",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": world.get_agent(intent.agent_id).location_id
                    if world.get_agent(intent.agent_id)
                    else None,
                    **intent.payload,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        if self._conversation_roles.get(intent.agent_id) == "listener":
            if intent.action_type == "talk":
                event_payload = {
                    "agent_id": intent.agent_id,
                    "location_id": world.get_agent(intent.agent_id).location_id
                    if world.get_agent(intent.agent_id)
                    else None,
                    "target_agent_id": intent.target_agent_id,
                }
                self._append_conversation_metadata(intent.agent_id, event_payload)
                return self._build_result(
                    False,
                    intent.action_type,
                    "conversation_turn_taken",
                    event_payload=event_payload,
                    rule_evaluation=rule_evaluation,
                    governance_execution=governance_execution,
                )

        # If this agent is pre-registered as a talk target this tick,
        # suppress non-talk actions so no spurious rest/work/move appears
        # alongside the talk event in the timeline.
        agent = world.get_agent(intent.agent_id)
        if intent.agent_id in self._prefilled_targets and intent.action_type != "talk":
            event_payload = {
                "agent_id": intent.agent_id,
                "location_id": agent.location_id if agent else None,
            }
            self._append_conversation_metadata(intent.agent_id, event_payload)
            return self._build_result(
                False,
                intent.action_type,
                "agent_in_conversation",
                event_payload=event_payload,
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        if intent.action_type == "move":
            return self._resolve_move(
                world,
                intent,
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )
        if intent.action_type == "talk":
            return self._resolve_talk(
                world,
                intent,
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )
        if intent.action_type == "work":
            return self._resolve_work(
                world,
                intent,
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        # rest and other standard actions
        return self._build_result(
            accepted=True,
            action_type=intent.action_type,
            reason="accepted",
            event_payload={
                "agent_id": intent.agent_id,
                "location_id": agent.location_id if agent else None,
                **intent.payload,
            },
            rule_evaluation=rule_evaluation,
            governance_execution=governance_execution,
        )

    def _resolve_free_action(
        self,
        world: WorldState,
        intent: ActionIntent,
        *,
        rule_evaluation: RuleEvaluationResult | None,
        governance_execution: GovernanceExecutionResult | None,
    ) -> ActionResult:
        """Handle free actions (trade, gift, craft, etc.).

        Free actions are accepted and marked with consequence_source='pending'.
        The actual state changes are generated later by the ConsequenceGenerator
        during persistence.
        """
        agent = world.get_agent(intent.agent_id)
        if agent is None:
            return self._build_result(
                False,
                intent.action_type,
                "agent_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": None,
                    **intent.payload,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        # Basic validation: if target_agent_id is provided, target must be nearby
        if intent.target_agent_id:
            target = world.get_agent(intent.target_agent_id)
            if target is None:
                return self._build_result(
                    False,
                    intent.action_type,
                    "target_agent_not_found",
                    event_payload={
                        "agent_id": intent.agent_id,
                        "location_id": agent.location_id,
                        "target_agent_id": intent.target_agent_id,
                        **intent.payload,
                    },
                    rule_evaluation=rule_evaluation,
                    governance_execution=governance_execution,
                )
            if agent.location_id != target.location_id:
                return self._build_result(
                    False,
                    intent.action_type,
                    "target_not_nearby",
                    event_payload={
                        "agent_id": intent.agent_id,
                        "location_id": agent.location_id,
                        "target_agent_id": intent.target_agent_id,
                        **intent.payload,
                    },
                    rule_evaluation=rule_evaluation,
                    governance_execution=governance_execution,
                )

        # Build event payload with free action metadata
        event_payload = {
            "agent_id": intent.agent_id,
            "location_id": agent.location_id,
            "target_agent_id": intent.target_agent_id,
            "raw_intent": intent.raw_intent,
            "free_action_payload": intent.payload,
            "consequence_source": "pending",  # Marked for ConsequenceGenerator
            **intent.payload,
        }

        return self._build_result(
            accepted=True,
            action_type=intent.action_type,
            reason="free_action_accepted",
            event_payload=event_payload,
            rule_evaluation=rule_evaluation,
            governance_execution=governance_execution,
        )

    def _resolve_move(
        self,
        world: WorldState,
        intent: ActionIntent,
        *,
        rule_evaluation: RuleEvaluationResult | None,
        governance_execution: GovernanceExecutionResult | None,
    ) -> ActionResult:
        agent = world.get_agent(intent.agent_id)
        if agent is None:
            return self._build_result(
                False,
                "move",
                "agent_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": None,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        if intent.target_location_id is None:
            return self._build_result(
                False,
                "move",
                "missing_target_location",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        destination = world.get_location(intent.target_location_id)
        if destination is None:
            return self._build_result(
                False,
                "move",
                "location_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    "to_location_id": intent.target_location_id,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        if agent.location_id == intent.target_location_id:
            return self._build_result(
                False,
                "move",
                "already_at_location",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    "to_location_id": intent.target_location_id,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        if len(destination.occupants) >= destination.capacity:
            return self._build_result(
                False,
                "move",
                "location_full",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    "to_location_id": intent.target_location_id,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        origin_id = agent.location_id
        world.move_agent(intent.agent_id, intent.target_location_id)
        return self._build_result(
            accepted=True,
            action_type="move",
            reason="accepted",
            event_payload={
                "agent_id": intent.agent_id,
                "from_location_id": origin_id,
                "to_location_id": intent.target_location_id,
            },
            rule_evaluation=rule_evaluation,
            governance_execution=governance_execution,
        )

    def _resolve_talk(
        self,
        world: WorldState,
        intent: ActionIntent,
        *,
        rule_evaluation: RuleEvaluationResult | None,
        governance_execution: GovernanceExecutionResult | None,
    ) -> ActionResult:
        agent = world.get_agent(intent.agent_id)
        target = self._resolve_target_agent(world, intent.target_agent_id)
        requested_target_agent_id = intent.target_agent_id
        if agent is None:
            return self._build_result(
                False,
                "talk",
                "agent_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": None,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )
        if target is None:
            return self._build_result(
                False,
                "talk",
                "target_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    "target_agent_id": None,
                    "requested_target_agent_id": requested_target_agent_id,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )
        if agent.location_id != target.location_id:
            event_payload = {
                "agent_id": intent.agent_id,
                "location_id": agent.location_id,
                "target_agent_id": target.id,
            }
            if requested_target_agent_id and requested_target_agent_id != target.id:
                event_payload["requested_target_agent_id"] = requested_target_agent_id
            return self._build_result(
                False,
                "talk",
                "target_not_nearby",
                event_payload=event_payload,
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        # Enforce turn-based conversation: if either participant has already
        # spoken this tick, reject this intent so the other side receives the
        # message in next-tick recent_events and can reply coherently.
        if intent.agent_id in self._talked_agents or target.id in self._talked_agents:
            return self._build_result(
                False,
                "talk",
                "conversation_turn_taken",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    "target_agent_id": target.id,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        self._talked_agents.add(intent.agent_id)
        self._talked_agents.add(target.id)

        event_payload = {
            **intent.payload,
            "agent_id": intent.agent_id,
            "target_agent_id": target.id,
            "location_id": agent.location_id,
            "message": intent.payload.get("message") or "",
            "conversation_event_type": "speech",
            "speaker_agent_id": intent.agent_id,
        }
        self._append_conversation_metadata(intent.agent_id, event_payload)

        return self._build_result(
            accepted=True,
            action_type="talk",
            reason="accepted",
            event_payload=event_payload,
            rule_evaluation=rule_evaluation,
            governance_execution=governance_execution,
        )

    def _resolve_target_agent(
        self,
        world: WorldState,
        raw_target_agent_id: str | None,
    ):
        if raw_target_agent_id is None:
            return None

        candidate = raw_target_agent_id.strip()
        if not candidate:
            return None

        exact = world.get_agent(candidate)
        if exact is not None:
            return exact

        normalized_candidates = [candidate.lower()]
        candidate_tail = candidate.rsplit("-", 1)[-1].strip().lower()
        if candidate_tail and candidate_tail not in normalized_candidates:
            normalized_candidates.append(candidate_tail)

        matched = []
        for agent in world.agents.values():
            agent_id_lower = agent.id.lower()
            agent_name_lower = agent.name.lower()
            agent_suffix_lower = agent.id.rsplit("-", 1)[-1].lower()
            if any(
                normalized == agent_id_lower
                or normalized == agent_name_lower
                or normalized == agent_suffix_lower
                for normalized in normalized_candidates
            ):
                matched.append(agent)

        if len(matched) == 1:
            return matched[0]
        return None

    def _resolve_work(
        self,
        world: WorldState,
        intent: ActionIntent,
        *,
        rule_evaluation: RuleEvaluationResult | None,
        governance_execution: GovernanceExecutionResult | None,
    ) -> ActionResult:
        agent = world.get_agent(intent.agent_id)
        if agent is None:
            return self._build_result(
                False,
                "work",
                "agent_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": None,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        location = world.get_location(agent.location_id)
        location_type = location.location_type if location is not None else None
        is_at_workplace = bool(agent.workplace_id) and agent.location_id == agent.workplace_id
        work_friendly_location = location_type in {"office", "hospital", "cafe", "shop"}

        # Soft guard: if an agent is at home or otherwise lacks a credible work
        # context, convert the action into rest instead of persisting work@home.
        if not is_at_workplace and not work_friendly_location:
            return self._build_result(
                accepted=True,
                action_type="rest",
                reason="downgraded_invalid_work_context",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    **intent.payload,
                },
                rule_evaluation=rule_evaluation,
                governance_execution=governance_execution,
            )

        return self._build_result(
            accepted=True,
            action_type="work",
            reason="accepted",
            event_payload={
                "agent_id": intent.agent_id,
                "location_id": agent.location_id,
                **intent.payload,
            },
            rule_evaluation=rule_evaluation,
            governance_execution=governance_execution,
        )

    def _evaluate_rules(
        self,
        world: WorldState,
        intent: ActionIntent,
    ) -> RuleEvaluationResult | None:
        if self._world_design_package is None:
            return None
        return evaluate_rules(world=world, intent=intent, package=self._world_design_package)

    def _execute_governance(
        self,
        world: WorldState,
        intent: ActionIntent,
        rule_evaluation: RuleEvaluationResult | None,
    ) -> GovernanceExecutionResult | None:
        if self._world_design_package is None:
            return None
        return execute_governance(
            world=world,
            intent=intent,
            rule_evaluation=rule_evaluation,
            package=self._world_design_package,
        )

    def _build_rule_rejection(
        self,
        current_location_id: str | None,
        intent: ActionIntent,
        rule_evaluation: RuleEvaluationResult | None,
        governance_execution: GovernanceExecutionResult | None,
    ) -> ActionResult:
        event_payload = {
            "agent_id": intent.agent_id,
            "location_id": current_location_id,
            **intent.payload,
        }
        if intent.target_location_id is not None:
            event_payload["to_location_id"] = intent.target_location_id
        if intent.target_agent_id is not None:
            event_payload["target_agent_id"] = intent.target_agent_id
        return self._build_result(
            accepted=False,
            action_type=intent.action_type,
            reason=(
                (governance_execution.reason if governance_execution is not None else None)
                or (rule_evaluation.reason if rule_evaluation is not None else None)
                or (
                    governance_execution.decision
                    if governance_execution is not None
                    else intent.action_type
                )
            ),
            event_payload=event_payload,
            rule_evaluation=rule_evaluation,
            governance_execution=governance_execution,
        )

    def _build_result(
        self,
        accepted: bool,
        action_type: str,
        reason: str,
        event_payload: dict[str, Any],
        *,
        rule_evaluation: RuleEvaluationResult | None,
        governance_execution: GovernanceExecutionResult | None,
    ) -> ActionResult:
        payload = dict(event_payload)
        if rule_evaluation is not None:
            payload["rule_evaluation"] = rule_evaluation.model_dump()
        if governance_execution is not None:
            payload["governance_execution"] = governance_execution.model_dump()
        return ActionResult(
            accepted=accepted,
            action_type=action_type,
            reason=reason,
            event_payload=payload,
            rule_evaluation=rule_evaluation,
            governance_execution=governance_execution,
        )

    def _append_conversation_metadata(
        self,
        agent_id: str,
        event_payload: dict[str, Any],
    ) -> None:
        if conversation_id := self._conversation_ids.get(agent_id):
            event_payload["conversation_id"] = conversation_id
        if conversation_role := self._conversation_roles.get(agent_id):
            event_payload["conversation_role"] = conversation_role
        if participant_ids := self._conversation_participants.get(agent_id):
            event_payload["participant_ids"] = participant_ids
