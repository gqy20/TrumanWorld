"""Persistence logic for simulation ticks.

This module handles persisting agent locations, events, memories, and relationships
after each simulation tick.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.scenario.runtime.world_design import load_world_design_runtime_package
from app.sim.event_utils import build_event
from app.sim.relationship_policy import compute_relationship_delta
from app.sim.memory_constants import calculate_memory_importance, determine_memory_category
from app.sim.runner import TickResult
from app.sim.world import WorldState
from app.store.models import Event, GovernanceRecord, Memory, Relationship, SimulationRun
from app.store.repositories import (
    AgentRepository,
    EventRepository,
    GovernanceRecordRepository,
    LocationRepository,
    MemoryRepository,
    RelationshipRepository,
    RunRepository,
)

if TYPE_CHECKING:
    from app.store.models import Agent


ROUTINE_MEMORY_EVENT_TYPES = {"work", "rest"}
ROUTINE_MEMORY_LOOKBACK_TICKS = 3


class PersistenceManager:
    """Manages persistence of simulation tick results.

    This class is responsible for:
    - Persisting agent locations after movement
    - Creating and storing events (accepted and rejected)
    - Building and storing memories from events
    - Updating relationships based on interactions
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.run_repo = RunRepository(session)
        self.agent_repo = AgentRepository(session)
        self.location_repo = LocationRepository(session)
        self.event_repo = EventRepository(session)
        self.governance_record_repo = GovernanceRecordRepository(session)
        self.memory_repo = MemoryRepository(session)
        self.relationship_repo = RelationshipRepository(session)

    async def persist_tick_results(
        self,
        run_id: str,
        result: TickResult,
        world: WorldState,
        new_tick: int,
    ) -> list[Event]:
        """Persist all tick results including agent locations, events, memories, and relationships.

        Args:
            run_id: The simulation run ID
            result: The tick result containing accepted/rejected actions
            world: The world state after the tick
            new_tick: The new tick number

        Returns:
            List of persisted events for further processing
        """
        # Update agent locations and sync goal with schedule
        agents = await self.agent_repo.list_for_run(run_id)
        for agent in agents:
            state = world.get_agent(agent.id)
            if state is not None:
                agent.current_location_id = state.location_id
                scheduled_goal = _compute_goal_for_schedule(world, agent)
                if scheduled_goal is not None and agent.current_goal != scheduled_goal:
                    agent.current_goal = scheduled_goal
        await self.session.commit()

        # Update tick number
        run = await self.run_repo.get(run_id)
        if run:
            await self.run_repo.update_tick(run, new_tick)

        # Build and persist events
        events = self._build_tick_events(run_id, result)
        if events:
            persisted = await self.event_repo.create_many(events)
            await self.persist_tick_governance_records(run_id, persisted)
            await self.persist_tick_governance_cases(run_id, result, world)
            await self.persist_tick_economic_state(run_id, result, world)
            await self.persist_tick_memories(run_id, persisted)
            await self.persist_tick_relationships(run_id, persisted)
            return persisted
        return []

    async def persist_tick_governance_records(self, run_id: str, events: list[Event]) -> None:
        records: list[GovernanceRecord] = []
        for event in events:
            payload = event.payload or {}
            governance_execution = payload.get("governance_execution")
            if not isinstance(governance_execution, dict):
                continue
            decision = governance_execution.get("decision")
            if decision not in {"record_only", "warn", "block"}:
                continue

            agent_id = payload.get("agent_id") or event.actor_agent_id
            if not isinstance(agent_id, str) or not agent_id:
                continue

            reason = governance_execution.get("reason")
            observation_score = governance_execution.get("observation_score")
            intervention_score = governance_execution.get("intervention_score")
            observed = governance_execution.get("observed")
            matched_signals = governance_execution.get("matched_signals")

            records.append(
                GovernanceRecord(
                    id=str(uuid4()),
                    run_id=run_id,
                    agent_id=agent_id,
                    tick_no=event.tick_no,
                    source_event_id=event.id,
                    location_id=event.location_id,
                    action_type=event.event_type,
                    decision=decision,
                    reason=reason if isinstance(reason, str) else None,
                    observed=bool(observed),
                    observation_score=(
                        float(observation_score)
                        if isinstance(observation_score, (int, float))
                        else 0.0
                    ),
                    intervention_score=(
                        float(intervention_score)
                        if isinstance(intervention_score, (int, float))
                        else 0.0
                    ),
                    metadata_json={
                        "enforcement_action": governance_execution.get("enforcement_action"),
                        "matched_signals": matched_signals
                        if isinstance(matched_signals, list)
                        else [],
                    },
                )
            )

        if records:
            await self.governance_record_repo.create_many(records)

    async def persist_tick_governance_cases(
        self,
        run_id: str,
        result: TickResult,
        world: WorldState,
    ) -> None:
        """Persist governance cases and restrictions from tick results.

        Processes warn/block decisions to create or update cases,
        and generates restrictions when thresholds are met.
        """
        from app.sim.governance_case_service import GovernanceCaseService
        from app.sim.world import RestrictionState

        service = GovernanceCaseService(self.session)

        # Process both accepted and rejected actions
        all_results = list(result.accepted) + list(result.rejected)

        for item in all_results:
            governance_execution = item.governance_execution
            if governance_execution is None:
                continue

            decision = governance_execution.decision
            if decision not in {"warn", "block"}:
                continue

            agent_id = item.event_payload.get("agent_id")
            if not isinstance(agent_id, str) or not agent_id:
                continue

            # Build ActionResult-like object for service
            action_result = item

            # Process governance case
            case = await service.process_governance_record(
                world=world,
                result=action_result,
                run_id=run_id,
                agent_id=agent_id,
                tick_no=result.tick_no,
            )

            # Maybe create restriction
            restriction = await service.maybe_create_restriction(
                world=world,
                result=action_result,
                case=case,
                run_id=run_id,
                agent_id=agent_id,
                tick_no=result.tick_no,
            )

            if restriction is not None:
                # Add restriction to world state for runtime checks
                restriction_state = RestrictionState(
                    id=restriction.id,
                    restriction_type=restriction.restriction_type,
                    scope_type=restriction.scope_type,
                    scope_value=restriction.scope_value,
                    start_tick=restriction.start_tick,
                    end_tick=restriction.end_tick,
                    reason=restriction.reason,
                )
                world.add_restriction(agent_id, restriction_state)

    async def persist_tick_economic_state(
        self,
        run_id: str,
        result: TickResult,
        world: WorldState,
    ) -> None:
        """Persist economic state changes and effect logs from tick results.

        Processes economic effects for all agents:
        - work_income for agents with accepted work actions
        - food decay for agents without income for N ticks
        - employment_status changes for agents with active work_ban
        """
        from app.sim.economic_state_service import EconomicStateService

        service = EconomicStateService(self.session)

        # Get all agents for this run
        agents = await self.agent_repo.list_for_run(run_id)

        # Build map of agents with accepted work actions
        accepted_work_agents: set[str] = set()
        for item in result.accepted:
            if item.action_type == "work":
                agent_id = item.event_payload.get("agent_id")
                if isinstance(agent_id, str):
                    accepted_work_agents.add(agent_id)

        # Process each agent
        for agent in agents:
            agent_id = agent.id
            tick_no = result.tick_no

            # Get associated governance case if any (for work_ban tracking)
            case_id = None

            # Process work income if agent had accepted work action
            if agent_id in accepted_work_agents:
                await service.process_work_income(
                    world=world,
                    agent_id=agent_id,
                    tick_no=tick_no,
                    run_id=run_id,
                )

            # Process daily consumption (Phase 3: economic pressure)
            await service.process_tick_consumption(
                world=world,
                agent_id=agent_id,
                tick_no=tick_no,
                run_id=run_id,
            )

            # Process tick economic effects (food decay, employment status)
            await service.process_tick_economic_effects(
                world=world,
                agent_id=agent_id,
                tick_no=tick_no,
                run_id=run_id,
                case_id=case_id,
            )

        # Process free action consequences (consequence_source == "pending")
        # These are handled by the ConsequenceGenerator in Phase 2
        await self._process_free_action_consequences(
            run_id=run_id,
            result=result,
            tick_no=result.tick_no,
        )

    async def _process_free_action_consequences(
        self,
        run_id: str,
        result: TickResult,
        tick_no: int,
    ) -> None:
        """Process free action consequences marked as pending.

        Calls the LLM ConsequenceGenerator to produce StateDelta for each
        pending free action, then applies the delta via DeltaApplier.
        """
        from app.infra.logging import get_logger
        from app.sim.consequence_generator import generate_consequences
        from app.sim.delta_applier import DeltaApplier
        from app.sim.economic_state_service import EconomicStateService

        logger = get_logger(__name__)

        # Find all accepted free actions (not standard actions)
        standard_actions = {"move", "rest", "work", "talk", "talk_rejected", "listen",
                          "conversation_started", "conversation_joined"}
        free_actions = [
            item for item in result.accepted
            if item.action_type not in standard_actions
            and item.event_payload.get("consequence_source") == "pending"
        ]

        if not free_actions:
            return

        service = EconomicStateService(self.session)
        applier = DeltaApplier(self.session)

        for item in free_actions:
            agent_id = item.event_payload.get("agent_id", "unknown")
            action_type = item.action_type
            raw_intent = item.event_payload.get("raw_intent", "")
            payload = item.event_payload.get("free_action_payload", {})
            target_agent_id = item.event_payload.get("target_agent_id")
            location_id = item.event_payload.get("location_id")
            matched_rules = ""

            # Extract matched rules if present
            if "rule_evaluation" in item.event_payload:
                rule_eval = item.event_payload.get("rule_evaluation", {})
                matched_rules = rule_eval.get("reason", "")

            # Get actor economic state
            actor_state = await service.ensure_economic_state(
                world=None, agent_id=agent_id, tick_no=tick_no, run_id=run_id
            )

            # Get target economic state if applicable
            target_state = None
            if target_agent_id:
                target_state = await service.ensure_economic_state(
                    world=None, agent_id=target_agent_id, tick_no=tick_no, run_id=run_id
                )

            # Generate consequences via LLM
            state_delta = await generate_consequences(
                action_type=action_type,
                agent_id=agent_id,
                target_agent_id=target_agent_id,
                target_location_id=location_id,
                raw_intent=raw_intent,
                payload=payload,
                actor_cash=actor_state.cash if actor_state else 0.0,
                actor_employment=actor_state.employment_status if actor_state else "unknown",
                actor_food_security=actor_state.food_security if actor_state else 1.0,
                target_cash=target_state.cash if target_state else None,
                target_employment=target_state.employment_status if target_state else None,
                target_food_security=target_state.food_security if target_state else None,
                matched_rules=matched_rules,
            )

            if state_delta is None:
                logger.warning(
                    "free_action_consequence_failed: agent=%s action=%s tick=%d",
                    agent_id,
                    action_type,
                    tick_no,
                )
                # Mark consequence source as failed
                item.event_payload["consequence_source"] = "generation_failed"
                continue

            # Apply delta via DeltaApplier
            affected = await applier.apply(
                state_delta,
                run_id=run_id,
                tick_no=tick_no,
                world=None,
            )

            # Apply relationship deltas if present
            if state_delta.relationship_deltas:
                await applier.apply_relationship_deltas(
                    state_delta,
                    run_id=run_id,
                    tick_no=tick_no,
                )

            logger.info(
                "free_action_processed: agent=%s action=%s affected=%s tick=%d",
                agent_id,
                action_type,
                affected,
                tick_no,
            )

            # Mark as successfully processed
            item.event_payload["consequence_source"] = "llm_generated"

    def _build_tick_events(self, run_id: str, result: TickResult) -> list[Event]:
        """Build event objects from tick results."""
        events = [
            build_event(
                run_id=run_id,
                tick_no=result.tick_no,
                world_time=result.world_time,
                action_type=item.action_type,
                payload=item.event_payload,
                accepted=True,
            )
            for item in result.accepted
        ]
        events.extend(
            build_event(
                run_id=run_id,
                tick_no=result.tick_no,
                world_time=result.world_time,
                action_type=item.action_type,
                payload={"reason": item.reason, **item.event_payload},
                accepted=False,
            )
            for item in result.rejected
        )
        return events

    async def persist_tick_memories(self, run_id: str, events: list[Event]) -> None:
        """Persist memories from tick events."""
        agents_list, locations_list = await asyncio.gather(
            self.agent_repo.list_for_run(run_id),
            self.location_repo.list_for_run(run_id),
        )
        agent_map = {a.id: a for a in agents_list}
        agent_name_map = {a.id: a.name for a in agents_list}
        location_name_map = {loc.id: loc.name for loc in locations_list}
        memories: list[Memory] = []
        updated_routine_memory = False
        memory_inputs = self._prepare_memory_inputs(
            events, agent_name_map=agent_name_map, location_name_map=location_name_map
        )
        routine_memory_map = await self._preload_routine_memories(
            session=self.session,
            run_id=run_id,
            items=memory_inputs,
        )
        relationship_strength_map = await self._preload_relationship_strengths(
            session=self.session,
            run_id=run_id,
            items=memory_inputs,
        )
        for event, records in memory_inputs:
            for agent_id, content, summary, related_agent_id in records:
                routine_memory = routine_memory_map.get((agent_id, summary, event.location_id))
                if routine_memory is not None:
                    self._extend_routine_memory(routine_memory, event)
                    updated_routine_memory = True
                    continue
                perspective = self._determine_perspective(event, agent_id)
                relationship_strength = relationship_strength_map.get(
                    (agent_id, related_agent_id), 0.0
                )
                memory_importance = calculate_memory_importance(
                    event_importance=event.importance,
                    perspective=perspective,
                    relationship_strength=relationship_strength,
                    goal_relevance=self._is_goal_relevant(event, agent_map.get(agent_id)),
                    location_relevance=self._is_location_relevant(event, agent_map.get(agent_id)),
                )
                memory_category = determine_memory_category(
                    importance=memory_importance,
                    tick_age=0,  # New memory, age is 0
                )

                memories.append(
                    Memory(
                        id=str(uuid4()),
                        run_id=run_id,
                        agent_id=agent_id,
                        tick_no=event.tick_no,
                        memory_type="episodic_short",
                        memory_category=memory_category,
                        content=content,
                        summary=summary,
                        importance=memory_importance,
                        event_importance=event.importance,
                        self_relevance=self._perspective_relevance(perspective),
                        streak_count=1,
                        last_tick_no=event.tick_no,
                        related_agent_id=related_agent_id,
                        location_id=event.location_id,
                        source_event_id=event.id,
                        metadata_json={"event_type": event.event_type},
                    )
                )

        if memories:
            await self.memory_repo.create_many(memories)
        elif updated_routine_memory:
            await self.session.commit()

    async def persist_tick_memories_with_session(
        self,
        session: AsyncSession,
        run_id: str,
        events: list[Event],
    ) -> None:
        """Persist memories using a provided session (for isolated tick operations)."""
        agent_repo = AgentRepository(session)
        location_repo = LocationRepository(session)
        agents, locations = await asyncio.gather(
            agent_repo.list_for_run(run_id),
            location_repo.list_for_run(run_id),
        )
        agent_map = {a.id: a for a in agents}
        agent_name_map = {a.id: a.name for a in agents}
        location_name_map = {loc.id: loc.name for loc in locations}
        memories: list[Memory] = []
        updated_routine_memory = False
        memory_inputs = self._prepare_memory_inputs(
            events, agent_name_map=agent_name_map, location_name_map=location_name_map
        )
        routine_memory_map = await self._preload_routine_memories(
            session=session,
            run_id=run_id,
            items=memory_inputs,
        )
        relationship_strength_map = await self._preload_relationship_strengths(
            session=session,
            run_id=run_id,
            items=memory_inputs,
        )
        for event, records in memory_inputs:
            for agent_id, content, summary, related_agent_id in records:
                routine_memory = routine_memory_map.get((agent_id, summary, event.location_id))
                if routine_memory is not None:
                    self._extend_routine_memory(routine_memory, event)
                    updated_routine_memory = True
                    continue
                perspective = self._determine_perspective(event, agent_id)
                relationship_strength = relationship_strength_map.get(
                    (agent_id, related_agent_id), 0.0
                )
                memory_importance = calculate_memory_importance(
                    event_importance=event.importance,
                    perspective=perspective,
                    relationship_strength=relationship_strength,
                    goal_relevance=self._is_goal_relevant(event, agent_map.get(agent_id)),
                    location_relevance=self._is_location_relevant(event, agent_map.get(agent_id)),
                )
                memory_category = determine_memory_category(
                    importance=memory_importance,
                    tick_age=0,  # New memory, age is 0
                )

                memories.append(
                    Memory(
                        id=str(uuid4()),
                        run_id=run_id,
                        agent_id=agent_id,
                        tick_no=event.tick_no,
                        memory_type="episodic_short",
                        memory_category=memory_category,
                        content=content,
                        summary=summary,
                        importance=memory_importance,
                        event_importance=event.importance,
                        self_relevance=self._perspective_relevance(perspective),
                        streak_count=1,
                        last_tick_no=event.tick_no,
                        related_agent_id=related_agent_id,
                        location_id=event.location_id,
                        source_event_id=event.id,
                        metadata_json={"event_type": event.event_type},
                    )
                )

        if memories:
            memory_repo = MemoryRepository(session)
            await memory_repo.create_many(memories)
        elif updated_routine_memory:
            await session.commit()

    async def persist_tick_relationships(self, run_id: str, events: list[Event]) -> None:
        """Persist relationships from social speech events."""
        run_context = await self._load_relationship_run_context(run_id)
        updated = False
        for event in events:
            delta = self._compute_relationship_delta(event, run_context)
            if delta is None:
                continue
            self._annotate_relationship_impact(event, delta)
            for actor_agent_id, other_agent_id in self._iter_relationship_pairs(event):
                await self.relationship_repo.upsert_interaction(
                    run_id=run_id,
                    agent_id=actor_agent_id,
                    other_agent_id=other_agent_id,
                    familiarity_delta=delta.familiarity_delta,
                    trust_delta=delta.trust_delta,
                    affinity_delta=delta.affinity_delta,
                )
                updated = True
                await self.relationship_repo.upsert_interaction(
                    run_id=run_id,
                    agent_id=other_agent_id,
                    other_agent_id=actor_agent_id,
                    familiarity_delta=delta.familiarity_delta,
                    trust_delta=delta.trust_delta,
                    affinity_delta=delta.affinity_delta,
                )
                updated = True
        if updated:
            await self.session.commit()

    async def persist_tick_relationships_with_session(
        self,
        session: AsyncSession,
        run_id: str,
        events: list[Event],
    ) -> None:
        """Persist relationships using a provided session."""
        rel_repo = RelationshipRepository(session)
        run_context = await self._load_relationship_run_context(run_id, session=session)
        updated = False
        for event in events:
            delta = self._compute_relationship_delta(event, run_context)
            if delta is None:
                continue
            self._annotate_relationship_impact(event, delta)
            for actor_agent_id, other_agent_id in self._iter_relationship_pairs(event):
                await rel_repo.upsert_interaction(
                    run_id=run_id,
                    agent_id=actor_agent_id,
                    other_agent_id=other_agent_id,
                    familiarity_delta=delta.familiarity_delta,
                    trust_delta=delta.trust_delta,
                    affinity_delta=delta.affinity_delta,
                )
                updated = True
                await rel_repo.upsert_interaction(
                    run_id=run_id,
                    agent_id=other_agent_id,
                    other_agent_id=actor_agent_id,
                    familiarity_delta=delta.familiarity_delta,
                    trust_delta=delta.trust_delta,
                    affinity_delta=delta.affinity_delta,
                )
                updated = True
        if updated:
            await session.commit()

    async def _load_relationship_run_context(
        self,
        run_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> tuple[SimulationRun | None, dict[str, str], dict[str, dict]]:
        active_session = session or self.session
        run_repo = self.run_repo if session is None else RunRepository(active_session)
        location_repo = (
            self.location_repo if session is None else LocationRepository(active_session)
        )
        agent_repo = self.agent_repo if session is None else AgentRepository(active_session)
        run, locations, agents = await asyncio.gather(
            run_repo.get(run_id),
            location_repo.list_for_run(run_id),
            agent_repo.list_for_run(run_id),
        )
        location_type_map = {location.id: location.location_type for location in locations}
        agent_status_map = {agent.id: dict(agent.status or {}) for agent in agents}
        return run, location_type_map, agent_status_map

    @staticmethod
    def _compute_relationship_delta(
        event: Event,
        run_context: tuple[SimulationRun | None, dict[str, str], dict[str, dict]],
    ):
        run, location_type_map, agent_status_map = run_context
        location_id = event.location_id
        location_type = location_type_map.get(location_id) if location_id else None
        policy_values: dict[str, object] | None = None
        if run is not None:
            package = load_world_design_runtime_package(run.scenario_type)
            policy_values = package.policy_config.values
        payload = event.payload or {}
        rule_evaluation = payload.get("rule_evaluation")
        governance_execution = payload.get("governance_execution")
        rule_decision = None
        rule_reason = None
        risk_level = None
        governance_decision = None
        governance_reason = None
        actor_attention_score = 0.0
        target_attention_score = 0.0
        if isinstance(rule_evaluation, dict):
            decision_value = rule_evaluation.get("decision")
            reason_value = rule_evaluation.get("reason")
            risk_level_value = rule_evaluation.get("risk_level")
            if isinstance(decision_value, str):
                rule_decision = decision_value
            if isinstance(reason_value, str):
                rule_reason = reason_value
            if isinstance(risk_level_value, str):
                risk_level = risk_level_value
        if isinstance(governance_execution, dict):
            governance_decision_value = governance_execution.get("decision")
            governance_reason_value = governance_execution.get("reason")
            if isinstance(governance_decision_value, str):
                governance_decision = governance_decision_value
            if isinstance(governance_reason_value, str):
                governance_reason = governance_reason_value
        if event.actor_agent_id:
            actor_attention_score = float(
                agent_status_map.get(event.actor_agent_id, {}).get(
                    "governance_attention_score",
                    0.0,
                )
                or 0.0
            )
        if event.target_agent_id:
            target_attention_score = float(
                agent_status_map.get(event.target_agent_id, {}).get(
                    "governance_attention_score",
                    0.0,
                )
                or 0.0
            )
        return compute_relationship_delta(
            event_type=event.event_type,
            world_time=event.world_time,
            location_id=location_id,
            location_type=location_type,
            rule_decision=rule_decision,
            rule_reason=rule_reason,
            risk_level=risk_level,
            governance_decision=governance_decision,
            governance_reason=governance_reason,
            actor_attention_score=actor_attention_score,
            target_attention_score=target_attention_score,
            policy_values=policy_values,
        )

    @staticmethod
    def _iter_relationship_pairs(event: Event) -> list[tuple[str, str]]:
        if event.event_type not in {"talk", "speech"}:
            return []
        if event.actor_agent_id is None:
            return []

        payload = event.payload or {}
        participant_ids = payload.get("participant_ids")
        participants = (
            [
                participant_id
                for participant_id in participant_ids
                if isinstance(participant_id, str) and participant_id != event.actor_agent_id
            ]
            if isinstance(participant_ids, list)
            else []
        )
        if event.target_agent_id and event.target_agent_id not in participants:
            participants.append(event.target_agent_id)

        return [
            (event.actor_agent_id, participant_id)
            for participant_id in participants
            if participant_id != event.actor_agent_id
        ]

    @staticmethod
    def _annotate_relationship_impact(event: Event, delta) -> None:
        payload = dict(event.payload or {})
        rule_evaluation = payload.get("rule_evaluation")
        governance_execution = payload.get("governance_execution")
        relationship_impact = {
            "applied": True,
            "familiarity_delta": delta.familiarity_delta,
            "trust_delta": delta.trust_delta,
            "affinity_delta": delta.affinity_delta,
            "modifiers": list(delta.modifiers),
            "summary": PersistenceManager._build_relationship_impact_summary(delta),
        }
        if isinstance(rule_evaluation, dict):
            relationship_impact["rule_decision"] = rule_evaluation.get("decision")
            relationship_impact["rule_reason"] = rule_evaluation.get("reason")
            relationship_impact["risk_level"] = rule_evaluation.get("risk_level")
        if isinstance(governance_execution, dict):
            relationship_impact["governance_decision"] = governance_execution.get("decision")
            relationship_impact["governance_reason"] = governance_execution.get("reason")
        payload["relationship_impact"] = relationship_impact
        event.payload = payload

    @staticmethod
    def _build_relationship_impact_summary(delta) -> str:
        modifiers = set(delta.modifiers)
        if "soft_risk" in modifiers:
            return "高风险社交接触降低了信任和亲近感的增长。"
        if "attention_high" in modifiers:
            return "高关注状态削弱了这次互动带来的关系增益。"
        if "attention_elevated" in modifiers:
            return "制度关注使这次互动的关系增益有所减弱。"
        if "governance_block" in modifiers:
            return "治理拦截使这次互动没有形成正向关系增益。"
        if "governance_warn" in modifiers:
            return "治理警告削弱了这次互动带来的关系增益。"
        if any(modifier.startswith("social_boost:") for modifier in modifiers):
            return "社交场景提升了亲近感的增长。"
        if "sensitive_location" in modifiers:
            return "敏感地点削弱了信任和亲近感的增长。"
        return "社交互动提升了熟悉度和关系强度。"

    async def persist_agent_locations(self, run_id: str, world: WorldState) -> None:
        """Update agent locations after tick."""
        agents = await self.agent_repo.list_for_run(run_id)
        for agent in agents:
            state = world.get_agent(agent.id)
            if state is not None:
                agent.current_location_id = state.location_id
        await self.session.commit()

    def _build_memory_records(
        self,
        event: Event,
        agent_name_map: dict[str, str] | None = None,
        location_name_map: dict[str, str] | None = None,
    ) -> list[tuple[str, str, str, str | None]]:
        """Build memory records from an event.

        Returns list of tuples: (agent_id, content, summary, related_agent_id)
        """
        payload = event.payload or {}
        _agents = agent_name_map or {}
        _locations = location_name_map or {}

        def agent_name(agent_id: str | None) -> str:
            if not agent_id:
                return "someone"
            return _agents.get(agent_id, agent_id)

        def location_name(loc_id: str | None) -> str:
            if not loc_id:
                return "unknown"
            return _locations.get(loc_id, loc_id)

        governance_records = self._build_governance_memory_records(
            event,
            agent_name=agent_name,
            location_name=location_name,
        )
        rule_feedback_records = self._build_rule_feedback_memory_records(
            event,
            agent_name=agent_name,
            location_name=location_name,
        )

        if event.event_type.endswith("_rejected"):
            return governance_records + rule_feedback_records

        if event.event_type == "move":
            destination = location_name(str(payload.get("to_location_id", "")) or None)
            origin = location_name(str(payload.get("from_location_id", "")) or None)
            return (
                [
                    (
                        event.actor_agent_id,
                        f"Moved from {origin} to {destination}.",
                        f"Moved to {destination}",
                        None,
                    )
                ]
                + governance_records
                + rule_feedback_records
            )

        if event.event_type in {"conversation_started", "conversation_joined"}:
            return []

        if event.event_type in {"talk", "speech"}:
            target_id = str(payload.get("target_agent_id") or event.target_agent_id or "")
            loc_id = str(payload.get("location_id") or "")
            target = agent_name(target_id)
            actor = agent_name(event.actor_agent_id)
            loc = location_name(loc_id)
            message = payload.get("message", "")
            participant_ids = payload.get("participant_ids")
            listeners = (
                [
                    participant_id
                    for participant_id in participant_ids
                    if isinstance(participant_id, str) and participant_id != event.actor_agent_id
                ]
                if isinstance(participant_ids, list)
                else []
            )
            if event.target_agent_id and event.target_agent_id not in listeners:
                listeners.append(event.target_agent_id)

            if message:
                actor_content = f'Said to {target} at {loc}: "{message}"'
                actor_summary = (
                    f"Said to {target}: {message[:30]}{'...' if len(message) > 30 else ''}"
                )
                listener_records = [
                    (
                        listener_id,
                        f'{actor} said at {loc}: "{message}"',
                        f"{actor} said: {message[:30]}{'...' if len(message) > 30 else ''}",
                        event.actor_agent_id,
                    )
                    for listener_id in listeners
                ]
            else:
                actor_content = f"Said something to {target} at {loc}."
                actor_summary = f"Said to {target}"
                listener_records = [
                    (
                        listener_id,
                        f"Talked with {actor} at {loc}.",
                        f"Talked with {actor}",
                        event.actor_agent_id,
                    )
                    for listener_id in listeners
                ]

            return (
                [
                    (event.actor_agent_id, actor_content, actor_summary, event.target_agent_id),
                    *listener_records,
                ]
                + governance_records
                + rule_feedback_records
            )

        if event.event_type == "listen":
            speaker_id = str(payload.get("target_agent_id") or event.target_agent_id or "")
            loc_id = str(payload.get("location_id") or "")
            speaker = agent_name(speaker_id)
            loc = location_name(loc_id)
            return (
                [
                    (
                        event.actor_agent_id,
                        f"Listened to {speaker} at {loc}.",
                        f"Listened to {speaker}",
                        event.target_agent_id,
                    )
                ]
                + governance_records
                + rule_feedback_records
            )

        if event.event_type == "work":
            return [
                (event.actor_agent_id, "Worked during this tick.", "Worked", None),
                *governance_records,
                *rule_feedback_records,
            ]

        if event.event_type == "rest":
            return [
                (event.actor_agent_id, "Rested during this tick.", "Rested", None),
                *governance_records,
                *rule_feedback_records,
            ]

        return (
            [
                (
                    event.actor_agent_id,
                    f"Experienced event {event.event_type}.",
                    f"Event: {event.event_type}",
                    event.target_agent_id,
                )
            ]
            + governance_records
            + rule_feedback_records
        )

    @staticmethod
    def _build_governance_memory_records(
        event: Event,
        *,
        agent_name,
        location_name,
    ) -> list[tuple[str, str, str, str | None]]:
        actor_agent_id = event.actor_agent_id
        if actor_agent_id is None:
            return []

        payload = event.payload or {}
        governance_execution = payload.get("governance_execution")
        if not isinstance(governance_execution, dict):
            return []

        decision = governance_execution.get("decision")
        reason = governance_execution.get("reason")
        if (
            decision not in {"record_only", "warn", "block"}
            or not isinstance(reason, str)
            or not reason
        ):
            return []

        loc_id = str(payload.get("location_id") or event.location_id or "")
        loc = location_name(loc_id)
        actor = agent_name(actor_agent_id)
        if decision == "record_only":
            return [
                (
                    actor_agent_id,
                    f"{actor} was observed by governance at {loc}: {reason}.",
                    f"Governance record: {reason}",
                    None,
                )
            ]
        if decision == "warn":
            return [
                (
                    actor_agent_id,
                    f"{actor} received a governance warning at {loc}: {reason}.",
                    f"Governance warning: {reason}",
                    None,
                )
            ]

        return [
            (
                actor_agent_id,
                f"{actor} was blocked by governance at {loc}: {reason}.",
                f"Governance block: {reason}",
                None,
            )
        ]

    @staticmethod
    def _build_rule_feedback_memory_records(
        event: Event,
        *,
        agent_name,
        location_name,
    ) -> list[tuple[str, str, str, str | None]]:
        actor_agent_id = event.actor_agent_id
        if actor_agent_id is None:
            return []

        payload = event.payload or {}
        rule_evaluation = payload.get("rule_evaluation")
        if not isinstance(rule_evaluation, dict):
            return []

        reason = rule_evaluation.get("reason")
        decision = rule_evaluation.get("decision")
        if not isinstance(reason, str) or not reason:
            return []

        governance_execution = payload.get("governance_execution")
        if (
            isinstance(governance_execution, dict)
            and governance_execution.get("reason") == reason
            and governance_execution.get("decision") in {"warn", "block"}
        ):
            return []

        loc_id = str(payload.get("location_id") or event.location_id or "")
        actor = agent_name(actor_agent_id)
        loc = location_name(loc_id)

        if decision == "soft_risk":
            return [
                (
                    actor_agent_id,
                    f"{actor} received a rule risk signal at {loc}: {reason}.",
                    f"Rule risk: {reason}",
                    None,
                )
            ]

        if decision in {"violates_rule", "impossible"}:
            return [
                (
                    actor_agent_id,
                    f"{actor} was stopped by a rule at {loc}: {reason}.",
                    f"Rule block: {reason}",
                    None,
                )
            ]

        return []

    def _prepare_memory_inputs(
        self,
        events: Sequence[Event],
        *,
        agent_name_map: dict[str, str],
        location_name_map: dict[str, str],
    ) -> list[tuple[Event, list[tuple[str, str, str, str | None]]]]:
        speech_listener_keys: set[tuple[int, str, str]] = set()
        for event in events:
            if event.event_type not in {"talk", "speech"} or event.actor_agent_id is None:
                continue
            payload = event.payload or {}
            conversation_id = payload.get("conversation_id")
            participant_ids = payload.get("participant_ids")
            if not isinstance(conversation_id, str) or not isinstance(participant_ids, list):
                continue
            for participant_id in participant_ids:
                if isinstance(participant_id, str) and participant_id != event.actor_agent_id:
                    speech_listener_keys.add((event.tick_no, conversation_id, participant_id))

        prepared: list[tuple[Event, list[tuple[str, str, str, str | None]]]] = []
        for event in events:
            if event.actor_agent_id is None:
                continue
            if event.event_type == "listen":
                payload = event.payload or {}
                conversation_id = payload.get("conversation_id")
                if (
                    isinstance(conversation_id, str)
                    and (event.tick_no, conversation_id, event.actor_agent_id)
                    in speech_listener_keys
                ):
                    continue
            records = self._build_memory_records(event, agent_name_map, location_name_map)
            if records:
                prepared.append((event, records))
        return prepared

    async def _preload_routine_memories(
        self,
        *,
        session: AsyncSession,
        run_id: str,
        items: Sequence[tuple[Event, list[tuple[str, str, str, str | None]]]],
    ) -> dict[tuple[str, str, str | None], Memory]:
        routine_requests = [
            (event, agent_id, summary)
            for event, records in items
            if event.event_type in ROUTINE_MEMORY_EVENT_TYPES
            for agent_id, _content, summary, _related_agent_id in records
        ]
        if not routine_requests:
            return {}

        agent_ids = {agent_id for _event, agent_id, _summary in routine_requests}
        summaries = {summary for _event, _agent_id, summary in routine_requests}
        min_tick = min(
            max(0, event.tick_no - ROUTINE_MEMORY_LOOKBACK_TICKS)
            for event, _agent_id, _summary in routine_requests
        )
        location_ids = {event.location_id for event, _agent_id, _summary in routine_requests}
        location_filters = []
        non_null_location_ids = [
            location_id for location_id in location_ids if location_id is not None
        ]
        if non_null_location_ids:
            location_filters.append(Memory.location_id.in_(non_null_location_ids))
        if None in location_ids:
            location_filters.append(Memory.location_id.is_(None))

        stmt = (
            select(Memory)
            .where(
                Memory.run_id == run_id,
                Memory.agent_id.in_(agent_ids),
                Memory.summary.in_(summaries),
                Memory.metadata_json["event_type"].as_string().in_(["work", "rest"]),
                Memory.tick_no >= min_tick,
                or_(*location_filters),
            )
            .order_by(Memory.tick_no.desc(), Memory.created_at.desc())
        )
        result = await session.execute(stmt)
        routine_map: dict[tuple[str, str, str | None], Memory] = {}
        for memory in result.scalars():
            key = (memory.agent_id, memory.summary or "", memory.location_id)
            routine_map.setdefault(key, memory)
        return routine_map

    async def _preload_relationship_strengths(
        self,
        *,
        session: AsyncSession,
        run_id: str,
        items: Sequence[tuple[Event, list[tuple[str, str, str, str | None]]]],
    ) -> dict[tuple[str, str | None], float]:
        pair_requests = {
            (agent_id, related_agent_id)
            for _event, records in items
            for agent_id, _content, _summary, related_agent_id in records
            if related_agent_id
        }
        if not pair_requests:
            return {}

        pair_conditions = [
            and_(Relationship.agent_id == agent_id, Relationship.other_agent_id == other_agent_id)
            for agent_id, other_agent_id in pair_requests
        ]
        stmt = select(Relationship).where(Relationship.run_id == run_id, or_(*pair_conditions))
        result = await session.execute(stmt)
        strength_map: dict[tuple[str, str | None], float] = {
            (agent_id, related_agent_id): 0.0 for agent_id, related_agent_id in pair_requests
        }
        for relation in result.scalars():
            components = [
                relation.familiarity,
                max(relation.trust, 0.0),
                max(relation.affinity, 0.0),
            ]
            strength_map[(relation.agent_id, relation.other_agent_id)] = sum(components) / len(
                components
            )
        return strength_map

    @staticmethod
    def _determine_perspective(event: Event, agent_id: str) -> str:
        if event.event_type == "listen" and agent_id == event.actor_agent_id:
            return "listener"
        if agent_id == event.actor_agent_id:
            return "actor"
        if agent_id == event.target_agent_id:
            return "target"
        return "observer"

    @staticmethod
    def _perspective_relevance(perspective: str) -> float:
        if perspective == "target":
            return 1.0
        if perspective == "listener":
            return 1.0
        if perspective == "actor":
            return 0.8
        return 0.4

    @staticmethod
    def _is_goal_relevant(event: Event, agent: Agent | None) -> bool:
        if agent is None or not agent.current_goal:
            return False
        goal = agent.current_goal.lower()
        if event.event_type in goal:
            return True
        if event.event_type == "move" and goal.startswith("move:"):
            return True
        return event.event_type == "speech" and "talk" in goal

    @staticmethod
    def _is_location_relevant(event: Event, agent: Agent | None) -> bool:
        if agent is None:
            return False
        return bool(
            event.location_id
            and (
                event.location_id == agent.current_location_id
                or event.location_id == agent.home_location_id
            )
        )

    async def _relationship_strength(
        self,
        *,
        run_id: str,
        agent_id: str,
        related_agent_id: str | None,
    ) -> float:
        return await self._relationship_strength_with_repo(
            rel_repo=self.relationship_repo,
            run_id=run_id,
            agent_id=agent_id,
            related_agent_id=related_agent_id,
        )

    async def _relationship_strength_with_repo(
        self,
        *,
        rel_repo: RelationshipRepository,
        run_id: str,
        agent_id: str,
        related_agent_id: str | None,
    ) -> float:
        if not related_agent_id:
            return 0.0
        relation = await rel_repo.get_pair(run_id, agent_id, related_agent_id)
        if relation is None:
            return 0.0
        components = [relation.familiarity, max(relation.trust, 0.0), max(relation.affinity, 0.0)]
        return sum(components) / len(components)

    async def _find_routine_memory_to_extend(
        self,
        *,
        run_id: str,
        agent_id: str,
        event: Event,
        summary: str,
    ) -> Memory | None:
        return await self._find_routine_memory_to_extend_with_session(
            session=self.session,
            run_id=run_id,
            agent_id=agent_id,
            event=event,
            summary=summary,
        )

    async def _find_routine_memory_to_extend_with_session(
        self,
        *,
        session: AsyncSession,
        run_id: str,
        agent_id: str,
        event: Event,
        summary: str,
    ) -> Memory | None:
        if event.event_type not in ROUTINE_MEMORY_EVENT_TYPES:
            return None
        return await MemoryRepository(session).find_recent_routine_memory(
            run_id=run_id,
            agent_id=agent_id,
            summary=summary,
            location_id=event.location_id,
            since_tick=max(0, event.tick_no - ROUTINE_MEMORY_LOOKBACK_TICKS),
        )

    @staticmethod
    def _extend_routine_memory(memory: Memory, event: Event) -> None:
        next_streak = (memory.streak_count or 1) + 1
        memory.streak_count = next_streak
        memory.last_tick_no = event.tick_no
        memory.tick_no = event.tick_no
        if next_streak >= 3:
            memory.memory_category = "medium_term"
        if memory.summary == "Worked":
            memory.content = f"Worked during {next_streak} consecutive ticks."
        elif memory.summary == "Rested":
            memory.content = f"Rested during {next_streak} consecutive ticks."


# ─── Schedule-based goal helpers ─────────────────────────────────────────────

# Maps time-period values from WorldState._time_period() to current_plan keys
_TIME_PERIOD_TO_PLAN_KEY: dict[str, str] = {
    "dawn": "morning",
    "morning": "morning",
    "noon": "daytime",
    "afternoon": "daytime",
    "evening": "evening",
}

# Plan values that should be normalised to a concrete action goal
_PLAN_VALUE_NORMALISE: dict[str, str] = {
    "socialize": "talk",
    "prepare_day": "rest",
    "home": "go_home",
}


def _compute_goal_for_schedule(world: WorldState, agent: Agent) -> str | None:
    """Compute the agent's goal for the current time period from its daily plan.

    Returns None when no update is needed (e.g. unrecognised time period or
    empty plan), so callers can skip the write.
    """
    plan: dict = agent.current_plan or {}
    if not plan:
        return None

    time_period: str = world._time_period()

    if time_period == "night":
        # Night time: agents should be resting
        return "rest"

    plan_key = _TIME_PERIOD_TO_PLAN_KEY.get(time_period)
    if plan_key is None:
        return None

    raw_goal: str | None = plan.get(plan_key)
    if raw_goal is None:
        return None

    # Normalise plan values to recognised goal identifiers
    return _PLAN_VALUE_NORMALISE.get(raw_goal, raw_goal)
