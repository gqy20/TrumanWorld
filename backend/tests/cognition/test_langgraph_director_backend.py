from __future__ import annotations

from unittest.mock import patch

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
                  "target_agent_names": ["Meryl"],
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
        llm_model="claude-test",
        llm_api_key="langgraph-key",
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
                subject_agent_id="truman-1",
                subject_alert_score=0.86,
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
            support_roles=["cast"],
            recent_events=[],
            recent_interventions=[],
            world_time="2026-03-02T08:00:00+00:00",
        ),
        recent_goals=set(),
    )

    result = await backend.propose_intervention(invocation)

    assert result is not None
    assert result.scene_goal == "soft_check_in"
    assert result.target_agent_ids == ["cast-spouse"]
    assert result.priority == "high"
    assert result.urgency == "immediate"
    assert result.target_agent_id == "truman-1"
    assert result.cooldown_ticks == 4


def test_director_agent_parse_response_prefers_target_agent_names() -> None:
    from app.cognition.claude.director_agent import DirectorAgent, DirectorContext

    agent = DirectorAgent(Settings(agent_backend="heuristic", director_backend="claude_sdk"))
    context = DirectorContext(
        run_id="run-1",
        current_tick=5,
        assessment=DirectorAssessment(
            run_id="run-1",
            current_tick=5,
            subject_agent_id="truman-1",
            subject_alert_score=0.86,
            suspicion_level="high",
            continuity_risk="watch",
            focus_agent_ids=["truman-1"],
            notes=["Truman suspicion is high."],
        ),
        agents=[],
        support_roles=["cast"],
        recent_events=[],
        recent_interventions=[],
        world_time="2026-03-02T08:00:00+00:00",
    )
    cast_agents = [
        {
            "id": "cast-spouse",
            "name": "Meryl",
            "profile": {"world_role": "cast", "agent_config_id": "spouse"},
            "current_location_id": "home",
        },
        {
            "id": "cast-friend",
            "name": "Lauren",
            "profile": {"world_role": "cast", "agent_config_id": "friend"},
            "current_location_id": "square",
        },
    ]

    result = agent._parse_response(
        """
        {
          "should_intervene": true,
          "scene_goal": "soft_check_in",
          "target_agent_names": ["Lauren"],
          "priority": "high",
          "urgency": "immediate",
          "reasoning": "Prefer the new generic target field.",
          "message_hint": "Check in naturally.",
          "strategy": "calm reassurance",
          "cooldown_ticks": 4
        }
        """,
        context,
        cast_agents,
    )

    assert result is not None
    assert result.target_agent_ids == ["cast-friend"]


def test_director_agent_builds_prompt_with_generic_subject_vocabulary() -> None:
    from app.cognition.claude.director_agent import DirectorAgent, DirectorContext

    agent = DirectorAgent(Settings(agent_backend="heuristic", director_backend="claude_sdk"))
    prompt = agent._build_decision_prompt(
        DirectorContext(
            run_id="run-1",
            current_tick=5,
            assessment=DirectorAssessment(
                run_id="run-1",
                current_tick=5,
                subject_agent_id="subject-1",
                subject_alert_score=0.86,
                suspicion_level="high",
                continuity_risk="watch",
                focus_agent_ids=["subject-1"],
                notes=["Subject alert is high."],
            ),
            agents=[],
            support_roles=["cast"],
            recent_events=[],
            recent_interventions=[],
            world_time="2026-03-02T08:00:00+00:00",
        ),
        [
            {
                "id": "cast-spouse",
                "name": "Meryl",
                "profile": {"world_role": "cast", "agent_config_id": "spouse"},
                "current_location_id": "home",
            }
        ],
        set(),
    )

    assert "Subject Status" in prompt
    assert "subject-1" in prompt
    assert "0.86" in prompt


async def test_langgraph_director_backend_uses_context_support_roles() -> None:
    from app.cognition.claude.director_agent import DirectorContext
    from app.cognition.langgraph.director_backend import LangGraphDirectorBackend

    class FakeTextResponse:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeTextModel:
        async def ainvoke(self, prompt: str):
            return FakeTextResponse(
                """
                {
                  "should_intervene": true,
                  "scene_goal": "soft_check_in",
                  "target_agent_names": ["Aly"],
                  "priority": "high",
                  "urgency": "immediate",
                  "reasoning": "Subject alert is high.",
                  "message_hint": "Check in naturally.",
                  "strategy": "calm reassurance",
                  "cooldown_ticks": 4
                }
                """
            )

    settings = Settings(
        agent_backend="heuristic",
        director_backend="langgraph",
        llm_model="claude-test",
        llm_api_key="langgraph-key",
    )
    backend = LangGraphDirectorBackend(settings=settings, text_model=FakeTextModel())
    invocation = DirectorDecisionInvocation(
        prompt="",
        context=DirectorContext(
            run_id="run-2",
            current_tick=5,
            assessment=DirectorAssessment(
                run_id="run-2",
                current_tick=5,
                subject_agent_id="hero-1",
                subject_alert_score=0.86,
                suspicion_level="high",
                continuity_risk="watch",
                focus_agent_ids=["hero-1"],
                notes=["Subject alert is high."],
            ),
            agents=[
                {
                    "id": "ally-1",
                    "name": "Aly",
                    "profile": {"world_role": "ally", "agent_config_id": "friend"},
                    "current_location_id": "home",
                },
                {
                    "id": "hero-1",
                    "name": "Hero",
                    "profile": {"world_role": "protagonist"},
                    "current_location_id": "square",
                },
            ],
            support_roles=["ally"],
            recent_events=[],
            recent_interventions=[],
            world_time="2026-03-02T08:00:00+00:00",
        ),
        recent_goals=set(),
    )

    result = await backend.propose_intervention(invocation)

    assert result is not None
    assert result.target_agent_ids == ["ally-1"]


def test_langgraph_director_backend_builds_openai_model_from_langgraph_settings() -> None:
    from app.cognition.langgraph.director_backend import LangGraphDirectorBackend

    settings = Settings(
        agent_backend="heuristic",
        director_backend="langgraph",
        llm_provider="openai",
        llm_model="gpt-4.1-mini",
        llm_api_key="openai-key",
        llm_base_url="https://example.invalid/v1",
        llm_enable_thinking=False,
        llm_thinking_budget=64,
    )
    captured: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    with patch("langchain_openai.ChatOpenAI", FakeChatOpenAI):
        backend = LangGraphDirectorBackend(settings=settings)

    assert backend._text_model is not None
    assert captured["model"] == "gpt-4.1-mini"
    assert captured["api_key"] == "openai-key"
    assert captured["base_url"] == "https://example.invalid/v1"
    assert captured["temperature"] == 0
    assert captured["extra_body"] == {
        "enable_thinking": False,
        "thinking_budget": 64,
    }
