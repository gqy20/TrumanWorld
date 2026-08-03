from __future__ import annotations

import pytest
from sqlalchemy import select

from app.sim.action_resolver import ActionIntent
from app.sim.service import SimulationService
from app.store.models import Agent, Location, SimulationRun


@pytest.mark.asyncio
async def test_activity_survives_refresh_pause_resume_and_completes(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000311"
    location_id = "activity-cafe"
    agent_id = "activity-mei"
    run = SimulationRun(
        id=run_id,
        name="activity-e2e",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    db_session.add_all(
        [
            run,
            Location(
                id=location_id,
                run_id=run_id,
                name="Cafe",
                location_type="cafe",
                x=0,
                y=0,
                capacity=4,
            ),
            Agent(
                id=agent_id,
                run_id=run_id,
                name="Mei",
                home_location_id=location_id,
                current_location_id=location_id,
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
        ]
    )
    await db_session.commit()
    service = SimulationService(db_session)

    await service.run_tick(
        run_id,
        [
            ActionIntent(
                agent_id=agent_id,
                action_type="start_activity",
                payload={"activity_type": "drink_coffee", "duration_seconds": 480},
            )
        ],
    )
    first = (await client.get(f"/api/runs/{run_id}/world")).json()
    refreshed = (await client.get(f"/api/runs/{run_id}/world")).json()
    activity = next(agent for agent in first["agents"] if agent["id"] == agent_id)["activity"]

    assert activity["status"] == "performing"
    assert activity["progress"] == 0.0
    assert activity["started_at_world_time"] == "2026-03-02T06:05:00Z"
    assert activity["expected_end_world_time"] == "2026-03-02T06:13:00Z"
    assert (
        next(agent for agent in refreshed["agents"] if agent["id"] == agent_id)["activity"]
        == activity
    )

    run.status = "paused"
    await db_session.commit()
    paused = (await client.get(f"/api/runs/{run_id}/world")).json()
    assert paused["run"]["current_tick"] == 1
    assert (
        next(agent for agent in paused["agents"] if agent["id"] == agent_id)["activity"] == activity
    )

    run.status = "running"
    await db_session.commit()
    await service.run_tick(run_id, [])
    completed = await service.run_tick(run_id, [])

    assert any(result.action_type == "activity_completed" for result in completed.accepted)
    final = (await client.get(f"/api/runs/{run_id}/world")).json()
    final_activity = next(agent for agent in final["agents"] if agent["id"] == agent_id)["activity"]
    assert final_activity["status"] == "completed"
    assert final_activity["progress"] == 1.0
    completed_event = next(
        event for event in final["recent_events"] if event["event_type"] == "activity_completed"
    )
    assert completed_event["payload"]["occurred_at_world_time"] == ("2026-03-02T06:13:00+00:00")


@pytest.mark.asyncio
async def test_configured_activity_persists_resource_occupancy_and_queue(client, db_session):
    created = await client.post(
        "/api/runs",
        json={"name": "coffee-queue", "scenario_type": "campus_world", "auto_start": False},
    )
    run_id = created.json()["id"]
    agents = list(
        (
            await db_session.scalars(select(Agent).where(Agent.run_id == run_id).order_by(Agent.id))
        ).all()
    )
    cafe = await db_session.scalar(
        select(Location).where(
            Location.run_id == run_id,
            Location.id == f"{run_id}-cafe",
        )
    )
    assert cafe is not None
    run = await db_session.get(SimulationRun, run_id)
    assert run is not None
    run.current_tick = 36
    first, second = agents[:2]
    first.current_location_id = cafe.id
    second.current_location_id = cafe.id
    await db_session.commit()

    service = SimulationService(db_session)
    result = await service.run_tick(
        run_id,
        [
            ActionIntent(
                agent_id=first.id,
                action_type="start_activity",
                target_location_id=cafe.id,
                payload={"activity_type": "drink_coffee"},
            ),
            ActionIntent(
                agent_id=second.id,
                action_type="start_activity",
                target_location_id=cafe.id,
                payload={"activity_type": "drink_coffee"},
            ),
        ],
    )

    assert [item.action_type for item in result.accepted[:2]] == [
        "activity_started",
        "activity_started",
    ]
    snapshot = (await client.get(f"/api/runs/{run_id}/world")).json()
    counter = next(
        item
        for item in snapshot["object_states"]
        if item["resource_id"] == "slot:cafe:coffee-counter:service"
    )
    assert counter["occupant_agent_ids"] == [first.id]
    assert counter["queue_agent_ids"] == [second.id]
    first_snapshot = next(item for item in snapshot["agents"] if item["id"] == first.id)
    second_snapshot = next(item for item in snapshot["agents"] if item["id"] == second.id)
    assert first_snapshot["position_meters"] == [5.0, 0.0, -1.2]
    assert first_snapshot["zone_id"] == "cafe.counter"
    assert first_snapshot["activity"]["current_step_id"] == "order"
    assert second_snapshot["activity"]["status"] == "waiting_for_resource"
    assert second_snapshot["activity"]["queue_position"] == 1
    assert second_snapshot["position_meters"] == [5.0, 0.0, -0.2]
    assert second_snapshot["zone_id"] == "cafe.counter"

    await SimulationService(db_session).run_tick(run_id, [])
    resumed = (await client.get(f"/api/runs/{run_id}/world")).json()
    chair = next(
        item
        for item in resumed["object_states"]
        if item["resource_id"] == "slot:cafe:window-chair-1:sit"
    )
    resumed_first = next(item for item in resumed["agents"] if item["id"] == first.id)
    resumed_second = next(item for item in resumed["agents"] if item["id"] == second.id)
    assert chair["occupant_agent_ids"] == [first.id]
    assert resumed_first["activity"]["current_step_id"] == "drink"
    assert resumed_second["activity"]["current_step_id"] == "take_seat"
    assert resumed_second["activity"]["status"] == "waiting_for_resource"


@pytest.mark.asyncio
async def test_manual_action_api_starts_activity_and_returns_event_details(client, db_session):
    created = await client.post(
        "/api/runs",
        json={"name": "manual-coffee", "scenario_type": "campus_world", "auto_start": False},
    )
    run_id = created.json()["id"]
    agent = await db_session.scalar(select(Agent).where(Agent.run_id == run_id))
    assert agent is not None
    cafe_id = f"{run_id}-cafe"
    agent.current_location_id = cafe_id
    await db_session.commit()

    response = await client.post(
        f"/api/runs/{run_id}/actions",
        json={
            "agent_id": agent.id,
            "action_type": "start_activity",
            "target_location_id": cafe_id,
            "payload": {"activity_type": "drink_coffee"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tick_no"] > 0
    started = next(item for item in body["accepted"] if item["action_type"] == "activity_started")
    assert started["event_payload"]["activity_type"] == "drink_coffee"


@pytest.mark.asyncio
async def test_manual_action_api_rejects_unknown_agent_without_advancing_world(client):
    created = await client.post(
        "/api/runs",
        json={"name": "manual-invalid", "scenario_type": "campus_world", "auto_start": False},
    )
    run_id = created.json()["id"]

    response = await client.post(
        f"/api/runs/{run_id}/actions",
        json={"agent_id": "unknown", "action_type": "rest"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "AGENT_NOT_FOUND"
    run = (await client.get(f"/api/runs/{run_id}")).json()
    assert run["current_tick"] == 0
