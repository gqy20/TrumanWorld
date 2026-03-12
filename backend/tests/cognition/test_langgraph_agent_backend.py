from __future__ import annotations

from app.cognition.registry import CognitionRegistry
from app.cognition.types import AgentActionInvocation
from app.infra.settings import Settings


def test_registry_builds_langgraph_agent_backend() -> None:
    settings = Settings(agent_backend="langgraph", director_backend="heuristic")

    backend = CognitionRegistry(settings).build_agent_backend()

    assert backend.__class__.__name__ == "LangGraphAgentBackend"


async def test_langgraph_backend_decides_move_for_direct_goal() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    backend = LangGraphAgentBackend()
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={
            "world": {
                "current_goal": "move:town-square",
                "known_location_ids": ["town-square", "home"],
            }
        },
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    result = await backend.decide_action(invocation)

    assert result.action_type == "move"
    assert result.target_location_id == "town-square"


async def test_langgraph_backend_falls_back_to_rest_without_directive() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    backend = LangGraphAgentBackend()
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={"world": {"current_goal": "talk", "known_location_ids": ["town-square"]}},
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    result = await backend.decide_action(invocation)

    assert result.action_type == "rest"
