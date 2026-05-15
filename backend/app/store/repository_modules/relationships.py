from __future__ import annotations
# ruff: noqa: F403,F405

from app.store.repository_modules._common import *

class RelationshipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_pair(
        self, run_id: str, agent_id: str, other_agent_id: str
    ) -> Relationship | None:
        stmt: Select[tuple[Relationship]] = select(Relationship).where(
            Relationship.run_id == run_id,
            Relationship.agent_id == agent_id,
            Relationship.other_agent_id == other_agent_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_interaction(
        self,
        run_id: str,
        agent_id: str,
        other_agent_id: str,
        *,
        familiarity_delta: float,
        trust_delta: float,
        affinity_delta: float,
        relation_type: str | None = None,
    ) -> Relationship:
        relation = await self.get_pair(run_id, agent_id, other_agent_id)
        now = datetime.now(UTC)

        if relation is None:
            relation = Relationship(
                id=str(uuid4()),
                run_id=run_id,
                agent_id=agent_id,
                other_agent_id=other_agent_id,
                familiarity=0.0,
                trust=0.0,
                affinity=0.0,
                relation_type=relation_type or "acquaintance",
                last_interaction_at=now,
            )
            self.session.add(relation)

        relation.familiarity = min(1.0, max(0.0, relation.familiarity + familiarity_delta))
        relation.trust = min(1.0, max(-1.0, relation.trust + trust_delta))
        relation.affinity = min(1.0, max(-1.0, relation.affinity + affinity_delta))
        if relation_type:
            relation.relation_type = relation_type
        relation.last_interaction_at = now

        await self.session.flush()
        return relation


