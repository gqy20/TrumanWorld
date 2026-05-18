import pytest
from sqlalchemy import select

from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime, RuntimeInvocation
from app.cognition.claude.decision_provider import AgentDecisionProvider
from app.cognition.claude.decision_utils import RuntimeDecision
from app.cognition.heuristic.agent_backend import HeuristicAgentBackend
from app.cognition.langgraph.agent_backend import LangGraphAgentBackend
from app.infra.settings import get_settings
from app.scenario.base import Scenario
from app.scenario.types import ScenarioGuidance
from app.sim.action_resolver import ActionIntent
from app.sim.service import SimulationService
from app.store.models import Agent, Event, Location, Memory, SimulationRun
from app.store.repositories import (
    AgentRepository,
    EventRepository,
    RelationshipRepository,
    RunRepository,
)


class FakeLangGraphStructuredModel:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts: list[str] = []

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, prompt: str):
        self.prompts.append(prompt)
        return dict(self.response)


class RecordingDecisionProvider(AgentDecisionProvider):
    def __init__(self) -> None:
        self.agent_ids: list[str] = []

    async def decide(self, invocation: RuntimeInvocation, runtime_ctx=None):
        self.agent_ids.append(invocation.agent_id)
        world = invocation.context.get("world", {})
        goal = world.get("current_goal")
        if isinstance(goal, str) and goal.startswith("move:"):
            return RuntimeDecision(
                action_type="move",
                target_location_id=goal.split(":", 1)[1].strip(),
            )
        return RuntimeDecision(action_type="rest")


class ContextCapturingDecisionProvider(AgentDecisionProvider):
    def __init__(self) -> None:
        self.recent_events_by_agent: dict[str, list[dict]] = {}

    async def decide(self, invocation: RuntimeInvocation, runtime_ctx=None):
        self.recent_events_by_agent[invocation.agent_id] = list(
            invocation.context.get("recent_events", [])
        )
        return RuntimeDecision(action_type="rest")


class MixedOutcomeDecisionProvider(AgentDecisionProvider):
    def __init__(self, *, failing_agent_ids: set[str], success_action: str = "work") -> None:
        self.failing_agent_ids = set(failing_agent_ids)
        self.success_action = success_action
        self.calls: list[str] = []

    async def decide(self, invocation: RuntimeInvocation, runtime_ctx=None):
        self.calls.append(invocation.agent_id)
        if invocation.agent_id in self.failing_agent_ids:
            raise RuntimeError(f"forced failure for {invocation.agent_id}")
        return RuntimeDecision(action_type=self.success_action)


class FakeScenario(Scenario):
    def __init__(self) -> None:
        self.runtime_configured = False
        self.seed_called = False
        self.state_update_calls: list[tuple[str, int]] = []

    def with_session(self, session):
        return self

    def configure_runtime(self, agent_runtime) -> None:
        self.runtime_configured = True

    def configure_agent_context(self, context_builder) -> None:
        return None

    async def observe_run(self, run_id: str, event_limit: int = 20):
        raise RuntimeError("not used")

    def assess(self, *, run_id: str, current_tick: int, agents: list[Agent], events: list):
        raise RuntimeError("not used")

    async def build_director_plan(self, run_id: str, agents: list[Agent]):
        return None

    async def persist_director_plan(self, run_id: str, plan) -> None:
        return None

    def merge_agent_profile(self, agent: Agent, plan) -> dict:
        return dict(agent.profile or {})

    def allowed_actions(self) -> list[str]:
        return ["move", "talk", "work", "rest"]

    def fallback_intent(
        self,
        *,
        agent_id: str,
        current_location_id: str,
        home_location_id: str | None,
        nearby_agent_id: str | None,
        world_role: str | None = None,
        current_status: dict | None = None,
        scenario_state: dict | None = None,
        scenario_guidance: ScenarioGuidance | None = None,
    ):
        return None

    async def seed_demo_run(self, run: SimulationRun) -> None:
        self.seed_called = True

    async def update_state_from_events(self, run_id: str, events: list) -> None:
        self.state_update_calls.append((run_id, len(events)))


