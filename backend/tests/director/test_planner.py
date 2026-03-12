import pytest
import asyncio

from app.director.observer import DirectorAssessment, SuspicionTrend
from app.director.planner import DirectorPlanner
from app.protocol.simulation import (
    DIRECTOR_SCENE_BREAK_ISOLATION,
    DIRECTOR_SCENE_PREEMPTIVE_COMFORT,
    DIRECTOR_SCENE_REJECTION_RECOVERY,
    DIRECTOR_SCENE_SOFT_CHECK_IN,
)
from app.store.models import Agent


def _make_cast_agent(agent_id: str, name: str, config_id: str = "spouse") -> Agent:
    return Agent(
        id=agent_id,
        run_id="run-1",
        name=name,
        occupation="resident",
        profile={"world_role": "cast", "agent_config_id": config_id},
        personality={},
        status={},
        current_plan={},
    )


def _make_truman_agent(suspicion_score: float = 0.0) -> Agent:
    return Agent(
        id="truman-1",
        run_id="run-1",
        name="Truman",
        occupation="resident",
        profile={"world_role": "truman"},
        personality={},
        status={"suspicion_score": suspicion_score},
        current_plan={},
    )


@pytest.mark.asyncio
async def test_director_planner_builds_soft_check_in_plan_for_high_suspicion():
    planner = DirectorPlanner()
    agents = [
        _make_cast_agent("cast-spouse", "Meryl", "spouse"),
        _make_truman_agent(0.86),
    ]
    assessment = DirectorAssessment(
        run_id="run-1",
        current_tick=5,
        truman_agent_id="truman-1",
        truman_suspicion_score=0.86,
        suspicion_level="high",
        continuity_risk="watch",
        focus_agent_ids=["truman-1"],
        notes=["Truman 的怀疑度已经明显升高。"],
    )

    plan = await planner.build_plan(assessment=assessment, agents=agents)

    assert plan is not None
    assert plan.scene_goal == DIRECTOR_SCENE_SOFT_CHECK_IN
    assert plan.target_cast_ids == ["cast-spouse"]
    assert plan.priority == "advisory"
    assert plan.target_agent_id == "truman-1"


@pytest.mark.asyncio
async def test_director_planner_builds_preemptive_comfort_for_rapid_rise():
    """测试怀疑度快速上升时触发预防性安抚"""
    planner = DirectorPlanner()
    agents = [
        _make_cast_agent("cast-friend", "Bob", "friend"),
        _make_truman_agent(0.35),
    ]

    # 模拟怀疑度快速上升：从 0.1 到 0.35
    trend = SuspicionTrend(
        current_score=0.35,
        previous_score=0.10,
        delta=0.25,
        trend_type="rapid_rise",
    )
    assessment = DirectorAssessment(
        run_id="run-1",
        current_tick=5,
        truman_agent_id="truman-1",
        truman_suspicion_score=0.35,
        suspicion_level="guarded",  # 不高，但趋势是快速上升
        suspicion_trend=trend,
        continuity_risk="stable",
        focus_agent_ids=["truman-1"],
        notes=[],
    )

    plan = await planner.build_plan(assessment=assessment, agents=agents)

    assert plan is not None
    assert plan.scene_goal == DIRECTOR_SCENE_PREEMPTIVE_COMFORT
    assert plan.urgency == "immediate"
    assert "不安" in plan.message_hint or "转移注意力" in plan.message_hint


@pytest.mark.asyncio
async def test_director_planner_builds_break_isolation_for_lonely_truman():
    """测试 Truman 长时间独处时触发打破隔离"""
    planner = DirectorPlanner()
    agents = [
        _make_cast_agent("cast-neighbor", "Neighbor", "neighbor"),
        _make_truman_agent(0.2),
    ]
    assessment = DirectorAssessment(
        run_id="run-1",
        current_tick=10,
        truman_agent_id="truman-1",
        truman_suspicion_score=0.2,
        suspicion_level="low",
        continuity_risk="stable",
        truman_isolation_ticks=6,  # 长时间独处
        focus_agent_ids=["truman-1"],
        notes=[],
    )

    plan = await planner.build_plan(assessment=assessment, agents=agents)

    assert plan is not None
    assert plan.scene_goal == DIRECTOR_SCENE_BREAK_ISOLATION
    assert plan.cooldown_ticks == 4  # 隔离场景冷却时间较长


