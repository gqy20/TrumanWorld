from __future__ import annotations

# ruff: noqa: F403,F405

from sqlalchemy import tuple_

from app.store.repository_modules._common import *


@dataclass(frozen=True, slots=True)
class RelationshipInteraction:
    agent_id: str
    other_agent_id: str
    familiarity_delta: float
    trust_delta: float
    affinity_delta: float
    relation_type: str | None = None


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
        relationships = await self.apply_interactions(
            run_id,
            [
                RelationshipInteraction(
                    agent_id=agent_id,
                    other_agent_id=other_agent_id,
                    familiarity_delta=familiarity_delta,
                    trust_delta=trust_delta,
                    affinity_delta=affinity_delta,
                    relation_type=relation_type,
                )
            ],
        )
        return relationships[(agent_id, other_agent_id)]

    async def apply_interactions(
        self,
        run_id: str,
        interactions: Sequence[RelationshipInteraction],
    ) -> dict[tuple[str, str], Relationship]:
        if not interactions:
            return {}
        pairs = {(item.agent_id, item.other_agent_id) for item in interactions}
        result = await self.session.execute(
            select(Relationship).where(
                Relationship.run_id == run_id,
                tuple_(Relationship.agent_id, Relationship.other_agent_id).in_(sorted(pairs)),
            )
        )
        relationships = {
            (relation.agent_id, relation.other_agent_id): relation for relation in result.scalars()
        }
        now = datetime.now(UTC)
        for interaction in interactions:
            pair = (interaction.agent_id, interaction.other_agent_id)
            relation = relationships.get(pair)
            if relation is None:
                relation = Relationship(
                    id=str(uuid4()),
                    run_id=run_id,
                    agent_id=interaction.agent_id,
                    other_agent_id=interaction.other_agent_id,
                    familiarity=0.0,
                    trust=0.0,
                    affinity=0.0,
                    relation_type=interaction.relation_type or "acquaintance",
                    last_interaction_at=now,
                )
                self.session.add(relation)
                relationships[pair] = relation
            relation.familiarity = min(
                1.0,
                max(0.0, relation.familiarity + interaction.familiarity_delta),
            )
            relation.trust = min(1.0, max(-1.0, relation.trust + interaction.trust_delta))
            relation.affinity = min(1.0, max(-1.0, relation.affinity + interaction.affinity_delta))
            if interaction.relation_type:
                relation.relation_type = interaction.relation_type
            relation.last_interaction_at = now
        await self.session.flush()
        return relationships