@pytest.mark.asyncio
async def test_simulation_service_persists_tick_and_events(db_session):
    run = SimulationRun(
        id="run-service-1", name="service", status="running", current_tick=0, tick_minutes=5
    )
    home = Location(
        id="loc-home", run_id="run-service-1", name="Home", location_type="home", capacity=2
    )
    park = Location(
        id="loc-park", run_id="run-service-1", name="Park", location_type="park", capacity=2
    )
    alice = Agent(
        id="alice",
        run_id="run-service-1",
        name="Alice",
        occupation="resident",
        home_location_id="loc-home",
        current_location_id="loc-home",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, home, park, alice])
    await db_session.commit()

    service = SimulationService(db_session)
    result = await service.run_tick(
        "run-service-1",
        [ActionIntent(agent_id="alice", action_type="move", target_location_id="loc-park")],
    )

    run_repo = RunRepository(db_session)
    event_repo = EventRepository(db_session)
    updated_run = await run_repo.get("run-service-1")
    events = await event_repo.list_for_run("run-service-1")
    memories = await AgentRepository(db_session).list_recent_memories("alice")

    assert result.tick_no == 1
    assert updated_run is not None
    assert updated_run.current_tick == 1
    assert len(events) == 1
    assert events[0].event_type == "move"
    assert events[0].actor_agent_id == "alice"
    assert events[0].payload["to_location_id"] == "loc-park"
    assert result.world_time == "2026-03-02T06:05:00+00:00"
    assert len(memories) == 1
    assert memories[0].summary == "Moved to Park"
    assert memories[0].source_event_id == events[0].id


@pytest.mark.asyncio
async def test_simulation_service_rolls_back_tick_writes_when_event_persistence_fails(
    db_session,
):
    run = SimulationRun(
        id="run-service-write-rollback",
        name="service-write-rollback",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    home = Location(
        id="loc-home-write-rollback",
        run_id=run.id,
        name="Home",
        location_type="home",
        capacity=2,
    )
    park = Location(
        id="loc-park-write-rollback",
        run_id=run.id,
        name="Park",
        location_type="park",
        capacity=2,
    )
    alice = Agent(
        id="alice-write-rollback",
        run_id=run.id,
        name="Alice",
        occupation="resident",
        home_location_id=home.id,
        current_location_id=home.id,
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, home, park, alice])
    await db_session.commit()
    run_id = run.id
    home_id = home.id
    park_id = park.id
    alice_id = alice.id

    service = SimulationService(db_session)

    async def fail_tick_events(*_args, **_kwargs):
        raise RuntimeError("event persistence failed")

    service._persist_tick_events = fail_tick_events

    with pytest.raises(RuntimeError, match="event persistence failed"):
        await service.run_tick(
            run_id,
            [
                ActionIntent(
                    agent_id=alice_id,
                    action_type="move",
                    target_location_id=park_id,
                )
            ],
        )

    await db_session.rollback()
    updated_run = await db_session.get(SimulationRun, run_id)
    updated_alice = await db_session.get(Agent, alice_id)
    events = (await db_session.execute(select(Event).where(Event.run_id == run_id))).scalars().all()

    assert updated_run is not None
    assert updated_run.current_tick == 0
    assert updated_alice is not None
    assert updated_alice.current_location_id == home_id
    assert events == []


