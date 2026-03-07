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
    """Validates and applies agent action intents."""

    SUPPORTED_ACTIONS = {"move", "rest", "work", "talk"}

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

        if intent.action_type == "move":
            return self._resolve_move(world, intent)
        if intent.action_type == "talk":
            return self._resolve_talk(world, intent)

        # work, rest 等其他动作需要包含 location_id
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
