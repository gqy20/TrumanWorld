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


async def test_langgraph_backend_uses_structured_model_decision() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    class FakeStructuredModel:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, prompt: str):
            self.prompts.append(prompt)
            return {
                "action_type": "talk",
                "target_agent_id": "bob",
                "message": "Morning, Bob.",
                "payload": {"source": "langgraph-model"},
            }

    model = FakeStructuredModel()
    backend = LangGraphAgentBackend(decision_model=model)
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={"world": {"current_goal": "talk", "nearby_agent_id": "bob"}},
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    result = await backend.decide_action(invocation)

    assert result.action_type == "talk"
    assert result.target_agent_id == "bob"
    assert result.message == "Morning, Bob."
    assert result.payload == {"source": "langgraph-model"}
    assert model.prompts
    assert "Pick the next action." in model.prompts[0]


async def test_langgraph_backend_falls_back_when_model_errors() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    class FailingStructuredModel:
        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, prompt: str):
            raise RuntimeError("model unavailable")

    backend = LangGraphAgentBackend(decision_model=FailingStructuredModel())
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