@pytest.mark.asyncio
async def test_director_planner_builds_rejection_recovery_for_multiple_rejections():
    """测试连续被拒绝时触发恢复计划"""
    planner = DirectorPlanner()
    agents = [
        _make_cast_agent("cast-spouse", "Meryl", "spouse"),
        _make_truman_agent(0.4),
    ]
    assessment = DirectorAssessment(
        run_id="run-1",
        current_tick=8,
        truman_agent_id="truman-1",
        truman_suspicion_score=0.4,
        suspicion_level="guarded",
        continuity_risk="elevated",
        recent_rejections=3,  # 多次被拒绝
        focus_agent_ids=["truman-1"],
        notes=[],
    )

    plan = await planner.build_plan(assessment=assessment, agents=agents)

    assert plan is not None
    assert plan.scene_goal == DIRECTOR_SCENE_REJECTION_RECOVERY
    assert plan.urgency == "immediate"
    assert "拒绝" in plan.reason or "拒绝" in plan.message_hint


@pytest.mark.asyncio
async def test_director_planner_avoids_duplicate_interventions():
    """测试避免重复干预"""
    planner = DirectorPlanner()
    agents = [
        _make_cast_agent("cast-spouse", "Meryl", "spouse"),
        _make_truman_agent(0.86),
    ]
    assessment = DirectorAssessment(
        run_id="run-1",
        current_tick=10,
        truman_agent_id="truman-1",
        truman_suspicion_score=0.86,
        suspicion_level="high",
        continuity_risk="stable",
        focus_agent_ids=["truman-1"],
        notes=[],
    )

    # 第一次应该生成计划
    plan1 = await planner.build_plan(
        assessment=assessment,
        agents=agents,
        recent_intervention_goals=[],
    )
    assert plan1 is not None

    # 第二次，如果最近已经有相同的干预，应该返回 None 或其他计划
    plan2 = await planner.build_plan(
        assessment=assessment,
        agents=agents,
        recent_intervention_goals=[DIRECTOR_SCENE_SOFT_CHECK_IN],
    )
    # 由于 soft_check_in 已在 recent_goals 中，应该返回 None
    assert plan2 is None


@pytest.mark.asyncio
async def test_director_planner_prioritizes_rapid_rise_over_high_suspicion():
    """测试快速上升优先于高怀疑度"""
    planner = DirectorPlanner()
    agents = [
        _make_cast_agent("cast-spouse", "Meryl", "spouse"),
        _make_truman_agent(0.85),
    ]

    # 高怀疑度 + 快速上升
    trend = SuspicionTrend(
        current_score=0.85,
        previous_score=0.60,
        delta=0.25,
        trend_type="rapid_rise",
    )
    assessment = DirectorAssessment(
        run_id="run-1",
        current_tick=5,
        truman_agent_id="truman-1",
        truman_suspicion_score=0.85,
        suspicion_level="high",
        suspicion_trend=trend,
        continuity_risk="stable",
        focus_agent_ids=["truman-1"],
        notes=[],
    )

    plan = await planner.build_plan(assessment=assessment, agents=agents)

    # 快速上升应该优先
    assert plan is not None
    assert plan.scene_goal == DIRECTOR_SCENE_PREEMPTIVE_COMFORT
    assert plan.urgency == "immediate"


@pytest.mark.asyncio
async def test_director_planner_consumes_langgraph_backend_async_result():
    from app.cognition.langgraph.director_backend import LangGraphDirectorBackend
    from app.infra.settings import Settings

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
                  "target_cast_names": ["Meryl"],
                  "priority": "normal",
                  "urgency": "advisory",
                  "reasoning": "A gentle check-in keeps the scene natural.",
                  "message_hint": "Check in with Truman naturally.",
                  "strategy": "soft reassurance",
                  "cooldown_ticks": 3
                }
                """
            )

    planner = DirectorPlanner(
        backend=LangGraphDirectorBackend(
            settings=Settings(
                agent_backend="heuristic",
                director_backend="langgraph",
                langgraph_model="claude-test",
                langgraph_api_key="langgraph-key",
            ),
            text_model=FakeTextModel(),
        )
    )
    agents = [
        _make_cast_agent("cast-spouse", "Meryl", "spouse"),
        _make_truman_agent(0.1),
    ]
    assessment = DirectorAssessment(
        run_id="run-1",
        current_tick=5,
        truman_agent_id="truman-1",
        truman_suspicion_score=0.1,
        suspicion_level="low",
        continuity_risk="stable",
        focus_agent_ids=["truman-1"],
        notes=[],
    )

    first = await planner.build_plan(
        assessment=assessment,
        agents=agents,
        current_tick=5,
        world_time="2026-03-02T08:00:00+00:00",
        run_id="run-1",
    )
    await asyncio.sleep(0)
    second = await planner.build_plan(
        assessment=assessment,
        agents=agents,
        current_tick=5,
        world_time="2026-03-02T08:00:00+00:00",
        run_id="run-1",
    )

    assert first is None
    assert second is not None
    assert second.scene_goal == DIRECTOR_SCENE_SOFT_CHECK_IN
    assert second.target_cast_ids == ["cast-spouse"]
