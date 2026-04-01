"""State delta models for free action consequences."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentDelta(BaseModel):
    """Individual agent state changes from a free action."""

    cash_delta: float = 0.0
    food_security_delta: float = 0.0
    housing_security_delta: float = 0.0
    inventory_add: list[str] = Field(default_factory=list)
    inventory_remove: list[str] = Field(default_factory=list)
    employment_status: str | None = None
    status_updates: dict[str, Any] = Field(default_factory=dict)


class WorldDelta(BaseModel):
    """World-level state changes from a free action."""

    location_effects: dict[str, Any] = Field(default_factory=dict)


class RelationshipDelta(BaseModel):
    """Relationship changes between two agents."""

    familiarity_delta: float = 0.0
    trust_delta: float = 0.0
    affinity_delta: float = 0.0


class MemoryFragment(BaseModel):
    """Memory fragment generated from a free action."""

    agent_id: str
    content: str


class StateDelta(BaseModel):
    """Complete state delta from a free action consequence."""

    agent_deltas: dict[str, AgentDelta] = Field(default_factory=dict)
    world_deltas: WorldDelta = Field(default_factory=WorldDelta)
    relationship_deltas: dict[str, RelationshipDelta] = Field(default_factory=dict)
    memory_fragments: list[MemoryFragment] = Field(default_factory=list)
    effect_type: str
    reason: str

    def validate_currency_conservation(self) -> bool:
        """Validate that cash deltas sum to zero (currency conservation).

        Returns:
            True if cash is conserved (sum of all cash_deltas is approximately 0),
            False otherwise.
        """
        total = sum(d.cash_delta for d in self.agent_deltas.values())
        return abs(total) < 0.01

    def validate_bounds(self) -> list[str]:
        """Validate that state changes are within acceptable bounds.

        Returns:
            List of validation error messages. Empty list if valid.
        """
        errors = []
        for agent_id, delta in self.agent_deltas.items():
            if delta.food_security_delta != 0:
                new_value = delta.status_updates.get("food_security_after", float("inf"))
                if abs(new_value) > 1.0:
                    errors.append(f"{agent_id}: food_security out of bounds [0, 1]")
            if delta.cash_delta < 0:
                current = delta.status_updates.get("cash_before", 0)
                if current + delta.cash_delta < 0:
                    errors.append(f"{agent_id}: cash would go negative")
        return errors
