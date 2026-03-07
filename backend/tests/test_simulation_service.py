import asyncio

import pytest

from app.agent.providers import AgentDecisionProvider, RuntimeDecision
from app.agent.runtime import RuntimeInvocation
from app.sim.action_resolver import ActionIntent
from app.sim.service import SimulationService
from app.store.models import Agent, Location, SimulationRun
from app.store.repositories import AgentRepository, EventRepository, RunRepository


class FailingDecisionProvider(AgentDecisionProvider):
    async def decide(self, invocation: RuntimeInvocation):
        raise RuntimeError("provider unavailable")


class CancelledDecisionProvider(AgentDecisionProvider):
    async def decide(self, invocation: RuntimeInvocation):
        raise asyncio.CancelledError


class RecordingDecisionProvider(AgentDecisionProvider):
    def __init__(self) -> None:
        self.agent_ids: list[str] = []

    async def decide(self, invocation: RuntimeInvocation):
        self.agent_ids.append(invocation.agent_id)
        world = invocation.context.get("world", {})
        goal = world.get("current_goal")
        if isinstance(goal, str) and goal.startswith("move:"):
            return RuntimeDecision(
                action_type="move",
                target_location_id=goal.split(":", 1)[1].strip(),
            )
        return RuntimeDecision(action_type="rest")


@pytest.mark.asyncio
async def test_simulation_service_persists_tick_and_events(db_session):
    run = SimulationRun(id="run-service-1", name="service", status="running", current_tick=0, tick_minutes=5)
    home = Location(id="loc-home", run_id="run-service-1", name="Home", location_type="home", capacity=2)
    park = Location(id="loc-park", run_id="run-service-1", name="Park", location_type="park", capacity=2)
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
    assert len(memories) == 1
    assert memories[0].summary == "Moved to loc-park"
    assert memories[0].source_event_id == events[0].id


@pytest.mark.asyncio
async def test_simulation_service_persists_rejected_events(db_session):
    run = SimulationRun(id="run-service-2", name="service", status="running", current_tick=0, tick_minutes=5)
    home = Location(id="loc-home-2", run_id="run-service-2", name="Home", location_type="home", capacity=2)
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
        [ActionIntent(agent_id="alice-2", action_type="move", target_location_id="missing-location")],
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
    run = SimulationRun(id="run-service-3", name="service", status="running", current_tick=0, tick_minutes=5)
    home = Location(id="loc-home-3", run_id="run-service-3", name="Home", location_type="home", capacity=2)
    park = Location(id="loc-park-3", run_id="run-service-3", name="Park", location_type="park", capacity=2)
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
    run = SimulationRun(id="run-service-profile", name="service", status="running", current_tick=0, tick_minutes=5)
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
async def test_simulation_service_falls_back_when_runtime_provider_fails(db_session):
    run = SimulationRun(id="run-service-4", name="service", status="running", current_tick=0, tick_minutes=5)
    home = Location(id="loc-home-4", run_id="run-service-4", name="Home", location_type="home", capacity=2)
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
    run = SimulationRun(id="run-service-4b", name="service", status="running", current_tick=0, tick_minutes=5)
    home = Location(id="loc-home-4b", run_id="run-service-4b", name="Home", location_type="home", capacity=2)
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
async def test_simulation_service_updates_relationships_from_talk_events(db_session):
    run = SimulationRun(id="run-service-5", name="service", status="running", current_tick=0, tick_minutes=5)
    plaza = Location(id="loc-plaza-5", run_id="run-service-5", name="Plaza", location_type="plaza", capacity=4)
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

    alice_relationships = await AgentRepository(db_session).list_relationships("run-service-5", "alice-5")
    bob_relationships = await AgentRepository(db_session).list_relationships("run-service-5", "bob-5")
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
    assert alice_memories[0].summary == "Talked with bob-5"
    assert bob_memories[0].summary == "Talked with alice-5"
