from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.logging import get_logger
from app.sim.consequence_generator import generate_consequences
from app.sim.delta_applier import DeltaApplier
from app.sim.economic_state_service import EconomicStateService
from app.sim.runner import TickResult
from app.sim.world import WorldState
from app.store.repositories import AgentRepository


STANDARD_ACTIONS = {
    "move",
    "rest",
    "work",
    "talk",
    "talk_rejected",
    "listen",
    "conversation_started",
    "conversation_joined",
}


class EconomicPersistence:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.agent_repo = AgentRepository(session)

    async def persist_tick_economic_state(
        self,
        run_id: str,
        result: TickResult,
        world: WorldState,
    ) -> None:
        """Persist economic state changes and effect logs from tick results."""
        service = EconomicStateService(self.session)
        agents = await self.agent_repo.list_for_run(run_id)
        accepted_work_agents = _accepted_work_agent_ids(result)

        for agent in agents:
            agent_id = agent.id
            tick_no = result.tick_no
            case_id = None

            if agent_id in accepted_work_agents:
                await service.process_work_income(
                    world=world,
                    agent_id=agent_id,
                    tick_no=tick_no,
                    run_id=run_id,
                )

            await service.process_tick_consumption(
                world=world,
                agent_id=agent_id,
                tick_no=tick_no,
                run_id=run_id,
            )

            await service.process_tick_economic_effects(
                world=world,
                agent_id=agent_id,
                tick_no=tick_no,
                run_id=run_id,
                case_id=case_id,
            )

        await self.process_free_action_consequences(
            run_id=run_id,
            result=result,
            tick_no=result.tick_no,
        )

    async def process_free_action_consequences(
        self,
        run_id: str,
        result: TickResult,
        tick_no: int,
    ) -> None:
        """Process free action consequences marked as pending."""
        logger = get_logger(__name__)
        free_actions = [
            item
            for item in result.accepted
            if item.action_type not in STANDARD_ACTIONS
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
            matched_rules = _matched_rules(item.event_payload)

            actor_state = await service.ensure_economic_state(
                world=None,
                agent_id=agent_id,
                tick_no=tick_no,
                run_id=run_id,
            )

            target_state = None
            if target_agent_id:
                target_state = await service.ensure_economic_state(
                    world=None,
                    agent_id=target_agent_id,
                    tick_no=tick_no,
                    run_id=run_id,
                )

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
                item.event_payload["consequence_source"] = "generation_failed"
                continue

            affected = await applier.apply(
                state_delta,
                run_id=run_id,
                tick_no=tick_no,
                world=None,
            )

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

            item.event_payload["consequence_source"] = "llm_generated"


def _accepted_work_agent_ids(result: TickResult) -> set[str]:
    accepted_work_agents: set[str] = set()
    for item in result.accepted:
        if item.action_type == "work":
            agent_id = item.event_payload.get("agent_id")
            if isinstance(agent_id, str):
                accepted_work_agents.add(agent_id)
    return accepted_work_agents


def _matched_rules(event_payload: dict) -> str:
    rule_eval = event_payload.get("rule_evaluation")
    if not isinstance(rule_eval, dict):
        return ""
    reason = rule_eval.get("reason")
    return reason if isinstance(reason, str) else ""
