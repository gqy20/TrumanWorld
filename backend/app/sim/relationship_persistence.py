from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.scenario.runtime.world_design import load_world_design_runtime_package
from app.sim.relationship_policy import compute_relationship_delta
from app.store.models import Event, SimulationRun
from app.store.repository_modules.relationships import RelationshipInteraction
from app.store.repositories import (
    AgentRepository,
    LocationRepository,
    RelationshipRepository,
    RunRepository,
)


class RelationshipPersistence:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.run_repo = RunRepository(session)
        self.agent_repo = AgentRepository(session)
        self.location_repo = LocationRepository(session)
        self.relationship_repo = RelationshipRepository(session)

    async def persist_tick_relationships(self, run_id: str, events: list[Event]) -> None:
        """Persist relationships from social speech events."""
        run_context = await self._load_relationship_run_context(run_id)
        interactions = self._build_interactions(events, run_context)
        await self.relationship_repo.apply_interactions(run_id, interactions)

    async def persist_tick_relationships_with_session(
        self,
        session: AsyncSession,
        run_id: str,
        events: list[Event],
    ) -> None:
        """Persist relationships using a provided session."""
        rel_repo = RelationshipRepository(session)
        run_context = await self._load_relationship_run_context(run_id, session=session)
        interactions = self._build_interactions(events, run_context)
        if interactions:
            await rel_repo.apply_interactions(run_id, interactions)
            await session.commit()

    def _build_interactions(
        self,
        events: list[Event],
        run_context: tuple[SimulationRun | None, dict[str, str], dict[str, dict]],
    ) -> list[RelationshipInteraction]:
        interactions: list[RelationshipInteraction] = []
        for event in events:
            delta = self._compute_relationship_delta(event, run_context)
            if delta is None:
                continue
            self._annotate_relationship_impact(event, delta)
            for actor_agent_id, other_agent_id in self._iter_relationship_pairs(event):
                interactions.extend(
                    (
                        RelationshipInteraction(
                            agent_id=actor_agent_id,
                            other_agent_id=other_agent_id,
                            familiarity_delta=delta.familiarity_delta,
                            trust_delta=delta.trust_delta,
                            affinity_delta=delta.affinity_delta,
                        ),
                        RelationshipInteraction(
                            agent_id=other_agent_id,
                            other_agent_id=actor_agent_id,
                            familiarity_delta=delta.familiarity_delta,
                            trust_delta=delta.trust_delta,
                            affinity_delta=delta.affinity_delta,
                        ),
                    )
                )
        return interactions

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
        run = await run_repo.get(run_id)
        locations = await location_repo.list_for_run(run_id)
        agents = await agent_repo.list_for_run(run_id)
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
        conversation_turn_no = payload.get("conversation_turn_no", 1)
        if not isinstance(conversation_turn_no, int) or conversation_turn_no < 1:
            conversation_turn_no = 1
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
            conversation_turn_no=conversation_turn_no,
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
            "summary": RelationshipPersistence._build_relationship_impact_summary(delta),
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
