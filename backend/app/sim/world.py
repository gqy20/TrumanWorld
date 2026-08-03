from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from app.scenario.embodiment_config import (
    ActivityDefinition,
    EmbodimentCatalog,
    SocialSpatialConfig,
)
from app.sim.activity import ActivityInstance, ActivityStepInstance, create_activity
from app.sim.movement import AgentMovementState, create_agent_movement
from app.sim.world_map import WorldMapTopology, build_world_map


@dataclass
class LocationState:
    id: str
    name: str
    capacity: int = 10
    occupants: set[str] = field(default_factory=set)
    location_type: str | None = None
    x: int | None = None
    y: int | None = None


@dataclass
class AgentState:
    id: str
    name: str
    location_id: str
    status: dict[str, Any] = field(default_factory=dict)
    occupation: str | None = None
    workplace_id: str | None = None
    movement: AgentMovementState | None = None
    activity: ActivityInstance | None = None


@dataclass(frozen=True)
class ActivityTransition:
    event_type: str
    activity: ActivityInstance
    occurred_at_world_time: datetime
    activity_status: str
    step_index: int
    step_id: str | None = None
    action: str | None = None
    resource_id: str | None = None
    zone_id: str | None = None
    queue_position: int | None = None


@dataclass(frozen=True)
class TickAdvance:
    current_time: datetime
    tick_delta: int
    completed_movements: tuple[AgentMovementState, ...] = ()
    activity_transitions: tuple[ActivityTransition, ...] = ()


@dataclass
class ActiveConversationState:
    id: str
    location_id: str
    participant_ids: list[str]
    active_speaker_id: str
    last_tick_no: int
    last_message_summary: str | None = None
    last_proposal: str | None = None
    open_question: str | None = None
    repeat_count: int = 0
    started_tick_no: int = 0
    turn_count: int = 0
    phase: str = "open"


@dataclass
class InteractionEdgeState:
    conversation_id: str
    source_agent_id: str
    target_agent_id: str
    last_outgoing_message: str | None = None
    last_incoming_message: str | None = None
    last_outgoing_tick_no: int | None = None
    last_incoming_tick_no: int | None = None
    last_outgoing_act: str | None = None
    last_incoming_act: str | None = None
    unresolved_item: str | None = None
    closure_state: str = "open"
    novelty_since_last_turn: bool = True
    redundancy_risk: float = 0.0


@dataclass
class RestrictionState:
    """Represents an active restriction in the world state."""

    id: str
    restriction_type: str
    scope_type: str
    scope_value: str | None
    start_tick: int
    end_tick: int | None
    reason: str | None = None


