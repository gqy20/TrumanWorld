from __future__ import annotations
# ruff: noqa: F403,F405

from app.store.repository_modules._common import *

class AgentEconomicStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        run_id: str,
        agent_id: str,
        cash: float | None = None,
        employment_status: str | None = None,
        food_security: float | None = None,
        housing_security: float | None = None,
        work_restriction_until_tick: int | None = None,
        last_income_tick: int | None = None,
    ) -> AgentEconomicState:
        """Create or update economic state for an agent."""
        stmt = select(AgentEconomicState).where(
            AgentEconomicState.run_id == run_id,
            AgentEconomicState.agent_id == agent_id,
        )
        result = await self.session.execute(stmt)
        state = result.scalars().first()

        if state is None:
            state = AgentEconomicState(
                id=str(uuid4()),
                run_id=run_id,
                agent_id=agent_id,
                cash=cash if cash is not None else 100.0,
                employment_status=employment_status if employment_status else "stable",
                food_security=food_security if food_security is not None else 1.0,
                housing_security=housing_security if housing_security is not None else 1.0,
            )
            self.session.add(state)
        else:
            if cash is not None:
                state.cash = cash
            if employment_status is not None:
                state.employment_status = employment_status
            if food_security is not None:
                state.food_security = food_security
            if housing_security is not None:
                state.housing_security = housing_security
            if work_restriction_until_tick is not None:
                state.work_restriction_until_tick = work_restriction_until_tick
            if last_income_tick is not None:
                state.last_income_tick = last_income_tick

        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def get_for_agent(
        self,
        run_id: str,
        agent_id: str,
    ) -> AgentEconomicState | None:
        stmt = select(AgentEconomicState).where(
            AgentEconomicState.run_id == run_id,
            AgentEconomicState.agent_id == agent_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def add_cash(
        self,
        run_id: str,
        agent_id: str,
        amount: float,
    ) -> AgentEconomicState | None:
        state = await self.get_for_agent(run_id, agent_id)
        if state is None:
            return None
        state.cash = max(0.0, state.cash + amount)
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def deduct_cash(
        self,
        run_id: str,
        agent_id: str,
        amount: float,
    ) -> AgentEconomicState | None:
        state = await self.get_for_agent(run_id, agent_id)
        if state is None:
            return None
        state.cash = max(0.0, state.cash - amount)
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def update_food_security(
        self,
        run_id: str,
        agent_id: str,
        delta: float,
    ) -> AgentEconomicState | None:
        state = await self.get_for_agent(run_id, agent_id)
        if state is None:
            return None
        state.food_security = max(0.0, min(1.0, state.food_security + delta))
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def update_employment_status(
        self,
        run_id: str,
        agent_id: str,
        new_status: str,
    ) -> AgentEconomicState | None:
        state = await self.get_for_agent(run_id, agent_id)
        if state is None:
            return None
        state.employment_status = new_status
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def set_work_restriction(
        self,
        run_id: str,
        agent_id: str,
        until_tick: int,
    ) -> AgentEconomicState | None:
        state = await self.get_for_agent(run_id, agent_id)
        if state is None:
            return None
        state.work_restriction_until_tick = until_tick
        await self.session.commit()
        await self.session.refresh(state)
        return state


class EconomicEffectLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        run_id: str,
        agent_id: str,
        tick_no: int,
        effect_type: str,
        cash_delta: float = 0.0,
        food_security_delta: float = 0.0,
        housing_security_delta: float = 0.0,
        employment_status_before: str | None = None,
        employment_status_after: str | None = None,
        reason: str | None = None,
        case_id: str | None = None,
    ) -> EconomicEffectLog:
        log = EconomicEffectLog(
            id=str(uuid4()),
            run_id=run_id,
            agent_id=agent_id,
            case_id=case_id,
            tick_no=tick_no,
            effect_type=effect_type,
            cash_delta=cash_delta,
            food_security_delta=food_security_delta,
            housing_security_delta=housing_security_delta,
            employment_status_before=employment_status_before,
            employment_status_after=employment_status_after,
            reason=reason,
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def list_for_agent(
        self,
        run_id: str,
        agent_id: str,
        limit: int = 50,
        effect_type: str | None = None,
    ) -> Sequence[EconomicEffectLog]:
        stmt = select(EconomicEffectLog).where(
            EconomicEffectLog.run_id == run_id,
            EconomicEffectLog.agent_id == agent_id,
        )
        if effect_type:
            stmt = stmt.where(EconomicEffectLog.effect_type == effect_type)
        stmt = stmt.order_by(EconomicEffectLog.tick_no.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_run(
        self,
        run_id: str,
        limit: int = 100,
    ) -> Sequence[EconomicEffectLog]:
        stmt = (
            select(EconomicEffectLog)
            .where(EconomicEffectLog.run_id == run_id)
            .order_by(EconomicEffectLog.tick_no.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_recent_logs(
        self,
        run_id: str,
        agent_id: str,
        limit: int = 10,
    ) -> Sequence[EconomicEffectLog]:
        return await self.list_for_agent(run_id, agent_id, limit=limit)


