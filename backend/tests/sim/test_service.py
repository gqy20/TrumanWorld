import asyncio

import pytest

from app.agent.providers import AgentDecisionProvider, RuntimeDecision
from app.agent.runtime import RuntimeInvocation
from app.scenario.base import Scenario
from app.scenario.truman_world.types import DirectorGuidance
from app.sim.action_resolver import ActionIntent
from app.sim.service import SimulationService
from app.store.models import Agent, Location, SimulationRun
from app.store.repositories import AgentRepository, EventRepository, RunRepository


class FailingDecisionProvider(AgentDecisionProvider):
    async def decide(self, invocation: RuntimeInvocation, runtime_ctx=None):
        raise RuntimeError("provider unavailable")


class CancelledDecisionProvider(AgentDecisionProvider):
    async def decide(self, invocation: RuntimeInvocation, runtime_ctx=None):
        raise asyncio.CancelledError


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

    def merge_agent_profile(self, agent: Agent, plan) -> dict:
        return dict(agent.profile or {})

    def fallback_intent(
        self,
        *,
        agent_id: str,
        current_location_id: str,
        home_location_id: str | None,
        nearby_agent_id: str | None,
        world_role: str | None = None,
        current_status: dict | None = None,
        truman_suspicion_score: float = 0.0,
        director_guidance: DirectorGuidance | None = None,
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
    assert result.world_time == "2026-03-02T07:05:00+00:00"
    assert len(memories) == 1
    assert memories[0].summary == "Moved to Park"
    assert memories[0].source_event_id == events[0].id


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

    service = SimulationService(db_session)
    result = await service.run_tick("run-service-3")

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
    runtime.decision_provider = recording_provider
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
async def test_simulation_service_uses_world_role_and_clock_in_runtime_context(
    db_session, tmp_path
):
    run = SimulationRun(
        id="run-service-role-clock",
        name="service",
        status="running",
        current_tick=2,
        tick_minutes=15,
        metadata_json={"world_start_time": "2026-03-02T07:00:00+00:00"},
    )
    home = Location(
        id="loc-home-role-clock",
        run_id="run-service-role-clock",
        name="Home",
        location_type="home",
        capacity=2,
    )
    park = Location(
        id="loc-park-role-clock",
        run_id="run-service-role-clock",
        name="Park",
        location_type="park",
        capacity=2,
    )
    agent_dir = tmp_path / "truman"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: truman",
                "name: Truman",
                "world_role: truman",
                "occupation: resident",
                "home: loc-home-role-clock",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Truman\nBase prompt", encoding="utf-8")

    truman = Agent(
        id="run-service-role-clock-truman",
        run_id="run-service-role-clock",
        name="Truman",
        occupation="resident",
        home_location_id="loc-home-role-clock",
        current_location_id="loc-home-role-clock",
        current_goal="move:loc-park-role-clock",
        personality={},
        profile={"agent_config_id": "truman", "world_role": "truman"},
        status={},
        current_plan={},
    )

    db_session.add_all([run, home, park, truman])
    await db_session.commit()

    recording_provider = RecordingDecisionProvider()
    runtime = SimulationService(db_session, agents_root=tmp_path).agent_runtime
    runtime.decision_provider = recording_provider
    service = SimulationService(db_session, agent_runtime=runtime, agents_root=tmp_path)

    result = await service.run_tick("run-service-role-clock")

    assert result.world_time == "2026-03-02T07:45:00+00:00"
    assert recording_provider.agent_ids == ["truman"]


@pytest.mark.asyncio
async def test_simulation_service_includes_director_system_events_for_cast_recent_events(
    db_session, tmp_path
):
    run = SimulationRun(
        id="run-service-director-events",
        name="service",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    square = Location(
        id="loc-square-director-events",
        run_id=run.id,
        name="Square",
        location_type="plaza",
        capacity=4,
    )
    cast = Agent(
        id="run-service-director-events-cast",
        run_id=run.id,
        name="Meryl",
        occupation="resident",
        home_location_id=square.id,
        current_location_id=square.id,
        current_goal="rest",
        personality={},
        profile={"agent_config_id": "spouse", "world_role": "cast"},
        status={},
        current_plan={},
    )
    truman = Agent(
        id="run-service-director-events-truman",
        run_id=run.id,
        name="Truman",
        occupation="resident",
        home_location_id=square.id,
        current_location_id=square.id,
        current_goal="rest",
        personality={},
        profile={"agent_config_id": "truman", "world_role": "truman"},
        status={},
        current_plan={},
    )

    db_session.add_all([run, square, cast, truman])
    await db_session.commit()

    service = SimulationService(db_session)
    await service.inject_director_event(
        run_id=run.id,
        event_type="broadcast",
        payload={"message": "Town hall at plaza"},
        importance=0.8,
    )

    spouse_dir = tmp_path / "spouse"
    spouse_dir.mkdir(parents=True)
    (spouse_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: spouse",
                "name: Meryl",
                "occupation: resident",
                "home: loc-square-director-events",
            ]
        ),
        encoding="utf-8",
    )
    (spouse_dir / "prompt.md").write_text("# Meryl\nBase prompt", encoding="utf-8")

    truman_dir = tmp_path / "truman"
    truman_dir.mkdir(parents=True)
    (truman_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: truman",
                "name: Truman",
                "occupation: resident",
                "home: loc-square-director-events",
            ]
        ),
        encoding="utf-8",
    )
    (truman_dir / "prompt.md").write_text("# Truman\nBase prompt", encoding="utf-8")

    capturing_provider = ContextCapturingDecisionProvider()
    runtime = SimulationService(db_session, agents_root=tmp_path).agent_runtime
    runtime.decision_provider = capturing_provider
    service = SimulationService(db_session, agent_runtime=runtime, agents_root=tmp_path)

    await service.run_tick(run.id)

    spouse_recent_events = capturing_provider.recent_events_by_agent["spouse"]
    truman_recent_events = capturing_provider.recent_events_by_agent["truman"]

    assert any(event["event_type"] == "director_broadcast" for event in spouse_recent_events)
    assert all(event["event_type"] != "director_broadcast" for event in truman_recent_events)


