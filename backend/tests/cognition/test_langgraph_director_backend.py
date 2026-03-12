from __future__ import annotations

from app.cognition.registry import CognitionRegistry
from app.cognition.types import DirectorDecisionInvocation
from app.director.observer import DirectorAssessment
from app.infra.settings import Settings


def test_registry_builds_langgraph_director_backend() -> None:
    settings = Settings(agent_backend="heuristic", director_backend="langgraph")

    backend = CognitionRegistry(settings).build_director_backend()

    assert backend.__class__.__name__ == "LangGraphDirectorBackend"


async def test_langgraph_director_backend_proposes_plan() -> None:
    from app.cognition.claude.director_agent import DirectorContext
    from app.cognition.langgraph.director_backend import LangGraphDirectorBackend

    class FakeTextResponse:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeTextModel:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def ainvoke(self, prompt: str):
            self.prompts.append(prompt)
            return FakeTextResponse(
                """
                {
                  "should_intervene": true,
                  "scene_goal": "soft_check_in",
                  "target_cast_names": ["Meryl"],
                  "priority": "high",
                  "urgency": "immediate",
                  "reasoning": "Truman suspicion is high.",
                  "message_hint": "Check in naturally.",
                  "strategy": "calm reassurance",
                  "cooldown_ticks": 4
                }
                """
            )

    settings = Settings(
        agent_backend="heuristic",
        director_backend="langgraph",
        langgraph_model="claude-test",
        langgraph_api_key="langgraph-key",
    )
    backend = LangGraphDirectorBackend(settings=settings, text_model=FakeTextModel())
    invocation = DirectorDecisionInvocation(
        prompt="",
        context=DirectorContext(
            run_id="run-1",
            current_tick=5,
            assessment=DirectorAssessment(
                run_id="run-1",
                current_tick=5,
                truman_agent_id="truman-1",
                truman_suspicion_score=0.86,
                suspicion_level="high",
                continuity_risk="watch",
                focus_agent_ids=["truman-1"],
                notes=["Truman suspicion is high."],
            ),
            agents=[
                {
                    "id": "cast-spouse",
                    "name": "Meryl",
                    "profile": {"world_role": "cast", "agent_config_id": "spouse"},
                    "current_location_id": "home",
                },
                {
                    "id": "truman-1",
                    "name": "Truman",
                    "profile": {"world_role": "truman"},
                    "current_location_id": "square",
                },
            ],
            recent_events=[],
            recent_interventions=[],
            world_time="2026-03-02T08:00:00+00:00",
        ),
        recent_goals=set(),
    )

    result = await backend.propose_intervention(invocation)

    assert result is not None
    assert result.scene_goal == "soft_check_in"
    assert result.target_cast_ids == ["cast-spouse"]
    assert result.priority == "high"
    assert result.urgency == "immediate"
    assert result.target_agent_id == "truman-1"
    assert result.cooldown_ticks == 4
