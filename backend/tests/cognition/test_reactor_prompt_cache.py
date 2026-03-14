"""Tests for reactor prompt caching functionality."""

import pytest

from app.cognition.langgraph.agent_backend import LangGraphAgentBackend
from app.cognition.types import AgentActionInvocation
from app.infra.settings import Settings


class TestReactorPromptCache:
    """Test suite for reactor prompt caching."""

    @pytest.fixture
    def backend_with_cache_enabled(self) -> LangGraphAgentBackend:
        """Create backend with prompt cache enabled."""
        return LangGraphAgentBackend(
            settings=Settings(
                agent_backend="langgraph",
                langgraph_reactor_prompt_cache_enabled=True,
            )
        )

    @pytest.fixture
    def backend_with_cache_disabled(self) -> LangGraphAgentBackend:
        """Create backend with prompt cache disabled."""
        return LangGraphAgentBackend(
            settings=Settings(
                agent_backend="langgraph",
                langgraph_reactor_prompt_cache_enabled=False,
            )
        )

    @pytest.fixture
    def sample_invocation(self) -> AgentActionInvocation:
        """Create a sample invocation for testing."""
        return AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action.",
            context={
                "world": {
                    "current_goal": "rest",
                    "known_location_ids": ["town-square", "home"],
                }
            },
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["move", "talk", "work", "rest"],
        )

    def test_reactor_prompt_has_agent_context_json_marker(
        self, backend_with_cache_enabled: LangGraphAgentBackend
    ) -> None:
        """Reactor prompt should contain 'Agent context JSON:' marker."""
        invocation = AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action.",
            context={"world": {"current_goal": "rest"}},
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["rest"],
        )
        full_prompt = backend_with_cache_enabled._build_text_json_prompt(invocation)
        assert "Agent context JSON:" in full_prompt

        # Also verify the marker comes before the dynamic context
        marker_pos = full_prompt.find("Agent context JSON:")
        context_pos = full_prompt.find('{"world"')
        assert marker_pos is not None
        assert context_pos is not None
        assert marker_pos < context_pos

    def test_split_reactor_prompt_splits_at_agent_context_json_marker(
        self, backend_with_cache_enabled: LangGraphAgentBackend
    ) -> None:
        """_split_reactor_prompt should split at 'Agent context JSON:' marker."""
        invocation = AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action.",
            context={"world": {"current_goal": "rest", "tick": 5}},
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["rest"],
        )
        stable_prefix, dynamic_suffix = backend_with_cache_enabled._split_reactor_prompt(invocation)

        # Stable prefix should NOT contain the dynamic context
        assert '"world"' not in stable_prefix
        assert '"tick"' not in stable_prefix

        # Marker should be at the end of stable prefix
        assert stable_prefix.endswith("Agent context JSON:")

        # Dynamic suffix should contain only the context JSON (no marker)
        assert dynamic_suffix.startswith("{")
        assert '"world"' in dynamic_suffix
        assert '"tick"' in dynamic_suffix

    def test_stable_prefix_is_consistent_across_different_contexts(
        self, backend_with_cache_enabled: LangGraphAgentBackend
    ) -> None:
        """Stable prefix should be identical when only dynamic context changes."""
        invocation1 = AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action.",
            context={"world": {"current_goal": "rest", "tick": 1}},
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["rest"],
        )
        invocation2 = AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action.",
            context={"world": {"current_goal": "work", "tick": 100}},  # Different context
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["rest"],
        )

        stable1, _ = backend_with_cache_enabled._split_reactor_prompt(invocation1)
        stable2, _ = backend_with_cache_enabled._split_reactor_prompt(invocation2)

        # Stable prefixes should be identical
        assert stable1 == stable2

    def test_dynamic_suffix_varies_with_context(
        self, backend_with_cache_enabled: LangGraphAgentBackend
    ) -> None:
        """Dynamic suffix should vary when context changes."""
        invocation1 = AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action.",
            context={"world": {"tick": 1}},
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["rest"],
        )
        invocation2 = AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action.",
            context={"world": {"tick": 100}},  # Different tick
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["rest"],
        )

        _, dynamic1 = backend_with_cache_enabled._split_reactor_prompt(invocation1)
        _, dynamic2 = backend_with_cache_enabled._split_reactor_prompt(invocation2)

        # Dynamic suffixes should be different
        assert dynamic1 != dynamic2
        assert '"tick": 1' in dynamic1
        assert '"tick": 100' in dynamic2

    def test_build_reactor_messages_with_cache_enabled_returns_message_blocks(
        self,
        backend_with_cache_enabled: LangGraphAgentBackend,
        sample_invocation: AgentActionInvocation,
    ) -> None:
        """When cache is enabled, _build_reactor_messages should return list of HumanMessage with cache_control."""
        from langchain_core.messages import HumanMessage

        result = backend_with_cache_enabled._build_reactor_messages(sample_invocation)

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)

        # Verify message content structure
        content = result[0].content
        assert isinstance(content, list)
        assert len(content) >= 1

        # First block should have cache_control
        first_block = content[0]
        assert isinstance(first_block, dict)
        assert first_block.get("cache_control") == {"type": "ephemeral"}

    def test_build_reactor_messages_with_cache_disabled_returns_string(
        self,
        backend_with_cache_disabled: LangGraphAgentBackend,
        sample_invocation: AgentActionInvocation,
    ) -> None:
        """When cache is disabled, _build_reactor_messages should return plain string."""
        result = backend_with_cache_disabled._build_reactor_messages(sample_invocation)

        assert isinstance(result, str)
        assert "Pick the next action." in result

    def test_cache_control_only_on_stable_prefix(
        self, backend_with_cache_enabled: LangGraphAgentBackend
    ) -> None:
        """cache_control should only be on the stable prefix block, not dynamic suffix."""
        invocation = AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action.",
            context={"world": {"current_goal": "rest"}},
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["rest"],
        )
        result = backend_with_cache_enabled._build_reactor_messages(invocation)

        content = result[0].content
        assert len(content) == 2, "Should have stable and dynamic blocks"

        # First block (stable) should have cache_control
        assert content[0].get("cache_control") == {"type": "ephemeral"}

        # Second block (dynamic) should NOT have cache_control
        assert content[1].get("cache_control") is None

    def test_empty_context_still_works(
        self, backend_with_cache_enabled: LangGraphAgentBackend
    ) -> None:
        """Should handle empty context gracefully."""
        invocation = AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action.",
            context={},  # Empty context
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["rest"],
        )

        # Should not raise
        stable_prefix, dynamic_suffix = backend_with_cache_enabled._split_reactor_prompt(invocation)

        # Should still split properly
        assert isinstance(stable_prefix, str)
        assert isinstance(dynamic_suffix, str)

    def test_json_schema_in_stable_prefix(
        self, backend_with_cache_enabled: LangGraphAgentBackend
    ) -> None:
        """JSON schema should be in stable prefix for cache efficiency."""
        invocation = AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action.",
            context={"world": {"tick": 1}},
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["move", "talk", "work", "rest"],
        )
        stable_prefix, dynamic_suffix = backend_with_cache_enabled._split_reactor_prompt(invocation)

        # JSON schema should be in stable prefix (for caching)
        assert '"action_type"' in stable_prefix
        assert '"type": "string"' in stable_prefix
        assert '"properties"' in stable_prefix

        # JSON schema should NOT be in dynamic suffix
        assert '"action_type"' not in dynamic_suffix

    def test_return_instructions_in_stable_prefix(
        self, backend_with_cache_enabled: LangGraphAgentBackend
    ) -> None:
        """Return instructions should be in stable prefix for cache efficiency."""
        invocation = AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action.",
            context={"world": {"tick": 1}},
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["rest"],
        )
        stable_prefix, dynamic_suffix = backend_with_cache_enabled._split_reactor_prompt(invocation)

        # Return instructions should be in stable prefix
        assert "Return only the structured action decision" in stable_prefix
        assert "If native structured output is unavailable" in stable_prefix

        # These instructions should NOT be in dynamic suffix
        assert "Return only the structured action decision" not in dynamic_suffix

    def test_only_context_json_in_dynamic_suffix(
        self, backend_with_cache_enabled: LangGraphAgentBackend
    ) -> None:
        """Only the context JSON should be in dynamic suffix."""
        invocation = AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action.",
            context={"world": {"tick": 1, "current_goal": "rest"}},
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["rest"],
        )
        stable_prefix, dynamic_suffix = backend_with_cache_enabled._split_reactor_prompt(invocation)

        # Dynamic suffix should start with the context JSON
        assert dynamic_suffix.startswith("{")
        assert '"world"' in dynamic_suffix
        assert '"tick"' in dynamic_suffix

        # Dynamic suffix should NOT contain instructions or schema
        assert "Return only" not in dynamic_suffix
        assert "action_type" not in dynamic_suffix

    def test_stable_prefix_size_is_optimized(
        self, backend_with_cache_enabled: LangGraphAgentBackend
    ) -> None:
        """Stable prefix should be large enough for effective caching (target: >300 tokens)."""
        invocation = AgentActionInvocation(
            agent_id="alice",
            prompt="Pick the next action. You are a helpful assistant in a simulation world.",
            context={"world": {"tick": 1}},
            max_turns=2,
            max_budget_usd=0.1,
            allowed_actions=["move", "talk", "work", "rest"],
        )
        stable_prefix, dynamic_suffix = backend_with_cache_enabled._split_reactor_prompt(invocation)

        # Rough token estimation: chars / 4
        stable_tokens_estimate = len(stable_prefix) // 4

        # Target: stable prefix should be >250 tokens (roughly >1000 chars)
        # This ensures JSON schema + instructions are cached
        assert stable_tokens_estimate > 250, (
            f"Stable prefix too small: {stable_tokens_estimate} tokens ({len(stable_prefix)} chars). "
            f"Expected >250 tokens for effective caching."
        )

        # Dynamic suffix should be relatively small (<250 tokens)
        dynamic_tokens_estimate = len(dynamic_suffix) // 4
        assert dynamic_tokens_estimate < 250, (
            f"Dynamic suffix too large: {dynamic_tokens_estimate} tokens ({len(dynamic_suffix)} chars). "
            f"Expected <250 tokens."
        )