@pytest.mark.asyncio
async def test_seed_demo_run_creates_truman_world_agents(db_session):
    run = SimulationRun(id="run-demo-seed", name="demo-seed", status="running")
    db_session.add(run)
    await db_session.commit()

    service = SimulationService(db_session)
    await service.seed_demo_run("run-demo-seed")

    agents = await AgentRepository(db_session).list_for_run("run-demo-seed")

    assert [agent.name for agent in agents] == ["Alice", "Lauren", "Marlon", "Meryl", "Truman"]
    profile_by_name = {agent.name: agent.profile for agent in agents}
    assert profile_by_name["Truman"]["world_role"] == "truman"
    assert profile_by_name["Meryl"]["world_role"] == "cast"
    assert profile_by_name["Alice"]["world_role"] == "cast"


@pytest.mark.asyncio
async def test_simulation_service_updates_truman_suspicion_from_rejected_events(db_session):
    run = SimulationRun(
        id="run-truman-suspicion",
        name="suspicion",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    home = Location(
        id="loc-home-suspicion",
        run_id="run-truman-suspicion",
        name="Home",
        location_type="home",
        capacity=2,
    )
    truman = Agent(
        id="truman-suspicion",
        run_id="run-truman-suspicion",
        name="Truman",
        occupation="resident",
        home_location_id="loc-home-suspicion",
        current_location_id="loc-home-suspicion",
        personality={},
        profile={"world_role": "truman", "agent_config_id": "truman"},
        status={"suspicion_score": 0.1},
        current_plan={},
    )

    db_session.add_all([run, home, truman])
    await db_session.commit()

    service = SimulationService(db_session)
    await service.run_tick(
        "run-truman-suspicion",
        [
            ActionIntent(
                agent_id="truman-suspicion",
                action_type="move",
                target_location_id="missing-location",
            )
        ],
    )

    await db_session.refresh(truman)
    updated = await AgentRepository(db_session).get("truman-suspicion")

    assert updated is not None
    assert updated.status["suspicion_score"] > 0.1


@pytest.mark.asyncio
async def test_simulation_service_accepts_injected_scenario(db_session):
    run = SimulationRun(
        id="run-fake-scenario",
        name="fake-scenario",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    home = Location(
        id="loc-home-fake",
        run_id="run-fake-scenario",
        name="Home",
        location_type="home",
        capacity=2,
    )
    agent = Agent(
        id="agent-fake",
        run_id="run-fake-scenario",
        name="Agent",
        occupation="resident",
        home_location_id="loc-home-fake",
        current_location_id="loc-home-fake",
        current_goal="rest",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, home, agent])
    await db_session.commit()

    scenario = FakeScenario()
    service = SimulationService(db_session, scenario=scenario)
    result = await service.run_tick("run-fake-scenario")

    assert scenario.runtime_configured is True
    assert scenario.state_update_calls == [("run-fake-scenario", 1)]
    assert result.tick_no == 1


@pytest.mark.asyncio
async def test_simulation_service_falls_back_when_runtime_provider_fails(db_session):
    run = SimulationRun(
        id="run-service-4", name="service", status="running", current_tick=0, tick_minutes=5
    )
    home = Location(
        id="loc-home-4", run_id="run-service-4", name="Home", location_type="home", capacity=2
    )
    alice = Agent(
        id="demo_agent",
        run_id="run-service-4",
        name="Demo Agent",
        occupation="resident",
        home_location_id="loc-home-4",
        current_location_id="loc-home-4",
        current_goal="work",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, home, alice])
    await db_session.commit()

    failing_runtime = SimulationService(db_session).agent_runtime
    failing_runtime.decision_provider = FailingDecisionProvider()
    service = SimulationService(db_session, agent_runtime=failing_runtime)

    result = await service.run_tick("run-service-4")

    assert result.tick_no == 1
    assert len(result.accepted) == 1
    assert result.accepted[0].action_type == "work"


