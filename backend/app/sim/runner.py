from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.sim.action_resolver import ActionIntent, ActionResolver, ActionResult
from app.sim.conversation_scheduler import ConversationScheduler
from app.sim.world import WorldState


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

        intent_list = list(intents)
        self.resolver.reset_tick()
        _, assignments = self.conversation_scheduler.schedule(intent_list, self.world)
        listener_ids = {
            assignment.agent_id
            for assignment in assignments.values()
            if assignment.role == "listener"
        }
        self.resolver.prefill_conversation_targets(listener_ids)
        for intent in intent_list:
            result = self.resolver.resolve(self.world, intent)
            if result.accepted:
                accepted.append(result)
            else:
                rejected.append(result)

        advanced = self.world.advance_tick()
        world_time = advanced.current_time.isoformat()
        self.tick_no += advanced.tick_delta
        return TickResult(
            tick_no=self.tick_no,
            world_time=world_time,
            tick_delta=advanced.tick_delta,
            accepted=accepted,
            rejected=rejected,
        )
