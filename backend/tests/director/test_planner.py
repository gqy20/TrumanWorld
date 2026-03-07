from app.director.observer import DirectorAssessment
from app.director.planner import DirectorPlanner
from app.store.models import Agent


def test_director_planner_builds_soft_check_in_plan_for_high_suspicion():
    planner = DirectorPlanner()
    agents = [
        Agent(
            id="cast-spouse",
            run_id="run-1",
            name="Meryl",
            occupation="spouse",
            profile={"world_role": "cast", "agent_config_id": "spouse"},
            personality={},
            status={},
            current_plan={},
        ),
        Agent(
            id="truman-1",
            run_id="run-1",
            name="Truman",
            occupation="resident",
            profile={"world_role": "truman"},
            personality={},
            status={"suspicion_score": 0.7},
            current_plan={},
        ),
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

    plan = planner.build_plan(assessment=assessment, agents=agents)

    assert plan is not None
    assert plan.scene_goal == "soft_check_in"
    assert plan.target_cast_ids == ["cast-spouse"]
    assert plan.priority == "advisory"
    assert plan.target_agent_id == "truman-1"
