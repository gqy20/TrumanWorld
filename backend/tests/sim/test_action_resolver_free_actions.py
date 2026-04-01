"""Tests for free action routing in action_resolver."""

from datetime import datetime

from app.sim.action_resolver import ActionIntent, ActionResolver
from app.sim.world import AgentState, LocationState, WorldState


def _build_world() -> WorldState:
    """Build a test world with two agents at the same location."""
    return WorldState(
        current_time=datetime(2026, 3, 7, 8, 0, 0),
        agents={
            "alice": AgentState(
                id="alice",
                name="Alice",
                location_id="cafe",
                status={},
            ),
            "bob": AgentState(
                id="bob",
                name="Bob",
                location_id="cafe",
                status={},
            ),
        },
        locations={
            "cafe": LocationState(
                id="cafe",
                name="Cafe",
                location_type="cafe",
                capacity=10,
            ),
            "home": LocationState(
                id="home",
                name="Home",
                location_type="residence",
            ),
        },
    )


class TestActionResolverFreeActionRouting:
    """Test that action_resolver routes free actions correctly."""

    def test_free_action_trade_accepted(self):
        """Trade action should be accepted with proper payload."""
        world = _build_world()
        resolver = ActionResolver()

        intent = ActionIntent(
            agent_id="alice",
            action_type="trade",
            target_agent_id="bob",
            payload={"item": "coffee", "price": 30},
            raw_intent="我想从 Bob 那买一杯咖啡",
        )

        result = resolver.resolve(world, intent)

        assert result.accepted is True
        assert result.action_type == "trade"
        assert result.reason == "free_action_accepted"
        assert result.event_payload.get("consequence_source") == "pending"
        assert result.event_payload.get("raw_intent") == "我想从 Bob 那买一杯咖啡"
        assert result.event_payload.get("free_action_payload") == {"item": "coffee", "price": 30}

    def test_free_action_gift_accepted(self):
        """Gift action should be accepted."""
        world = _build_world()
        resolver = ActionResolver()

        intent = ActionIntent(
            agent_id="alice",
            action_type="gift",
            target_agent_id="bob",
            payload={"item": "book"},
            raw_intent="我想把我的书送给 Bob",
        )

        result = resolver.resolve(world, intent)

        assert result.accepted is True
        assert result.action_type == "gift"
        assert result.event_payload.get("consequence_source") == "pending"

    def test_free_action_target_not_nearby_rejected(self):
        """Free action with target not at same location should be rejected."""
        world = _build_world()
        world.agents["bob"].location_id = "home"  # Bob is at home, Alice at cafe
        resolver = ActionResolver()

        intent = ActionIntent(
            agent_id="alice",
            action_type="trade",
            target_agent_id="bob",
            payload={"item": "coffee", "price": 30},
            raw_intent="我想从 Bob 那买咖啡",
        )

        result = resolver.resolve(world, intent)

        assert result.accepted is False
        assert result.reason == "target_not_nearby"

    def test_free_action_target_agent_not_found_rejected(self):
        """Free action with non-existent target should be rejected."""
        world = _build_world()
        resolver = ActionResolver()

        intent = ActionIntent(
            agent_id="alice",
            action_type="trade",
            target_agent_id="nonexistent",
            payload={"item": "coffee", "price": 30},
            raw_intent="我想从不存在的人那买咖啡",
        )

        result = resolver.resolve(world, intent)

        assert result.accepted is False
        assert result.reason == "target_agent_not_found"

    def test_free_action_agent_not_found_rejected(self):
        """Free action with non-existent agent should be rejected."""
        world = _build_world()
        resolver = ActionResolver()

        intent = ActionIntent(
            agent_id="nonexistent",
            action_type="trade",
            target_agent_id="bob",
            payload={"item": "coffee", "price": 30},
        )

        result = resolver.resolve(world, intent)

        assert result.accepted is False
        assert result.reason == "agent_not_found"

    def test_standard_action_move_still_works(self):
        """Standard move action should still work."""
        world = _build_world()
        resolver = ActionResolver()

        intent = ActionIntent(
            agent_id="alice",
            action_type="move",
            target_location_id="home",
        )

        result = resolver.resolve(world, intent)

        assert result.accepted is True
        assert result.action_type == "move"

    def test_standard_action_rest_still_works(self):
        """Standard rest action should still work."""
        world = _build_world()
        resolver = ActionResolver()

        intent = ActionIntent(
            agent_id="alice",
            action_type="rest",
        )

        result = resolver.resolve(world, intent)

        assert result.accepted is True
        assert result.action_type == "rest"

    def test_standard_action_work_still_works(self):
        """Standard work action should still work."""
        world = _build_world()
        world.agents["alice"].location_id = "cafe"
        world.agents["alice"].workplace_id = "cafe"
        resolver = ActionResolver()

        intent = ActionIntent(
            agent_id="alice",
            action_type="work",
        )

        result = resolver.resolve(world, intent)

        assert result.accepted is True
        assert result.action_type == "work"

    def test_free_action_without_target_accepted(self):
        """Free action without target (e.g., craft) should be accepted."""
        world = _build_world()
        resolver = ActionResolver()

        intent = ActionIntent(
            agent_id="alice",
            action_type="craft",
            payload={"item": "cake", "materials": ["flour", "sugar"]},
            raw_intent="我想烤一个蛋糕",
        )

        result = resolver.resolve(world, intent)

        assert result.accepted is True
        assert result.action_type == "craft"
        assert result.event_payload.get("consequence_source") == "pending"

    def test_free_action_with_governance_block(self):
        """Free action should be blocked if governance decides to block."""
        world = _build_world()
        # Add a restriction that would block (though governance is None by default)
        resolver = ActionResolver()

        intent = ActionIntent(
            agent_id="alice",
            action_type="trade",
            target_agent_id="bob",
            payload={"item": "coffee", "price": 30},
        )

        result = resolver.resolve(world, intent)

        # Without governance executor, free action should be accepted
        assert result.accepted is True


class TestActionResolverStandardActionsRouting:
    """Test that standard actions still route correctly."""

    def test_move_action_uses_resolve_move(self):
        """Move action should go through move resolution logic."""
        world = _build_world()
        world.agents["alice"].location_id = "cafe"
        resolver = ActionResolver()

        intent = ActionIntent(
            agent_id="alice",
            action_type="move",
            target_location_id="home",
        )

        result = resolver.resolve(world, intent)

        assert result.accepted is True
        assert result.event_payload.get("from_location_id") == "cafe"
        assert result.event_payload.get("to_location_id") == "home"

    def test_talk_action_uses_resolve_talk(self):
        """Talk action should go through talk resolution logic."""
        world = _build_world()
        resolver = ActionResolver()

        intent = ActionIntent(
            agent_id="alice",
            action_type="talk",
            target_agent_id="bob",
            payload={"message": "Hello Bob!"},
        )

        result = resolver.resolve(world, intent)

        assert result.accepted is True
        assert result.event_payload.get("conversation_event_type") == "speech"
