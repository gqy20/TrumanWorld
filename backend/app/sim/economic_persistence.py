from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.sim.economic_state_service import EconomicStateService
from app.sim.runner import TickResult
from app.sim.world import WorldState
from app.store.repositories import AgentRepository


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


def _accepted_work_agent_ids(result: TickResult) -> set[str]:
    accepted_work_agents: set[str] = set()
    for item in result.accepted:
        if item.action_type == "work":
            agent_id = item.event_payload.get("agent_id")
            if isinstance(agent_id, str):
                accepted_work_agents.add(agent_id)
    return accepted_work_agents
