import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime import RuntimeInvocation
from app.cognition.claude.decision_provider import AgentDecisionProvider
from app.cognition.claude.decision_utils import RuntimeDecision
from app.cognition.heuristic.agent_backend import HeuristicAgentBackend
from app.sim.action_resolver import ActionIntent
from app.sim.context import get_run_world_time
from app.store.models import Agent
from app.store.repositories import EventRepository, LlmCallRepository, RunRepository
from tests.factories import make_agent, make_location, make_run, write_agent_config

from .helpers import build_scheduler_service, create_isolated_sqlite_engine
from .test_service import MixedOutcomeDecisionProvider


class TokenCapturingDecisionProvider(AgentDecisionProvider):
    def __init__(self, usage: dict | None = None, cost: float = 0.01) -> None:
        self.captured_ctx: list = []
        self.captured_invocations: list[RuntimeInvocation] = []
        self._usage = usage or {"input_tokens": 100, "output_tokens": 200}
        self._cost = cost

    async def decide(self, invocation: RuntimeInvocation, runtime_ctx=None):
        self.captured_ctx.append(runtime_ctx)
        self.captured_invocations.append(invocation)
        if runtime_ctx and runtime_ctx.on_llm_call:
            runtime_ctx.on_llm_call(
                agent_id=invocation.agent_id,
                task_type=invocation.task,
                usage=self._usage,
                total_cost_usd=self._cost,
                duration_ms=500,
            )
        return RuntimeDecision(action_type="rest")


class FixedTalkDecisionProvider(TokenCapturingDecisionProvider):
    def __init__(self, *, message: str, target_agent_id: str) -> None:
        super().__init__()
        self._message = message
        self._target_agent_id = target_agent_id

    async def decide(self, invocation: RuntimeInvocation, runtime_ctx=None):
        await super().decide(invocation, runtime_ctx=runtime_ctx)
        return RuntimeDecision(
            action_type="talk",
            target_agent_id=self._target_agent_id,
            message=self._message,
        )


@pytest.mark.asyncio
async def test_run_tick_isolated_with_separate_sessions(db_session, tmp_path):
    engine = await create_isolated_sqlite_engine()
    run_id = "run-isolated-1"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = make_run(run_id, name="isolated")
        home = make_location("loc-home-isolated", run_id=run_id, name="Home", location_type="home")
        alice = make_agent(
            "alice-isolated",
            run_id=run_id,
            location_id="loc-home-isolated",
            name="Alice",
        )
        session.add_all([run, home, alice])
        await session.commit()

    write_agent_config(tmp_path, "agent", name="Test", occupation="test")
    service = build_scheduler_service(tmp_path)

    result = await service.run_tick_isolated(
        run_id,
        engine,
        [ActionIntent(agent_id="alice-isolated", action_type="rest")],
    )

    assert result.tick_no == 1
    assert len(result.accepted) == 1
    assert result.accepted[0].action_type == "rest"

    async with AsyncSession(engine, expire_on_commit=False) as session:
        updated_run = await RunRepository(session).get(run_id)
        assert updated_run is not None
        assert updated_run.current_tick == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_run_tick_isolated_persists_movement_until_arrival_tick(tmp_path):
    engine = await create_isolated_sqlite_engine()
    run_id = "run-isolated-transit"
    alice_id = "alice-isolated-transit"
    bob_id = "bob-isolated-transit"
    home_id = "loc-home-isolated-transit"
    park_id = "loc-park-isolated-transit"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = make_run(run_id, name="isolated-transit")
        home = make_location(home_id, run_id=run_id, name="Home", location_type="home")
        home.capacity = 4
        park = make_location(park_id, run_id=run_id, name="Park", location_type="park")
        alice = make_agent(alice_id, run_id=run_id, location_id=home_id, name="Alice")
        bob = make_agent(bob_id, run_id=run_id, location_id=home_id, name="Bob")
        session.add_all([run, home, park, alice, bob])
        await session.commit()

    service = build_scheduler_service(tmp_path)
    started = await service.run_tick_isolated(
        run_id,
        engine,
        [ActionIntent(agent_id=alice_id, action_type="move", target_location_id=park_id)],
    )

    assert started.tick_no == 1
    async with AsyncSession(engine, expire_on_commit=False) as session:
        alice = await session.get(Agent, alice_id)
        assert alice is not None
        assert alice.current_location_id == home_id
        assert alice.movement["state"] == "in_transit"

    arrived = await service.run_tick_isolated(
        run_id,
        engine,
        [ActionIntent(agent_id=bob_id, action_type="rest")],
    )

    assert arrived.tick_no == 2
    assert [item.action_type for item in arrived.accepted] == ["rest", "move_arrived"]
    async with AsyncSession(engine, expire_on_commit=False) as session:
        alice = await session.get(Agent, alice_id)
        events = await EventRepository(session).list_for_run(run_id)
        assert alice is not None
        assert alice.current_location_id == park_id
        assert alice.movement == {}
        assert events[0].event_type == "move"
        assert {event.event_type for event in events[1:]} == {"rest", "move_arrived"}

    await engine.dispose()