class WorldState:
    """Authoritative in-memory world state facade."""

    def __init__(
        self,
        current_time: datetime,
        current_tick: int = 0,
        tick_minutes: int = 5,
        locations: dict[str, LocationState] | None = None,
        agents: dict[str, AgentState] | None = None,
        world_effects: dict[str, Any] | None = None,
        relationship_contexts: dict[str, dict[str, dict[str, Any]]] | None = None,
        active_conversations: dict[str, ActiveConversationState] | None = None,
        interaction_edges: dict[str, InteractionEdgeState] | None = None,
        active_restrictions: dict[str, list[RestrictionState]] | None = None,
        sleep_start_hour: int = 23,
        sleep_end_hour: int = 6,
        topology: WorldMapTopology | None = None,
        embodiment_catalog: EmbodimentCatalog | None = None,
        world_seed: int = 0,
        social_spatial_config: SocialSpatialConfig | None = None,
        location_zone_ids: dict[str, str] | None = None,
    ) -> None:
        self.current_time = current_time
        self.current_tick = current_tick
        self.tick_minutes = tick_minutes
        self.locations = locations or {}
        self.agents = agents or {}
        self.world_effects = world_effects or {}
        self.relationship_contexts = relationship_contexts or {}
        self.active_conversations = active_conversations or {}
        self.interaction_edges = interaction_edges or {}
        self.active_restrictions = active_restrictions or {}
        self.sleep_start_hour = sleep_start_hour
        self.sleep_end_hour = sleep_end_hour
        self.topology = topology
        self.embodiment_catalog = embodiment_catalog
        self.world_seed = world_seed
        self.social_spatial_config = social_spatial_config
        self.location_zone_ids = location_zone_ids or {}
        self._pending_activity_transitions: list[ActivityTransition] = []
        self._reconcile_resource_claims()

    def snapshot(self) -> dict[str, Any]:
        return {
            "current_time": self.current_time.isoformat(),
            "current_tick": self.current_tick,
            "tick_minutes": self.tick_minutes,
            "clock": self.time_context(),
            "locations": {
                location_id: {
                    "name": location.name,
                    "capacity": location.capacity,
                    "occupants": sorted(location.occupants),
                    "location_type": location.location_type,
                    "x": location.x,
                    "y": location.y,
                }
                for location_id, location in self.locations.items()
            },
            "world_effects": deepcopy(self.world_effects),
            "relationship_contexts": deepcopy(self.relationship_contexts),
            "active_conversations": {
                conversation_id: {
                    "location_id": conversation.location_id,
                    "participant_ids": list(conversation.participant_ids),
                    "active_speaker_id": conversation.active_speaker_id,
                    "last_tick_no": conversation.last_tick_no,
                    "last_message_summary": conversation.last_message_summary,
                    "last_proposal": conversation.last_proposal,
                    "open_question": conversation.open_question,
                    "repeat_count": conversation.repeat_count,
                    "started_tick_no": conversation.started_tick_no,
                    "turn_count": conversation.turn_count,
                    "phase": conversation.phase,
                }
                for conversation_id, conversation in self.active_conversations.items()
            },
            "interaction_edges": {
                edge_key: {
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
                for edge_key, edge in self.interaction_edges.items()
            },
            "agents": {
                agent_id: {
                    "name": agent.name,
                    "location_id": agent.location_id,
                    "status": deepcopy(agent.status),
                    "occupation": agent.occupation,
                    "workplace_id": agent.workplace_id,
                    "movement": agent.movement.to_dict() if agent.movement else None,
                    "activity": (
                        agent.activity.to_dict(world_time=self.current_time)
                        if agent.activity
                        else None
                    ),
                }
                for agent_id, agent in self.agents.items()
            },
        }

    def time_context(self) -> dict[str, Any]:
        weekday = self.current_time.weekday()
        minute_of_day = (self.current_time.hour * 60) + self.current_time.minute
        return {
            "current_time": self.current_time.isoformat(),
            "current_tick": self.current_tick,
            "tick_minutes": self.tick_minutes,
            "day_index": self._day_index(),
            "weekday": weekday,
            "weekday_name": self._weekday_name(weekday),
            "hour": self.current_time.hour,
            "minute": self.current_time.minute,
            "minute_of_day": minute_of_day,
            "is_weekend": weekday >= 5,
            "time_period": self._time_period(),
        }

    def advance_tick(self) -> TickAdvance:
        next_time = self.current_time + timedelta(minutes=self.tick_minutes)
        has_continuous_interval = any(
            agent.movement is not None or (agent.activity is not None and agent.activity.is_active)
            for agent in self.agents.values()
        )
        wake_time = None if has_continuous_interval else self._resolve_sleep_jump(next_time)
        if wake_time is not None:
            advanced_minutes = int((wake_time - self.current_time).total_seconds() // 60)
            tick_delta = advanced_minutes // self.tick_minutes
            self.current_time = wake_time
        else:
            tick_delta = 1
            self.current_time = next_time

        self.current_tick += tick_delta
        completed_movements, activity_transitions = self.complete_due_intervals()
        return TickAdvance(
            current_time=self.current_time,
            tick_delta=tick_delta,
            completed_movements=tuple(completed_movements),
            activity_transitions=tuple(activity_transitions),
        )

    def get_agent(self, agent_id: str) -> AgentState | None:
        return self.agents.get(agent_id)

    def get_location(self, location_id: str) -> LocationState | None:
        return self.locations.get(location_id)

    def add_restriction(self, agent_id: str, restriction: RestrictionState) -> None:
        """Add an active restriction for an agent."""
        if agent_id not in self.active_restrictions:
            self.active_restrictions[agent_id] = []
        self.active_restrictions[agent_id].append(restriction)

    def has_restriction(
        self,
        agent_id: str,
        restriction_type: str,
        scope_value: str | None = None,
    ) -> bool:
        """Check if agent has an active restriction of given type."""
        if agent_id not in self.active_restrictions:
            return False
        tick = self.current_tick
        for restriction in self.active_restrictions[agent_id]:
            if restriction.restriction_type != restriction_type:
                continue
            if scope_value is not None and restriction.scope_value != scope_value:
                continue
            # Check if restriction is active at current tick
            if restriction.start_tick > tick:
                continue
            if restriction.end_tick is not None and restriction.end_tick < tick:
                continue
            return True
        return False

    def move_agent(self, agent_id: str, destination_id: str) -> None:
        agent = self.agents[agent_id]
        origin = self.locations[agent.location_id]
        destination = self.locations[destination_id]

        origin.occupants.discard(agent_id)
        destination.occupants.add(agent_id)
        agent.location_id = destination_id

    def start_agent_movement(
        self,
        agent_id: str,
        destination_id: str,
        *,
        activity_id: str | None = None,
    ) -> AgentMovementState:
        agent = self.agents[agent_id]
        origin_id = agent.location_id
        topology = self.topology or build_world_map(self.locations.values())
        route = (
            topology.route_between_locations(origin_id, destination_id)
            if origin_id in topology.location_entrances
            and destination_id in topology.location_entrances
            else None
        )
        movement = create_agent_movement(
            agent_id=agent_id,
            from_location_id=origin_id,
            to_location_id=destination_id,
            # Intents are committed by the tick that advance_tick() is about to publish.
            # Aligning the movement interval with that public tick keeps a fresh snapshot
            # at progress 0 instead of making the client skip the first half of the route.
            started_tick=self.current_tick + 1,
            route_node_ids=route.node_ids if route else (),
            distance=route.distance if route else 0.0,
            # Intents are committed at the upcoming public cognition boundary.
            started_at_world_time=self.current_time + timedelta(minutes=self.tick_minutes),
            tick_seconds=self.tick_minutes * 60,
            activity_id=activity_id,
        )
        self.locations[origin_id].occupants.discard(agent_id)
        agent.movement = movement
        return movement

    def start_agent_activity(
        self,
        agent_id: str,
        activity_type: str,
        *,
        duration_seconds: float | None = None,
        target_location_id: str | None = None,
        parent_intent_id: str | None = None,
    ) -> ActivityInstance:
        agent = self.agents[agent_id]
        requires_navigation = bool(target_location_id and target_location_id != agent.location_id)
        started_at = self.current_time + timedelta(minutes=self.tick_minutes)
        definition = self.get_activity_definition(activity_type)
        steps = self._build_activity_steps(
            agent_id=agent_id,
            activity_type=activity_type,
            definition=definition,
            target_location_id=target_location_id or agent.location_id,
            started_at=started_at,
        )
        resolved_duration = (
            sum(step.duration_seconds for step in steps)
            if steps
            else max(0.0, float(duration_seconds or 0.0))
        )
        activity = create_activity(
            agent_id=agent_id,
            activity_type=activity_type,
            started_at_world_time=started_at,
            duration_seconds=resolved_duration,
            target_entity_id=target_location_id,
            requires_navigation=requires_navigation,
            parent_intent_id=parent_intent_id,
            steps=steps,
            interruptible=definition.interruptible if definition is not None else True,
        )
        agent.activity = activity
        if requires_navigation and target_location_id is not None:
            self.start_agent_movement(
                agent_id,
                target_location_id,
                activity_id=activity.id,
            )
        elif steps:
            activity.status = "planned"
            activity.expected_end_world_time = None
            self._start_current_activity_step(activity, started_at)
        return activity

    def interrupt_agent_activity(self, agent_id: str, reason: str) -> ActivityInstance | None:
        agent = self.agents[agent_id]
        activity = agent.activity
        if activity is None or not activity.is_active or not activity.interruptible:
            return None
        released_resource_ids = tuple(activity.claimed_resource_ids)
        self._release_activity_resources(activity)
        activity.interrupt(reason)
        agent.movement = None
        if agent.location_id in self.locations:
            self.locations[agent.location_id].occupants.add(agent_id)
        for resource_id in released_resource_ids:
            self._pending_activity_transitions.append(
                self._activity_transition(
                    "resource_released",
                    activity,
                    self.current_time,
                    resource_id=resource_id,
                )
            )
        self._promote_waiting_activities(self.current_time)
        return activity

    def get_activity_definition(self, activity_type: str) -> ActivityDefinition | None:
        if self.embodiment_catalog is None:
            return None
        return self.embodiment_catalog.get_activity(activity_type)

    def validate_activity_target(
        self,
        activity_type: str,
        target_location_id: str | None,
        fallback_location_id: str,
    ) -> str | None:
        definition = self.get_activity_definition(activity_type)
        if self.embodiment_catalog is not None and definition is None:
            return "unknown_activity_type"
        if definition is None or not definition.requirements.location_types:
            location = self.locations.get(target_location_id or fallback_location_id)
        else:
            location = self.locations.get(target_location_id or fallback_location_id)
            if location is None:
                return "location_not_found"
            if location.location_type not in definition.requirements.location_types:
                return "activity_location_type_mismatch"
        if definition is None or self.embodiment_catalog is None or location is None:
            return None
        for step in definition.steps:
            if step.resource is None:
                continue
            if not self.embodiment_catalog.resources_for(
                location_id=location.id,
                object_types=tuple(step.resource.object_types),
                slot_kind=step.resource.slot_kind,
            ):
                return "activity_resource_unavailable"
        return None

    def complete_due_intervals(
        self,
    ) -> tuple[list[AgentMovementState], list[ActivityTransition]]:
        completed: list[AgentMovementState] = []
        transitions = self._pending_activity_transitions
        self._pending_activity_transitions = []
        ordered_agents = sorted(
            self.agents.values(),
            key=lambda item: (
                item.movement.expected_arrival_world_time
                if item.movement and item.movement.expected_arrival_world_time
                else self.current_time,
                item.id,
            ),
        )
        for agent in ordered_agents:
            movement = agent.movement
            if movement is None or not movement.arrives_by(self.current_time, self.current_tick):
                continue
            destination = self.locations.get(movement.to_location_id)
            if destination is None:
                continue
            agent.location_id = destination.id
            agent.movement = None
            destination.occupants.add(agent.id)
            completed.append(movement)
            activity = agent.activity
            if (
                activity is not None
                and activity.id == movement.activity_id
                and activity.status == "navigating"
            ):
                arrival_time = movement.expected_arrival_world_time or self.current_time
                if activity.steps:
                    transitions.append(
                        self._activity_transition(
                            "activity_step_completed",
                            activity,
                            arrival_time,
                            step_id="navigate",
                            action="navigate",
                        )
                    )
                    self._start_current_activity_step(activity, arrival_time, transitions)
                else:
                    transitions.append(
                        self._activity_transition("activity_step_completed", activity, arrival_time)
                    )
                    activity.start_performing(arrival_time)
                    transitions.append(
                        self._activity_transition("activity_step_started", activity, arrival_time)
                    )

        performing = sorted(
            (
                agent.activity
                for agent in self.agents.values()
                if agent.activity is not None
                and not agent.activity.steps
                and agent.activity.status == "performing"
                and agent.activity.expected_end_world_time is not None
                and agent.activity.expected_end_world_time <= self.current_time
            ),
            key=lambda item: (item.expected_end_world_time, item.id),
        )
        for activity in performing:
            completed_at = activity.expected_end_world_time or self.current_time
            activity.complete()
            transitions.append(
                self._activity_transition("activity_completed", activity, completed_at)
            )

        self._complete_configured_activity_steps(transitions)
        self._update_queue_positions()
        # Python's stable sort preserves the causal append order for transitions sharing
        # an exact timestamp (step completed -> step started -> activity completed).
        transitions.sort(key=lambda item: item.occurred_at_world_time)
        return completed, transitions

    def _build_activity_steps(
        self,
        *,
        agent_id: str,
        activity_type: str,
        definition: ActivityDefinition | None,
        target_location_id: str,
        started_at: datetime,
    ) -> tuple[ActivityStepInstance, ...]:
        if definition is None or self.embodiment_catalog is None:
            return ()
        steps = []
        for step in definition.steps:
            candidate_resource_ids: tuple[str, ...] = ()
            if step.resource is not None:
                candidate_resource_ids = tuple(
                    resource.id
                    for resource in self.embodiment_catalog.resources_for(
                        location_id=target_location_id,
                        object_types=tuple(step.resource.object_types),
                        slot_kind=step.resource.slot_kind,
                    )
                )
            duration_seconds = self.embodiment_catalog.resolve_duration(
                step.duration_seconds,
                world_seed=self.world_seed,
                agent_id=agent_id,
                activity_type=activity_type,
                step_id=step.id,
                started_at_iso=started_at.isoformat(),
            )
            steps.append(
                ActivityStepInstance(
                    id=step.id,
                    action=step.action,
                    status="pending",
                    duration_seconds=duration_seconds,
                    visual_state=step.visual_state,
                    resource_required=step.resource is not None,
                    candidate_resource_ids=candidate_resource_ids,
                    release_after=step.release_after,
                )
            )
        return tuple(steps)

    def _start_current_activity_step(
        self,
        activity: ActivityInstance,
        started_at: datetime,
        transitions: list[ActivityTransition] | None = None,
    ) -> None:
        emitted = transitions if transitions is not None else self._pending_activity_transitions
        step = activity.current_step
        if step is None:
            self._complete_configured_activity(activity, started_at, emitted)
            return

        if step.resource_required and step.claimed_resource_id is None:
            resource_id = self._first_available_resource(step.candidate_resource_ids)
            if resource_id is None:
                step.status = "waiting_for_resource"
                activity.status = "waiting_for_resource"
                activity.expected_end_world_time = None
                emitted.append(
                    self._activity_transition(
                        "activity_waiting_for_resource",
                        activity,
                        started_at,
                        step_id=step.id,
                        action=step.action,
                    )
                )
                self._update_queue_positions()
                return
            step.claimed_resource_id = resource_id
            activity.claimed_resource_ids = tuple(
                sorted(set(activity.claimed_resource_ids) | {resource_id})
            )
            resource = self._resource_by_id(resource_id)
            activity.zone_id = resource.zone_id if resource is not None else activity.zone_id
            emitted.append(
                self._activity_transition(
                    "resource_reserved",
                    activity,
                    started_at,
                    step_id=step.id,
                    action=step.action,
                    resource_id=resource_id,
                )
            )

        step.status = "performing"
        step.started_at_world_time = started_at
        step.expected_end_world_time = started_at + timedelta(seconds=step.duration_seconds)
        activity.status = "performing"
        activity.expected_end_world_time = step.expected_end_world_time
        activity.queue_position = None
        emitted.append(
            self._activity_transition(
                "activity_step_started",
                activity,
                started_at,
                step_id=step.id,
                action=step.action,
                resource_id=step.claimed_resource_id,
            )
        )

    def _complete_configured_activity_steps(
        self,
        transitions: list[ActivityTransition],
    ) -> None:
        while True:
            due = sorted(
                (
                    activity
                    for agent in self.agents.values()
                    if (activity := agent.activity) is not None
                    and activity.steps
                    and activity.status == "performing"
                    and activity.current_step is not None
                    and activity.current_step.expected_end_world_time is not None
                    and activity.current_step.expected_end_world_time <= self.current_time
                ),
                key=lambda item: (
                    item.current_step.expected_end_world_time,
                    item.started_at_world_time,
                    item.agent_id,
                    item.id,
                ),
            )
            if not due:
                break
            activity = due[0]
            step = activity.current_step
            if step is None or step.expected_end_world_time is None:
                break
            completed_at = step.expected_end_world_time
            step.status = "completed"
            transitions.append(
                self._activity_transition(
                    "activity_step_completed",
                    activity,
                    completed_at,
                    step_id=step.id,
                    action=step.action,
                    resource_id=step.claimed_resource_id,
                )
            )
            if step.release_after and step.claimed_resource_id is not None:
                resource_id = step.claimed_resource_id
                self._release_step_resource(activity, step)
                transitions.append(
                    self._activity_transition(
                        "resource_released",
                        activity,
                        completed_at,
                        step_id=step.id,
                        action=step.action,
                        resource_id=resource_id,
                    )
                )
            activity.step_index += 1
            if activity.current_step is None:
                self._complete_configured_activity(activity, completed_at, transitions)
            else:
                self._start_current_activity_step(activity, completed_at, transitions)
            self._promote_waiting_activities(completed_at, transitions)

    def _complete_configured_activity(
        self,
        activity: ActivityInstance,
        completed_at: datetime,
        transitions: list[ActivityTransition],
    ) -> None:
        released = tuple(activity.claimed_resource_ids)
        self._release_activity_resources(activity)
        activity.complete()
        activity.expected_end_world_time = completed_at
        activity.queue_position = None
        for resource_id in released:
            transitions.append(
                self._activity_transition(
                    "resource_released", activity, completed_at, resource_id=resource_id
                )
            )
        transitions.append(self._activity_transition("activity_completed", activity, completed_at))

    def _promote_waiting_activities(
        self,
        occurred_at: datetime,
        transitions: list[ActivityTransition] | None = None,
    ) -> None:
        emitted = transitions if transitions is not None else self._pending_activity_transitions
        waiting = sorted(
            (
                activity
                for agent in self.agents.values()
                if (activity := agent.activity) is not None
                and activity.status == "waiting_for_resource"
                and activity.current_step is not None
            ),
            key=lambda item: (item.started_at_world_time, item.agent_id, item.id),
        )
        for activity in waiting:
            step = activity.current_step
            if step is not None and self._first_available_resource(step.candidate_resource_ids):
                step.status = "pending"
                self._start_current_activity_step(activity, occurred_at, emitted)
        self._update_queue_positions()

    def _first_available_resource(self, resource_ids: tuple[str, ...]) -> str | None:
        for resource_id in resource_ids:
            resource = self._resource_by_id(resource_id)
            if resource is None:
                continue
            if self._resource_claim_count(resource_id) < resource.capacity:
                return resource_id
        return None

    def _resource_claim_count(self, resource_id: str) -> int:
        return sum(
            1
            for agent in self.agents.values()
            if agent.activity is not None
            and agent.activity.is_active
            and resource_id in agent.activity.claimed_resource_ids
        )

    def _resource_by_id(self, resource_id: str):
        if self.embodiment_catalog is None:
            return None
        return next(
            (
                resource
                for resource in self.embodiment_catalog.resources
                if resource.id == resource_id
            ),
            None,
        )

    def _release_step_resource(
        self,
        activity: ActivityInstance,
        step: ActivityStepInstance,
    ) -> None:
        resource_id = step.claimed_resource_id
        if resource_id is None:
            return
        step.claimed_resource_id = None
        activity.claimed_resource_ids = tuple(
            item for item in activity.claimed_resource_ids if item != resource_id
        )

    def _release_activity_resources(self, activity: ActivityInstance) -> None:
        for step in activity.steps:
            step.claimed_resource_id = None
        activity.claimed_resource_ids = ()
        activity.zone_id = None

    def _update_queue_positions(self) -> None:
        waiting = sorted(
            (
                activity
                for agent in self.agents.values()
                if (activity := agent.activity) is not None
                and activity.status == "waiting_for_resource"
            ),
            key=lambda item: (item.started_at_world_time, item.agent_id, item.id),
        )
        for index, activity in enumerate(waiting):
            candidates = (
                set(activity.current_step.candidate_resource_ids)
                if activity.current_step
                else set()
            )
            predecessors = sum(
                1
                for previous in waiting[:index]
                if previous.current_step is not None
                and candidates.intersection(previous.current_step.candidate_resource_ids)
            )
            activity.queue_position = predecessors + 1

    def _reconcile_resource_claims(self) -> None:
        if self.embodiment_catalog is None:
            return
        for resource in self.embodiment_catalog.resources:
            claimants = sorted(
                (
                    activity
                    for agent in self.agents.values()
                    if (activity := agent.activity) is not None
                    and activity.is_active
                    and resource.id in activity.claimed_resource_ids
                ),
                key=lambda item: (item.started_at_world_time, item.agent_id, item.id),
            )
            for activity in claimants[resource.capacity :]:
                activity.claimed_resource_ids = tuple(
                    item for item in activity.claimed_resource_ids if item != resource.id
                )
                for step in activity.steps:
                    if step.claimed_resource_id == resource.id:
                        step.claimed_resource_id = None
                        step.status = "waiting_for_resource"
                        step.started_at_world_time = None
                        step.expected_end_world_time = None
                activity.status = "waiting_for_resource"
                activity.expected_end_world_time = None
        self._update_queue_positions()

    def _activity_transition(
        self,
        event_type: str,
        activity: ActivityInstance,
        occurred_at: datetime,
        *,
        step_id: str | None = None,
        action: str | None = None,
        resource_id: str | None = None,
    ) -> ActivityTransition:
        return ActivityTransition(
            event_type=event_type,
            activity=activity,
            occurred_at_world_time=occurred_at,
            activity_status=activity.status,
            step_index=activity.step_index,
            step_id=step_id if step_id is not None else activity.current_step_id,
            action=action if action is not None else activity.current_action,
            resource_id=resource_id,
            zone_id=activity.zone_id,
            queue_position=activity.queue_position,
        )

    def complete_arrived_movements(self) -> list[AgentMovementState]:
        completed, _transitions = self.complete_due_intervals()
        return completed

    def destination_occupancy(self, location_id: str) -> int:
        location = self.locations[location_id]
        reservations = sum(
            1
            for agent in self.agents.values()
            if agent.movement is not None and agent.movement.to_location_id == location_id
        )
        return len(location.occupants) + reservations

    def _day_index(self) -> int:
        return self.current_time.toordinal()

    def _weekday_name(self, weekday: int) -> str:
        names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        return names[weekday]

    def _time_period(self) -> str:
        hour = self.current_time.hour
        if hour < 5:
            return "night"
        if hour < 7:
            return "dawn"
        if hour < 12:
            return "morning"
        if hour < 14:
            return "noon"
        if hour < 18:
            return "afternoon"
        if hour < 21:
            return "evening"
        return "night"

    def _resolve_sleep_jump(self, candidate_time: datetime) -> datetime | None:
        if not self._is_sleep_time(candidate_time):
            return None

        if candidate_time.hour >= self.sleep_start_hour:
            wake_date = (candidate_time + timedelta(days=1)).date()
        else:
            wake_date = candidate_time.date()

        wake_time = datetime.combine(
            wake_date,
            time(self.sleep_end_hour, 0),
            tzinfo=candidate_time.tzinfo,
        )
        return wake_time

    def _is_sleep_time(self, dt: datetime) -> bool:
        hour = dt.hour
        if self.sleep_start_hour <= self.sleep_end_hour:
            return self.sleep_start_hour <= hour < self.sleep_end_hour
        return hour >= self.sleep_start_hour or hour < self.sleep_end_hour
