from app.director.observer import DirectorAssessment
from app.director.strategy_engine import StrategyConditionEngine


def test_strategy_condition_engine_supports_generic_subject_alert_metric():
    engine = StrategyConditionEngine()
    assessment = DirectorAssessment(
        run_id="run-1",
        current_tick=3,
        subject_agent_id="subject-1",
        subject_alert_score=0.68,
        suspicion_level="alerted",
        continuity_risk="watch",
    )

    matched = engine.evaluate(
        {
            "type": "threshold",
            "metric": "subject_alert_score",
            "operator": "gte",
            "value": 0.6,
        },
        assessment,
    )

    assert matched is True


def test_strategy_condition_engine_skips_alert_metrics_when_tracking_disabled():
    engine = StrategyConditionEngine()
    assessment = DirectorAssessment(
        run_id="run-1",
        current_tick=3,
        subject_agent_id="subject-1",
        subject_alert_score=0.68,
        subject_alert_tracking_enabled=False,
        suspicion_level="alerted",
        continuity_risk="watch",
    )

    matched = engine.evaluate(
        {
            "type": "threshold",
            "metric": "subject_alert_score",
            "operator": "gte",
            "value": 0.6,
        },
        assessment,
    )

    assert matched is False


def test_strategy_condition_engine_supports_subject_isolation_metric():
    engine = StrategyConditionEngine()
    assessment = DirectorAssessment(
        run_id="run-1",
        current_tick=6,
        subject_agent_id="subject-1",
        subject_alert_score=0.2,
        suspicion_level="low",
        continuity_risk="stable",
        subject_isolation_ticks=5,
    )

    matched = engine.evaluate(
        {
            "type": "threshold",
            "metric": "subject_isolation_ticks",
            "operator": "gte",
            "value": 3,
        },
        assessment,
    )

    assert matched is True