@pytest.mark.asyncio
async def test_simulation_service_aggregates_consecutive_work_memories_into_streak(db_session):
    run = SimulationRun(
        id="run-service-work-dedup",
        name="service",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    office = Location(
        id="loc-office-dedup",
        run_id="run-service-work-dedup",
        name="Office",
        location_type="office",
        capacity=2,
    )
    alice = Agent(
        id="alice-work-dedup",
        run_id="run-service-work-dedup",
        name="Alice",
        occupation="resident",
        home_location_id=office.id,
        current_location_id=office.id,
        personality={},
        profile={"workplace_location_id": office.id},
        status={},
        current_plan={},
    )

    db_session.add_all([run, office, alice])
    await db_session.commit()

    service = SimulationService(db_session)
    for _ in range(3):
        await service.run_tick(
            "run-service-work-dedup",
            [ActionIntent(agent_id="alice-work-dedup", action_type="work")],
        )

    memories = await AgentRepository(db_session).list_recent_memories("alice-work-dedup", limit=10)
    worked_memories = [memory for memory in memories if memory.summary == "Worked"]

    assert len(worked_memories) == 1
    assert worked_memories[0].streak_count == 3
    assert worked_memories[0].last_tick_no == 3
    assert worked_memories[0].tick_no == 3
    assert worked_memories[0].content == "Worked during 3 consecutive ticks."


@pytest.mark.asyncio
async def test_simulation_service_group_conversation_does_not_create_spurious_rejection(
    db_session,
):
    run = SimulationRun(
        id="run-service-group-conversation",
        name="service",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    plaza = Location(
        id="loc-plaza-group",
        run_id=run.id,
        name="Plaza",
        location_type="plaza",
        capacity=4,
    )
    alice = Agent(
        id="alice-group",
        run_id=run.id,
        name="Alice",
        occupation="resident",
        home_location_id=plaza.id,
        current_location_id=plaza.id,
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    bob = Agent(
        id="bob-group",
        run_id=run.id,
        name="Bob",
        occupation="resident",
        home_location_id=plaza.id,
        current_location_id=plaza.id,
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    carol = Agent(
        id="carol-group",
        run_id=run.id,
        name="Carol",
        occupation="resident",
        home_location_id=plaza.id,
        current_location_id=plaza.id,
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, plaza, alice, bob, carol])
    await db_session.commit()

    service = SimulationService(db_session)
    result = await service.run_tick(
        run.id,
        [
            ActionIntent(
                agent_id=alice.id,
                action_type="talk",
                target_agent_id=bob.id,
                payload={"message": "Hey Bob!"},
            ),
            ActionIntent(
                agent_id=carol.id,
                action_type="talk",
                target_agent_id=bob.id,
                payload={"message": "Mind if I join?"},
            ),
        ],
    )

    events = await EventRepository(db_session).list_for_run(run.id, limit=10)
    memories_result = await db_session.execute(
        select(Memory)
        .where(Memory.run_id == run.id)
        .order_by(Memory.agent_id.asc(), Memory.id.asc())
    )
    memories = memories_result.scalars().all()
    alice_to_carol = await RelationshipRepository(db_session).get_pair(run.id, alice.id, carol.id)
    carol_to_alice = await RelationshipRepository(db_session).get_pair(run.id, carol.id, alice.id)

    assert len(result.rejected) == 0
    assert not any(event.event_type == "talk_rejected" for event in events)
    assert any(
        memory.agent_id == bob.id and "Alice said at Plaza" in memory.content for memory in memories
    )
    assert any(
        memory.agent_id == carol.id and "Alice said at Plaza" in memory.content
        for memory in memories
    )
    assert alice_to_carol is not None
    assert carol_to_alice is not None
    assert alice_to_carol.familiarity > 0
    assert carol_to_alice.familiarity > 0


@pytest.mark.asyncio
async def test_simulation_service_persists_rejected_events(db_session):
    run = SimulationRun(
        id="run-service-2", name="service", status="running", current_tick=0, tick_minutes=5
    )
    home = Location(
        id="loc-home-2", run_id="run-service-2", name="Home", location_type="home", capacity=2
    )
    alice = Agent(
        id="alice-2",
        run_id="run-service-2",
        name="Alice",
        occupation="resident",
        home_location_id="loc-home-2",
        current_location_id="loc-home-2",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, home, alice])
    await db_session.commit()

    service = SimulationService(db_session)
    result = await service.run_tick(
        "run-service-2",
        [
            ActionIntent(
                agent_id="alice-2", action_type="move", target_location_id="missing-location"
            )
        ],
    )

    event_repo = EventRepository(db_session)
    events = await event_repo.list_for_run("run-service-2")

    assert result.tick_no == 1
    assert len(result.rejected) == 1
    assert len(events) == 1
    assert events[0].event_type == "move_rejected"
    assert events[0].payload["reason"] == "location_not_found"


@pytest.mark.asyncio
async def test_simulation_service_can_prepare_intents_from_agent_runtime(db_session):
    run = SimulationRun(
        id="run-service-3", name="service", status="running", current_tick=0, tick_minutes=5
    )
    home = Location(
        id="loc-home-3", run_id="run-service-3", name="Home", location_type="home", capacity=2
    )
    park = Location(
        id="loc-park-3", run_id="run-service-3", name="Park", location_type="park", capacity=2
    )
    alice = Agent(
        id="demo_agent",
        run_id="run-service-3",
        name="Demo Agent",
        occupation="resident",
        home_location_id="loc-home-3",
        current_location_id="loc-home-3",
        current_goal="move:loc-park-3",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, home, park, alice])
    await db_session.commit()

    # 直接注入 intent，不走 LLM 决策路径
    service = SimulationService(db_session)
    result = await service.run_tick(
        "run-service-3",
        [ActionIntent(agent_id="demo_agent", action_type="move", target_location_id="loc-park-3")],
    )

    event_repo = EventRepository(db_session)
    events = await event_repo.list_for_run("run-service-3")

    assert result.tick_no == 1
    assert len(result.accepted) == 1
    assert result.accepted[0].action_type == "move"
    assert len(events) == 1
    assert events[0].event_type == "move"


@pytest.mark.asyncio
async def test_simulation_service_resolves_runtime_agent_id_from_profile(db_session, tmp_path):
    run = SimulationRun(
        id="run-service-profile", name="service", status="running", current_tick=0, tick_minutes=5
    )
    home = Location(
        id="loc-home-profile",
        run_id="run-service-profile",
        name="Home",
        location_type="home",
        capacity=2,
    )
    park = Location(
        id="loc-park-profile",
        run_id="run-service-profile",
        name="Park",
        location_type="park",
        capacity=2,
    )
    agent_dir = tmp_path / "alice"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: alice",
                "name: Alice",
                "occupation: resident",
                "home: loc-home-profile",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")

    alice = Agent(
        id="run-service-profile-alice",
        run_id="run-service-profile",
        name="Alice",
        occupation="resident",
        home_location_id="loc-home-profile",
        current_location_id="loc-home-profile",
        current_goal="move:loc-park-profile",
        personality={},
        profile={"agent_config_id": "alice"},
        status={},
        current_plan={},
    )

    db_session.add_all([run, home, park, alice])
    await db_session.commit()

    recording_provider = RecordingDecisionProvider()
    runtime = SimulationService(db_session, agents_root=tmp_path).agent_runtime
    runtime.backend = HeuristicAgentBackend(recording_provider)
    service = SimulationService(db_session, agent_runtime=runtime, agents_root=tmp_path)
    result = await service.run_tick("run-service-profile")

    event_repo = EventRepository(db_session)
    events = await event_repo.list_for_run("run-service-profile")

    assert result.tick_no == 1
    assert len(result.accepted) == 1
    assert result.accepted[0].action_type == "move"
    assert len(events) == 1
    assert events[0].event_type == "move"
    assert recording_provider.agent_ids == ["alice"]


@pytest.mark.asyncio
async def test_simulation_service_runs_tick_with_langgraph_backend(
    db_session, tmp_path, monkeypatch
):
    monkeypatch.setenv("TRUMANWORLD_AGENT_BACKEND", "langgraph")
    monkeypatch.setenv("TRUMANWORLD_LLM_MODEL", "langgraph-smoke-model")
    monkeypatch.setenv("TRUMANWORLD_ANTHROPIC_API_KEY", "langgraph-smoke-key")
    monkeypatch.setenv("TRUMANWORLD_LANGGRAPH_REACTOR_STRUCTURED_ENABLED", "true")
    get_settings.cache_clear()
    try:
        run = SimulationRun(
            id="run-service-langgraph",
            name="service",
            status="running",
            current_tick=1,
            tick_minutes=5,
        )
        home = Location(
            id="loc-home-langgraph",
            run_id="run-service-langgraph",
            name="Home",
            location_type="home",
            capacity=2,
        )
        square = Location(
            id="loc-square-langgraph",
            run_id="run-service-langgraph",
            name="Square",
            location_type="square",
            capacity=2,
        )
        agent_dir = tmp_path / "alice_langgraph"
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.yml").write_text(
            "\n".join(
                [
                    "id: alice_langgraph",
                    "name: Alice",
                    "occupation: resident",
                    "home: loc-home-langgraph",
                ]
            ),
            encoding="utf-8",
        )
        (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")

        alice = Agent(
            id="run-service-langgraph-alice",
            run_id="run-service-langgraph",
            name="Alice",
            occupation="resident",
            home_location_id="loc-home-langgraph",
            current_location_id="loc-home-langgraph",
            current_goal="move:loc-square-langgraph",
            personality={},
            profile={"agent_config_id": "alice_langgraph"},
            status={},
            current_plan={},
        )

        db_session.add_all([run, home, square, alice])
        await db_session.commit()

        runtime = AgentRuntime(registry=AgentRegistry(tmp_path))
        assert isinstance(runtime.backend, LangGraphAgentBackend)
        runtime.backend._decision_model = FakeLangGraphStructuredModel(
            {
                "action_type": "move",
                "target_location_id": "loc-square-langgraph",
                "payload": {"source": "langgraph-smoke"},
            }
        )

        service = SimulationService(db_session, agent_runtime=runtime, agents_root=tmp_path)
        result = await service.run_tick("run-service-langgraph")

        event_repo = EventRepository(db_session)
        events = await event_repo.list_for_run("run-service-langgraph")
        agent_repo = AgentRepository(db_session)
        updated_agent = await agent_repo.get("run-service-langgraph-alice")

        assert result.tick_no == 2
        assert len(result.accepted) == 1
        assert result.accepted[0].action_type == "move"
        assert len(events) == 1
        assert events[0].event_type == "move"
        assert updated_agent is not None
        assert updated_agent.current_location_id == "loc-square-langgraph"
    finally:
        get_settings.cache_clear()