@pytest.mark.asyncio
async def test_run_tick_isolated_skips_sleep_hours_and_persists_advanced_tick(db_session, tmp_path):
    engine = await create_isolated_sqlite_engine()
    run_id = "run-isolated-sleep-skip"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = make_run(
            run_id,
            name="isolated-sleep-skip",
            current_tick=203,
        )
        home = make_location(
            "loc-home-sleep-skip",
            run_id=run_id,
            name="Home",
            location_type="home",
        )
        alice = make_agent(
            "alice-sleep-skip",
            run_id=run_id,
            location_id="loc-home-sleep-skip",
            name="Alice",
        )
        session.add_all([run, home, alice])
        await session.commit()

    write_agent_config(tmp_path, "agent", name="Test", occupation="test")
    service = build_scheduler_service(tmp_path)

    result = await service.run_tick_isolated(
        run_id,
        engine,
        [ActionIntent(agent_id="alice-sleep-skip", action_type="rest")],
    )

    assert result.tick_delta == 85
    assert result.tick_no == 288
    assert result.world_time == "2026-03-03T06:00:00+00:00"

    async with AsyncSession(engine, expire_on_commit=False) as session:
        updated_run = await RunRepository(session).get(run_id)
        assert updated_run is not None
        assert updated_run.current_tick == 288
        assert get_run_world_time(updated_run).isoformat() == "2026-03-03T06:00:00+00:00"

    await engine.dispose()


@pytest.mark.asyncio
async def test_run_tick_isolated_persists_llm_calls(db_session, tmp_path):
    engine = await create_isolated_sqlite_engine()
    run_id = "run-llm-persist-1"
    agent_config_id = "alice-llm"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = make_run(run_id, name="llm-persist")
        loc = make_location("loc-llm-1", run_id=run_id, name="Home", location_type="home")
        agent = make_agent(
            "agent-llm-p1",
            run_id=run_id,
            name="Alice",
            profile={"agent_config_id": agent_config_id},
            location_id="loc-llm-1",
        )
        session.add_all([run, loc, agent])
        await session.commit()

    write_agent_config(tmp_path, agent_config_id, name="Alice", home="loc-llm-1")

    provider = TokenCapturingDecisionProvider(
        usage={"input_tokens": 111, "output_tokens": 222, "cache_read_input_tokens": 33},
        cost=0.015,
    )
    service = build_scheduler_service(tmp_path, HeuristicAgentBackend(provider))

    result = await service.run_tick_isolated(run_id, engine)

    assert result.tick_no == 1

    async with AsyncSession(engine, expire_on_commit=False) as session:
        totals = await LlmCallRepository(session).get_token_totals(run_id)
        assert totals["input_tokens"] == 111
        assert totals["output_tokens"] == 222
        assert totals["cache_read_tokens"] == 33

    await engine.dispose()


@pytest.mark.asyncio
async def test_run_tick_isolated_uses_planner_result_in_agent_context(tmp_path, monkeypatch):
    engine = await create_isolated_sqlite_engine()
    run_id = "run-isolated-planner-result"
    agent_id = "agent-isolated-planner-result"
    config_id = "alice-planner-result"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = make_run(run_id, name="isolated-planner-result", current_tick=1)
        home = make_location("loc-isolated-planner-result", run_id=run_id, name="Home")
        agent = make_agent(
            agent_id,
            run_id=run_id,
            location_id=home.id,
            name="Alice",
            profile={"agent_config_id": config_id},
            current_plan={"morning": "old plan"},
        )
        session.add_all([run, home, agent])
        await session.commit()

    write_agent_config(tmp_path, config_id, name="Alice", home="loc-isolated-planner-result")
    provider = TokenCapturingDecisionProvider()
    service = build_scheduler_service(tmp_path, HeuristicAgentBackend(provider))
    new_plan = {"morning": "read", "daytime": "work", "evening": "walk"}

    async def return_new_plan(**_kwargs):
        return {agent_id: new_plan}

    monkeypatch.setattr(service.day_boundary_coordinator, "run_planner_if_needed", return_new_plan)

    try:
        result = await service.run_tick_isolated(run_id, engine)
    finally:
        await engine.dispose()

    assert result.tick_no == 2
    assert provider.captured_invocations[0].context["world"]["daily_schedule"] == new_plan


