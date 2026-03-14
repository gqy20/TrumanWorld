from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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


@dataclass
class ActionResult:
    accepted: bool
    action_type: str
    reason: str
    event_payload: dict[str, Any] = field(default_factory=dict)


class ActionResolver:
    """Validates and applies agent action intents.

    Maintains a per-tick set of agents already involved in a talk exchange
    to enforce turn-based conversation: within a single tick only one side
    of a pair may initiate talk, so the other side will see the message in
    their next-tick recent_events and can reply naturally.
    """

    SUPPORTED_ACTIONS = {"move", "rest", "work", "talk"}

    def __init__(self) -> None:
        # Agents that have completed (accepted) a talk this tick — blocks further talk.
        self._talked_agents: set[str] = set()
        # Agents pre-registered as talk targets this tick — blocks non-talk actions.
        self._prefilled_targets: set[str] = set()
        # Scheduler-provided conversation roles for this tick.
        self._conversation_roles: dict[str, str] = {}
        self._conversation_ids: dict[str, str] = {}
        self._conversation_participants: dict[str, list[str]] = {}

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
        agent = world.get_agent(intent.agent_id)
        if agent is None:
            return ActionResult(
                False,
                intent.action_type,
                "agent_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": None,
                    **intent.payload,
                },
            )

        if intent.action_type not in self.SUPPORTED_ACTIONS:
            return ActionResult(
                False,
                intent.action_type,
                "unsupported_action",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    **intent.payload,
                },
            )

        if self._conversation_roles.get(intent.agent_id) == "listener":
            if intent.action_type == "talk":
                event_payload = {
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    "target_agent_id": intent.target_agent_id,
                }
                self._append_conversation_metadata(intent.agent_id, event_payload)
                return ActionResult(
                    False,
                    intent.action_type,
                    "conversation_turn_taken",
                    event_payload=event_payload,
                )

        # If this agent is pre-registered as a talk target this tick,
        # suppress non-talk actions so no spurious rest/work/move appears
        # alongside the talk event in the timeline.
        if intent.agent_id in self._prefilled_targets and intent.action_type != "talk":
            event_payload = {
                "agent_id": intent.agent_id,
                "location_id": agent.location_id,
            }
            self._append_conversation_metadata(intent.agent_id, event_payload)
            return ActionResult(
                False,
                intent.action_type,
                "agent_in_conversation",
                event_payload=event_payload,
            )

        if intent.action_type == "move":
            return self._resolve_move(world, intent)
        if intent.action_type == "talk":
            return self._resolve_talk(world, intent)
        if intent.action_type == "work":
            return self._resolve_work(world, intent)

        # rest and other actions
        return ActionResult(
            accepted=True,
            action_type=intent.action_type,
            reason="accepted",
            event_payload={
                "agent_id": intent.agent_id,
                "location_id": agent.location_id if agent else None,
                **intent.payload,
            },
        )

    def _resolve_move(self, world: WorldState, intent: ActionIntent) -> ActionResult:
        agent = world.get_agent(intent.agent_id)
        if agent is None:
            return ActionResult(
                False,
                "move",
                "agent_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": None,
                },
            )

        if intent.target_location_id is None:
            return ActionResult(
                False,
                "move",
                "missing_target_location",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                },
            )

        destination = world.get_location(intent.target_location_id)
        if destination is None:
            return ActionResult(
                False,
                "move",
                "location_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    "to_location_id": intent.target_location_id,
                },
            )

        if agent.location_id == intent.target_location_id:
            return ActionResult(
                False,
                "move",
                "already_at_location",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    "to_location_id": intent.target_location_id,
                },
            )

        if len(destination.occupants) >= destination.capacity:
            return ActionResult(
                False,
                "move",
                "location_full",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    "to_location_id": intent.target_location_id,
                },
            )

        origin_id = agent.location_id
        world.move_agent(intent.agent_id, intent.target_location_id)
        return ActionResult(
            accepted=True,
            action_type="move",
            reason="accepted",
            event_payload={
                "agent_id": intent.agent_id,
                "from_location_id": origin_id,
                "to_location_id": intent.target_location_id,
            },
        )

    def _resolve_talk(self, world: WorldState, intent: ActionIntent) -> ActionResult:
        agent = world.get_agent(intent.agent_id)
        target = self._resolve_target_agent(world, intent.target_agent_id)
        requested_target_agent_id = intent.target_agent_id
        if agent is None:
            return ActionResult(
                False,
                "talk",
                "agent_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": None,
                },
            )
        if target is None:
            return ActionResult(
                False,
                "talk",
                "target_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    "target_agent_id": None,
                    "requested_target_agent_id": requested_target_agent_id,
                },
            )
        if agent.location_id != target.location_id:
            event_payload = {
                "agent_id": intent.agent_id,
                "location_id": agent.location_id,
                "target_agent_id": target.id,
            }
            if requested_target_agent_id and requested_target_agent_id != target.id:
                event_payload["requested_target_agent_id"] = requested_target_agent_id
            return ActionResult(
                False,
                "talk",
                "target_not_nearby",
                event_payload=event_payload,
            )

        # Enforce turn-based conversation: if either participant has already
        # spoken this tick, reject this intent so the other side receives the
        # message in next-tick recent_events and can reply coherently.
        if intent.agent_id in self._talked_agents or target.id in self._talked_agents:
            return ActionResult(
                False,
                "talk",
                "conversation_turn_taken",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    "target_agent_id": target.id,
                },
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

        return ActionResult(
            accepted=True,
            action_type="talk",
            reason="accepted",
            event_payload=event_payload,
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

    def _resolve_work(self, world: WorldState, intent: ActionIntent) -> ActionResult:
        agent = world.get_agent(intent.agent_id)
        if agent is None:
            return ActionResult(
                False,
                "work",
                "agent_not_found",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": None,
                },
            )

        location = world.get_location(agent.location_id)
        location_type = location.location_type if location is not None else None
        is_at_workplace = bool(agent.workplace_id) and agent.location_id == agent.workplace_id
        work_friendly_location = location_type in {"office", "hospital", "cafe", "shop"}

        # Soft guard: if an agent is at home or otherwise lacks a credible work
        # context, convert the action into rest instead of persisting work@home.
        if not is_at_workplace and not work_friendly_location:
            return ActionResult(
                accepted=True,
                action_type="rest",
                reason="downgraded_invalid_work_context",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    **intent.payload,
                },
            )

        return ActionResult(
            accepted=True,
            action_type="work",
            reason="accepted",
            event_payload={
                "agent_id": intent.agent_id,
                "location_id": agent.location_id,
                **intent.payload,
            },
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