@pytest.mark.asyncio
async def test_simulation_service_falls_back_when_runtime_provider_is_cancelled(db_session):
    run = SimulationRun(
        id="run-service-4b", name="service", status="running", current_tick=0, tick_minutes=5
    )
    home = Location(
        id="loc-home-4b", run_id="run-service-4b", name="Home", location_type="home", capacity=2
    )
    alice = Agent(
        id="demo_agent",
        run_id="run-service-4b",
        name="Demo Agent",
        occupation="resident",
        home_location_id="loc-home-4b",
        current_location_id="loc-home-4b",
        current_goal="work",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, home, alice])
    await db_session.commit()

    cancelled_runtime = SimulationService(db_session).agent_runtime
    cancelled_runtime.decision_provider = CancelledDecisionProvider()
    service = SimulationService(db_session, agent_runtime=cancelled_runtime)

    result = await service.run_tick("run-service-4b")

    assert result.tick_no == 1
    assert len(result.accepted) == 1
    assert result.accepted[0].action_type == "work"


@pytest.mark.asyncio
async def test_simulation_service_fallback_talk_includes_message(db_session):
    run = SimulationRun(
        id="run-service-4c", name="service", status="running", current_tick=0, tick_minutes=5
    )
    cafe = Location(
        id="loc-cafe-4c", run_id="run-service-4c", name="Cafe", location_type="cafe", capacity=4
    )
    alice = Agent(
        id="alice-4c",
        run_id="run-service-4c",
        name="Alice",
        occupation="resident",
        home_location_id="loc-cafe-4c",
        current_location_id="loc-cafe-4c",
        current_goal="talk",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    bob = Agent(
        id="bob-4c",
        run_id="run-service-4c",
        name="Bob",
        occupation="resident",
        home_location_id="loc-cafe-4c",
        current_location_id="loc-cafe-4c",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, cafe, alice, bob])
    await db_session.commit()

    failing_runtime = SimulationService(db_session).agent_runtime
    failing_runtime.decision_provider = FailingDecisionProvider()
    service = SimulationService(db_session, agent_runtime=failing_runtime)

    result = await service.run_tick("run-service-4c")

    assert result.tick_no == 1
    assert len(result.accepted) == 2
    alice_talk = next(item for item in result.accepted if item.action_type == "talk")
    assert alice_talk.event_payload["target_agent_id"] == "bob-4c"
    assert alice_talk.event_payload["message"]


