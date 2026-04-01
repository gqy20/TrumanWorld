"""Tests for state_delta_models."""


from app.sim.state_delta_models import (
    AgentDelta,
    MemoryFragment,
    RelationshipDelta,
    StateDelta,
    WorldDelta,
)


class TestAgentDelta:
    """Test AgentDelta model."""

    def test_defaults(self):
        """Test default values."""
        delta = AgentDelta()

        assert delta.cash_delta == 0.0
        assert delta.food_security_delta == 0.0
        assert delta.housing_security_delta == 0.0
        assert delta.inventory_add == []
        assert delta.inventory_remove == []
        assert delta.employment_status is None
        assert delta.status_updates == {}

    def test_full_delta(self):
        """Test full agent delta."""
        delta = AgentDelta(
            cash_delta=30.0,
            food_security_delta=0.1,
            inventory_add=["coffee"],
            inventory_remove=["money"],
            employment_status="self_employed",
            status_updates={"note": "test"},
        )

        assert delta.cash_delta == 30.0
        assert delta.food_security_delta == 0.1
        assert delta.inventory_add == ["coffee"]
        assert delta.inventory_remove == ["money"]
        assert delta.employment_status == "self_employed"


class TestWorldDelta:
    """Test WorldDelta model."""

    def test_defaults(self):
        """Test default values."""
        delta = WorldDelta()

        assert delta.location_effects == {}

    def test_with_effects(self):
        """Test with location effects."""
        delta = WorldDelta(
            location_effects={"cafe": {"crowd_level": "high"}}
        )

        assert delta.location_effects == {"cafe": {"crowd_level": "high"}}


class TestRelationshipDelta:
    """Test RelationshipDelta model."""

    def test_defaults(self):
        """Test default values."""
        delta = RelationshipDelta()

        assert delta.familiarity_delta == 0.0
        assert delta.trust_delta == 0.0
        assert delta.affinity_delta == 0.0

    def test_full_delta(self):
        """Test full relationship delta."""
        delta = RelationshipDelta(
            familiarity_delta=0.2,
            trust_delta=0.1,
            affinity_delta=0.15,
        )

        assert delta.familiarity_delta == 0.2
        assert delta.trust_delta == 0.1
        assert delta.affinity_delta == 0.15


class TestMemoryFragment:
    """Test MemoryFragment model."""

    def test_creation(self):
        """Test memory fragment creation."""
        fragment = MemoryFragment(
            agent_id="alice",
            content="Alice bought a coffee from Bob",
        )

        assert fragment.agent_id == "alice"
        assert fragment.content == "Alice bought a coffee from Bob"


class TestStateDelta:
    """Test StateDelta model."""

    def test_validate_currency_conservation_balanced(self):
        """Test that balanced cash deltas pass validation."""
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(cash_delta=-30.0),
                "bob": AgentDelta(cash_delta=30.0),
            },
            effect_type="trade",
            reason="Alice bought coffee from Bob",
        )

        assert delta.validate_currency_conservation() is True

    def test_validate_currency_conservation_unbalanced(self):
        """Test that unbalanced cash deltas fail validation."""
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(cash_delta=-30.0),
                "bob": AgentDelta(cash_delta=25.0),  # 5 less than needed
            },
            effect_type="trade",
            reason="Invalid trade",
        )

        assert delta.validate_currency_conservation() is False

    def test_validate_currency_conservation_zero_sum(self):
        """Test that zero sum passes validation."""
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(cash_delta=0.0),
            },
            effect_type="rest",
            reason="Resting",
        )

        assert delta.validate_currency_conservation() is True

    def test_validate_currency_conservation_small_tolerance(self):
        """Test that small rounding errors are tolerated."""
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(cash_delta=-30.001),
                "bob": AgentDelta(cash_delta=30.0),
            },
            effect_type="trade",
            reason="Trade with small rounding",
        )

        # Should pass because difference < 0.01
        assert delta.validate_currency_conservation() is True

    def test_validate_bounds_valid(self):
        """Test bounds validation with valid values."""
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(
                    cash_delta=-30.0,
                    food_security_delta=-0.1,
                    status_updates={
                        "food_security_after": 0.8,
                        "cash_before": 50.0,  # 50 - 30 = 20, not negative
                    },
                ),
            },
            effect_type="trade",
            reason="Trade",
        )

        errors = delta.validate_bounds()

        assert len(errors) == 0

    def test_validate_bounds_food_security_out_of_range(self):
        """Test bounds validation with food security out of range."""
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(
                    food_security_delta=-0.1,
                    status_updates={"food_security_after": 1.5},  # > 1.0
                ),
            },
            effect_type="trade",
            reason="Trade",
        )

        errors = delta.validate_bounds()

        assert len(errors) == 1
        assert "food_security" in errors[0]

    def test_validate_bounds_negative_cash(self):
        """Test bounds validation with negative cash result."""
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(
                    cash_delta=-50.0,
                    status_updates={"cash_before": 20.0},  # Would go to -30
                ),
            },
            effect_type="trade",
            reason="Trade",
        )

        errors = delta.validate_bounds()

        assert len(errors) == 1
        assert "negative" in errors[0]

    def test_full_trade_delta(self):
        """Test a complete trade state delta."""
        delta = StateDelta(
            agent_deltas={
                "alice": AgentDelta(
                    cash_delta=-30.0,
                    inventory_add=["coffee"],
                ),
                "bob": AgentDelta(
                    cash_delta=30.0,
                    inventory_remove=["coffee"],
                ),
            },
            world_deltas=WorldDelta(),
            relationship_deltas={
                "alice:bob": RelationshipDelta(
                    familiarity_delta=0.1,
                    trust_delta=0.05,
                    affinity_delta=0.1,
                ),
            },
            memory_fragments=[
                MemoryFragment(
                    agent_id="alice",
                    content="Bought a coffee from Bob for 30 yuan",
                ),
                MemoryFragment(
                    agent_id="bob",
                    content="Sold a coffee to Alice for 30 yuan",
                ),
            ],
            effect_type="trade",
            reason="Alice bought coffee from Bob",
        )

        assert delta.validate_currency_conservation() is True
        assert delta.agent_deltas["alice"].cash_delta == -30.0
        assert delta.agent_deltas["bob"].cash_delta == 30.0
        assert delta.relationship_deltas["alice:bob"].familiarity_delta == 0.1
        assert len(delta.memory_fragments) == 2
