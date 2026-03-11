import pytest

from app.agent.providers import AgentDecisionProvider, RuntimeDecision
from app.agent.runtime import RuntimeInvocation
from app.scenario.base import Scenario
from app.director.service import DirectorEventService
from app.scenario.truman_world.coordinator import TrumanWorldCoordinator
from app.scenario.types import ScenarioGuidance
from app.sim.action_resolver import ActionIntent
from app.sim.service import SimulationService
from app.sim.tick_orchestrator import TickOrchestrator
from app.store.models import Agent, Location, SimulationRun
from app.store.repositories import (
    AgentRepository,
    DirectorMemoryRepository,
    EventRepository,
    LlmCallRepository,
    RunRepository,
)


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
async def test_simulation_service_aggregates_consecutive_work_memories_into_streak(db_session):
    run = SimulationRun(
        id="run-service-work-dedup", name="service", status="running", current_tick=0, tick_minutes=5
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
    assert worked_memories[0].memory_category == "medium_term"


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

    await DirectorEventService(db_session).inject_event(
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
async def test_manual_director_intervention_is_not_consumed_in_read_phase(db_session):
    run = SimulationRun(
        id="run-service-manual-once",
        name="service",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    square = Location(
        id="loc-square-manual-once",
        run_id=run.id,
        name="Square",
        location_type="plaza",
        capacity=4,
    )
    cast = Agent(
        id="run-service-manual-once-cast",
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
        id="run-service-manual-once-truman",
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

    await DirectorEventService(db_session).inject_event(
        run_id=run.id,
        event_type="broadcast",
        payload={"message": "Town hall at plaza"},
        location_id=square.id,
        importance=0.8,
    )

    agents = list(await AgentRepository(db_session).list_for_run(run.id))
    coordinator = TrumanWorldCoordinator(db_session)

    first_plan = await coordinator.build_director_plan(run.id, agents)
    pending = await DirectorMemoryRepository(db_session).get_pending_manual_interventions(
        run_id=run.id,
        current_tick=run.current_tick,
        max_age_ticks=5,
    )

    assert first_plan is not None
    assert first_plan.scene_goal == "gather"
    assert first_plan.location_hint == square.id
    assert len(pending) == 1
    assert pending[0].was_executed is False


@pytest.mark.asyncio
async def test_seed_demo_run_creates_truman_world_agents(db_session):
    run = SimulationRun(id="run-demo-seed", name="demo-seed", status="running")
    db_session.add(run)
    await db_session.commit()

    service = SimulationService(db_session)
    await service.seed_demo_run("run-demo-seed")

    agents = await AgentRepository(db_session).list_for_run("run-demo-seed")

    assert [agent.name for agent in agents] == [
        "Alice",
        "Bob",
        "Lauren",
        "Marlon",
        "Meryl",
        "Truman",
    ]
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
    result = await service.run_tick(
        "run-fake-scenario",
        [ActionIntent(agent_id="agent-fake", action_type="rest")],
    )

    assert scenario.runtime_configured is True
    assert scenario.state_update_calls == [("run-fake-scenario", 1)]
    assert result.tick_no == 1


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
async def test_talk_memories_use_subjective_importance_per_agent(db_session):
    run = SimulationRun(
        id="run-memory-subjective",
        name="subjective",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    plaza = Location(
        id="loc-plaza-subjective",
        run_id="run-memory-subjective",
        name="Plaza",
        location_type="plaza",
        capacity=4,
    )
    alice = Agent(
        id="alice-subjective",
        run_id="run-memory-subjective",
        name="Alice",
        occupation="resident",
        home_location_id=plaza.id,
        current_location_id=plaza.id,
        current_goal="talk",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    bob = Agent(
        id="bob-subjective",
        run_id="run-memory-subjective",
        name="Bob",
        occupation="resident",
        home_location_id=plaza.id,
        current_location_id=plaza.id,
        current_goal="rest",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, plaza, alice, bob])
    await db_session.commit()

    service = SimulationService(db_session)
    await service.run_tick(
        "run-memory-subjective",
        [
            ActionIntent(
                agent_id="alice-subjective",
                action_type="talk",
                target_agent_id="bob-subjective",
                payload={"message": "I am really worried about you."},
            )
        ],
    )

    alice_memories = await AgentRepository(db_session).list_recent_memories("alice-subjective")
    bob_memories = await AgentRepository(db_session).list_recent_memories("bob-subjective")

    assert len(alice_memories) == 1
    assert len(bob_memories) == 1
    assert alice_memories[0].importance < bob_memories[0].importance
    assert alice_memories[0].memory_category == "medium_term"
    assert bob_memories[0].memory_category == "medium_term"
    assert alice_memories[0].self_relevance < bob_memories[0].self_relevance


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


# ============================================================
# LLM Token Tracking Tests
# ============================================================


class TokenCapturingDecisionProvider(AgentDecisionProvider):
    """记录每次 decide 调用传入的 runtime_ctx，并触发 on_llm_call 回调。"""

    def __init__(self, usage: dict | None = None, cost: float = 0.01) -> None:
        self.captured_ctx: list = []
        self._usage = usage or {"input_tokens": 100, "output_tokens": 200}
        self._cost = cost

    async def decide(self, invocation: RuntimeInvocation, runtime_ctx=None):
        self.captured_ctx.append(runtime_ctx)
        if runtime_ctx and runtime_ctx.on_llm_call:
            runtime_ctx.on_llm_call(
                agent_id=invocation.agent_id,
                task_type=invocation.task,
                usage=self._usage,
                total_cost_usd=self._cost,
                duration_ms=500,
            )
        return RuntimeDecision(action_type="rest")


@pytest.mark.asyncio
async def test_prepare_intents_collects_llm_records_when_on_llm_call_set(db_session):
    """_prepare_intents_from_data 应收集 on_llm_call 触发的 LlmCall 记录。"""
    from app.agent.registry import AgentRegistry
    from app.agent.runtime import AgentRuntime
    from app.sim.world import WorldState
    from app.sim.types import AgentDecisionSnapshot
    import tempfile
    from pathlib import Path

    # 准备 DB 数据
    run_id = "run-token-track-1"
    run = SimulationRun(
        id=run_id, name="token-track", status="running", current_tick=3, tick_minutes=5
    )
    agent = Agent(
        id="agent-tt-1",
        run_id=run_id,
        name="Alice",
        occupation="resident",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    db_session.add_all([run, agent])
    await db_session.commit()

    # 构建最小 AgentRuntime
    tmp_path = Path(tempfile.mkdtemp())
    # 创建 agent 配置文件，避免 ValueError: Agent config not found
    agent_dir = tmp_path / "agent-tt-1"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "id: agent-tt-1\nname: Alice\noccupation: resident\nhome: loc-1\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")
    provider = TokenCapturingDecisionProvider(
        usage={"input_tokens": 130, "output_tokens": 250, "cache_read_input_tokens": 60},
        cost=0.025,
    )
    runtime = AgentRuntime(
        registry=AgentRegistry(tmp_path),
        decision_provider=provider,
    )
    orchestrator = TickOrchestrator(
        agent_runtime=runtime,
        scenario=FakeScenario(),
    )

    # 构建 WorldState 和 AgentDecisionSnapshot
    from datetime import datetime, timezone

    world = WorldState(current_time=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))
    world.agents["agent-tt-1"] = type(
        "S", (), {"id": "agent-tt-1", "status": {}, "location_id": "loc-1"}
    )()

    snapshot = AgentDecisionSnapshot(
        id="agent-tt-1",
        current_goal="rest",
        current_location_id="loc-1",
        home_location_id="loc-1",
        profile={},
        recent_events=[],
    )

    # 没有 engine，llm_records 应为空（不影响主流程）
    intents, llm_records = await orchestrator.prepare_intents_from_data(
        world=world,
        agent_data=[snapshot],
        engine=None,
        run_id=run_id,
        tick_no=3,
    )

    # engine=None 时不写 DB，但 llm_records 仍由 on_llm_call 收集
    assert len(llm_records) == 1
    assert llm_records[0].input_tokens == 130
    assert len(intents) == 1

    import shutil

    shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_run_tick_isolated_persists_llm_calls(db_session):
    """run_tick_isolated 应将 llm_call 记录写入 llm_calls 表。"""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from app.agent.registry import AgentRegistry
    from app.agent.runtime import AgentRuntime
    from app.store.models import Base
    import tempfile
    from pathlib import Path
    import shutil

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    run_id = "run-llm-persist-1"
    # agent_config_id 与 agent dir 名称一致，方便 AgentRuntime._load_agent 查找
    agent_config_id = "alice-llm"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id=run_id, name="llm-persist", status="running", current_tick=0, tick_minutes=5
        )
        loc = Location(id="loc-llm-1", run_id=run_id, name="Home", location_type="home", capacity=2)
        agent = Agent(
            id="agent-llm-p1",
            run_id=run_id,
            name="Alice",
            occupation="resident",
            home_location_id="loc-llm-1",
            current_location_id="loc-llm-1",
            personality={},
            # profile 中声明 agent_config_id，使 runtime_agent_id 能匹配到 agent dir
            profile={"agent_config_id": agent_config_id},
            status={},
            current_plan={},
        )
        session.add_all([run, loc, agent])
        await session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    # 创建 AgentRegistry 能找到的 agent 配置目录
    agent_dir = tmp_path / agent_config_id
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        f"id: {agent_config_id}\nname: Alice\noccupation: resident\nhome: loc-llm-1\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")

    provider = TokenCapturingDecisionProvider(
        usage={"input_tokens": 111, "output_tokens": 222, "cache_read_input_tokens": 33},
        cost=0.015,
    )
    runtime = AgentRuntime(registry=AgentRegistry(tmp_path), decision_provider=provider)
    service = SimulationService.create_for_scheduler(runtime)

    result = await service.run_tick_isolated(run_id, engine)

    assert result.tick_no == 1

    # 验证 llm_calls 已写入
    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = LlmCallRepository(session)
        totals = await repo.get_token_totals(run_id)
        assert totals["input_tokens"] == 111
        assert totals["output_tokens"] == 222
        assert totals["cache_read_tokens"] == 33

    await engine.dispose()
    shutil.rmtree(tmp_path)