@pytest.mark.asyncio
async def test_run_tick_isolated_advances_when_one_agent_falls_back(tmp_path):
    engine = await create_isolated_sqlite_engine()
    run_id = "run-isolated-fallback-1"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = make_run(
            run_id,
            name="isolated-fallback",
            scenario_type="narrative_world",
        )
        home = make_location("loc-home-fb", run_id=run_id, name="Home", location_type="home")
        office = make_location(
            "loc-office-fb",
            run_id=run_id,
            name="Office",
            location_type="office",
        )
        ok_agent = make_agent(
            "agent-fallback-ok-iso",
            run_id=run_id,
            name="Alice",
            personality={},
            profile={"agent_config_id": "agent-fallback-ok-iso", "world_role": "cast"},
            status={},
            current_plan={},
        )
        ok_agent.home_location_id = home.id
        ok_agent.current_location_id = office.id
        bad_agent = make_agent(
            "agent-fallback-bad-iso",
            run_id=run_id,
            name="Bob",
            profile={"agent_config_id": "agent-fallback-bad-iso", "world_role": "cast"},
        )
        bad_agent.home_location_id = home.id
        bad_agent.current_location_id = office.id
        session.add_all([run, home, office, ok_agent, bad_agent])
        await session.commit()

    try:
        for agent_id, name in (
            ("agent-fallback-ok-iso", "Alice"),
            ("agent-fallback-bad-iso", "Bob"),
        ):
            write_agent_config(tmp_path, agent_id, name=name, home="loc-home-fb")

        provider = MixedOutcomeDecisionProvider(
            failing_agent_ids={"agent-fallback-bad-iso"},
            success_action="work",
        )
        service = build_scheduler_service(tmp_path, HeuristicAgentBackend(provider))

        result = await service.run_tick_isolated(run_id, engine)

        assert result.tick_no == 1
        assert any(item.action_type == "talk" for item in result.accepted)
        assert len(result.rejected) == 1

        async with AsyncSession(engine, expire_on_commit=False) as session:
            updated_run = await RunRepository(session).get(run_id)
            events = await EventRepository(session).list_for_run(run_id)
            assert updated_run is not None
            assert updated_run.current_tick == 1
            event_types = {event.event_type for event in events}
            assert "speech" in event_types
            assert "conversation_started" in event_types
            assert any(event.event_type.endswith("_rejected") for event in events)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_run_tick_isolated_reuses_conversation_id_across_adjacent_ticks(tmp_path):
    engine = await create_isolated_sqlite_engine()
    run_id = "run-isolated-conversation-continuity"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = make_run(
            run_id,
            name="isolated-conversation-continuity",
        )
        cafe = make_location(
            "loc-cafe-iso-continuity",
            run_id=run_id,
            name="Cafe",
            location_type="cafe",
        )
        alice = make_agent(
            "alice-iso-continuity",
            run_id=run_id,
            location_id=cafe.id,
            name="Alice",
        )
        bob = make_agent(
            "bob-iso-continuity",
            run_id=run_id,
            location_id=cafe.id,
            name="Bob",
        )
        session.add_all([run, cafe, alice, bob])
        await session.commit()

    service = build_scheduler_service(tmp_path)

    try:
        await service.run_tick_isolated(
            run_id,
            engine,
            [
                ActionIntent(
                    agent_id="alice-iso-continuity",
                    action_type="talk",
                    target_agent_id="bob-iso-continuity",
                    payload={"message": "First tick"},
                )
            ],
        )
        await service.run_tick_isolated(
            run_id,
            engine,
            [
                ActionIntent(
                    agent_id="bob-iso-continuity",
                    action_type="talk",
                    target_agent_id="alice-iso-continuity",
                    payload={"message": "Second tick"},
                )
            ],
        )

        async with AsyncSession(engine, expire_on_commit=False) as session:
            timeline_events, _total = await EventRepository(session).list_timeline_events(
                run_id,
                order_desc=False,
            )
            conversation_started = [
                event for event in timeline_events if event.event_type == "conversation_started"
            ]
            speeches = [event for event in timeline_events if event.event_type == "speech"]

            assert len(conversation_started) == 1
            assert len(speeches) == 2
            conversation_id = conversation_started[0].payload["conversation_id"]
            assert speeches[0].payload["conversation_id"] == conversation_id
            assert speeches[1].payload["conversation_id"] == conversation_id
    finally:
        await engine.dispose()
