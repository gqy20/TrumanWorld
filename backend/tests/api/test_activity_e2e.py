from __future__ import annotations

import pytest

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
