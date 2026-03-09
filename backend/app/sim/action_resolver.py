from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agent.providers import build_default_talk_message
from app.sim.world import WorldState


@dataclass
class ActionIntent:
    agent_id: str
    action_type: str
    target_location_id: str | None = None
    target_agent_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


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
        # Tracks all agent IDs that have already participated in an accepted
        # talk event this tick (as actor OR target).  Reset each tick via
        # SimulationRunner.
        self._talked_agents: set[str] = set()

    def reset_tick(self) -> None:
        """Clear the talked-agents set at the start of each tick."""
        self._talked_agents.clear()

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

        # If this agent is already participating in a talk this tick (as target),
        # suppress any other action so the timeline doesn't show a spurious rest/move.
        if intent.agent_id in self._talked_agents and intent.action_type != "talk":
            return ActionResult(
                False,
                intent.action_type,
                "agent_in_conversation",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                },
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
        target = world.get_agent(intent.target_agent_id or "")
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
                    "target_agent_id": intent.target_agent_id,
                },
            )
        if agent.location_id != target.location_id:
            return ActionResult(
                False,
                "talk",
                "target_not_nearby",
                event_payload={
                    "agent_id": intent.agent_id,
                    "location_id": agent.location_id,
                    "target_agent_id": intent.target_agent_id,
                },
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

        return ActionResult(
            accepted=True,
            action_type="talk",
            reason="accepted",
            event_payload={
                "agent_id": intent.agent_id,
                "target_agent_id": target.id,
                "location_id": agent.location_id,
                "message": intent.payload.get("message") or build_default_talk_message(),
                **intent.payload,
            },
        )

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
