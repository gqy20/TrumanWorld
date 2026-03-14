from app.sim.action_resolver import ActionIntent, PlanUpdate
from app.sim.plan_updater import should_update_plan, update_agent_plan


def test_action_intent_supports_plan_update():
    intent = ActionIntent(
        agent_id="agent_1",
        action_type="talk",
        target_agent_id="bob",
        payload={"message": "Hi Bob!"},
        plan_update=PlanUpdate(
            reason="遇到重要的人",
            new_daytime="和 Bob 聊天",
        ),
    )

    assert intent.action_type == "talk"
    assert intent.plan_update is not None
    assert intent.plan_update.reason == "遇到重要的人"
    assert intent.plan_update.new_daytime == "和 Bob 聊天"


def test_should_update_plan_with_valid_reason_and_no_previous_update():
    intent = ActionIntent(
        agent_id="agent_1",
        action_type="talk",
        plan_update=PlanUpdate(
            reason="遇到重要的人",
            new_daytime="和 Bob 聊天",
        ),
    )

    assert should_update_plan(intent, last_update_tick=0, current_tick=100) is True


def test_should_update_plan_without_plan_update():
    intent = ActionIntent(
        agent_id="agent_1",
        action_type="work",
    )

    assert should_update_plan(intent) is False


def test_should_update_plan_with_invalid_reason():
    intent = ActionIntent(
        agent_id="agent_1",
        action_type="rest",
        plan_update=PlanUpdate(
            reason="random_reason",
            new_daytime="休息",
        ),
    )

    assert should_update_plan(intent) is False


def test_should_update_plan_with_cooldown_allow():
    intent = ActionIntent(
        agent_id="agent_1",
        action_type="talk",
        plan_update=PlanUpdate(
            reason="遇到重要的人",
            new_daytime="和 Bob 聊天",
        ),
    )

    assert (
        should_update_plan(
            intent,
            last_update_tick=50,
            current_tick=100,
            cooldown_ticks=12,
        )
        is True
    )


def test_should_update_plan_with_cooldown_deny():
    intent = ActionIntent(
        agent_id="agent_1",
        action_type="talk",
        plan_update=PlanUpdate(
            reason="遇到重要的人",
            new_daytime="和 Bob 聊天",
        ),
    )

    assert (
        should_update_plan(
            intent,
            last_update_tick=95,
            current_tick=100,
            cooldown_ticks=12,
        )
        is False
    )


def test_update_agent_plan_partial():
    current_plan = {
        "morning": "去咖啡店工作",
        "daytime": "在广场逛逛",
        "evening": "回家做饭",
    }

    new_plan = update_agent_plan(
        PlanUpdate(
            reason="遇到重要的人",
            new_daytime="和 Bob 聊天",
        ),
        current_plan,
    )

    assert new_plan["morning"] == "去咖啡店工作"
    assert new_plan["daytime"] == "和 Bob 聊天"
    assert new_plan["evening"] == "回家做饭"


def test_update_agent_plan_full():
    current_plan = {
        "morning": "去咖啡店工作",
        "daytime": "在广场逛逛",
        "evening": "回家做饭",
    }

    new_plan = update_agent_plan(
        PlanUpdate(
            reason="突发事件",
            new_morning="处理紧急事务",
            new_daytime="处理紧急事务",
            new_evening="休息",
        ),
        current_plan,
    )

    assert new_plan["morning"] == "处理紧急事务"
    assert new_plan["daytime"] == "处理紧急事务"
    assert new_plan["evening"] == "休息"


def test_update_agent_plan_no_change():
    current_plan = {
        "morning": "去咖啡店工作",
        "daytime": "在广场逛逛",
        "evening": "回家做饭",
    }

    new_plan = update_agent_plan(
        PlanUpdate(reason="测试"),
        current_plan,
    )

    assert new_plan == current_plan