@pytest.mark.asyncio
async def test_simulation_service_updates_relationships_from_talk_events(db_session):
    run = SimulationRun(
        id="run-service-5", name="service", status="running", current_tick=0, tick_minutes=5
    )
    plaza = Location(
        id="loc-plaza-5", run_id="run-service-5", name="Plaza", location_type="plaza", capacity=4
    )
    alice = Agent(
        id="alice-5",
        run_id="run-service-5",
        name="Alice",
        occupation="resident",
        home_location_id="loc-plaza-5",
        current_location_id="loc-plaza-5",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    bob = Agent(
        id="bob-5",
        run_id="run-service-5",
        name="Bob",
        occupation="resident",
        home_location_id="loc-plaza-5",
        current_location_id="loc-plaza-5",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, plaza, alice, bob])
    await db_session.commit()

    service = SimulationService(db_session)
    result = await service.run_tick(
        "run-service-5",
        [ActionIntent(agent_id="alice-5", action_type="talk", target_agent_id="bob-5")],
    )

    alice_relationships = await AgentRepository(db_session).list_relationships(
        "run-service-5", "alice-5"
    )
    bob_relationships = await AgentRepository(db_session).list_relationships(
        "run-service-5", "bob-5"
    )
    alice_memories = await AgentRepository(db_session).list_recent_memories("alice-5")
    bob_memories = await AgentRepository(db_session).list_recent_memories("bob-5")

    assert result.tick_no == 1
    assert len(result.accepted) == 1
    assert result.accepted[0].action_type == "talk"
    assert len(alice_relationships) == 1
    assert len(bob_relationships) == 1
    assert alice_relationships[0].other_agent_id == "bob-5"
    assert bob_relationships[0].other_agent_id == "alice-5"
    assert alice_relationships[0].familiarity == 0.1
    assert bob_relationships[0].trust == 0.05
    assert alice_memories[0].summary.startswith("Talked with Bob")
    assert bob_memories[0].summary.startswith("Talked with Alice") or bob_memories[
        0
    ].summary.startswith("Alice said")


@pytest.mark.asyncio
async def test_run_tick_isolated_with_separate_sessions(db_session):
    """Test that run_tick_isolated properly handles session isolation.

    This test verifies that the method correctly handles the case where
    database operations need to be performed after agent runtime calls,
    which is where greenlet conflicts can occur with anyio-based SDKs.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from app.agent.providers import HeuristicDecisionProvider
    from app.agent.runtime import AgentRuntime
    from app.agent.registry import AgentRegistry
    from pathlib import Path
    import tempfile

    # Create a separate engine for isolated operations
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create tables
    from app.store.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Set up test data with the isolated engine
    run_id = "run-isolated-1"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id=run_id, name="isolated", status="running", current_tick=0, tick_minutes=5
        )
        home = Location(
            id="loc-home-isolated", run_id=run_id, name="Home", location_type="home", capacity=2
        )
        alice = Agent(
            id="alice-isolated",
            run_id=run_id,
            name="Alice",
            occupation="resident",
            home_location_id="loc-home-isolated",
            current_location_id="loc-home-isolated",
            personality={},
            profile={},
            status={},
            current_plan={},
        )
        session.add_all([run, home, alice])
        await session.commit()

    # Create service with heuristic provider (no SDK calls)
    tmp_path = Path(tempfile.mkdtemp())
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "agent.yml").write_text("id: test\nname: Test\noccupation: test\nhome: home\n")
    (agent_dir / "prompt.md").write_text("# Test")

    registry = AgentRegistry(tmp_path)
    runtime = AgentRuntime(registry=registry, decision_provider=HeuristicDecisionProvider())
    service = SimulationService.create_for_scheduler(runtime)

    # Run the isolated tick
    result = await service.run_tick_isolated(
        run_id,
        engine,
        [ActionIntent(agent_id="alice-isolated", action_type="rest")],
    )

    # Verify the results
    assert result.tick_no == 1
    assert len(result.accepted) == 1
    assert result.accepted[0].action_type == "rest"

    # Verify database state
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run_repo = RunRepository(session)
        updated_run = await run_repo.get(run_id)
        assert updated_run is not None
        assert updated_run.current_tick == 1

    await engine.dispose()

    # Cleanup
    import shutil

    shutil.rmtree(tmp_path)
