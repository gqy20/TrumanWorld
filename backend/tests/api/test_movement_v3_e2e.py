from __future__ import annotations

import pytest

from app.sim.action_resolver import ActionIntent
from app.sim.service import SimulationService
from app.store.models import Agent, Location, SimulationRun


@pytest.mark.asyncio
async def test_movement_v3_survives_refresh_pause_resume_and_arrival(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000310"
    home_id = "movement-v3-home"
    park_id = "movement-v3-park"
    agent_id = "movement-v3-alice"
    run = SimulationRun(
        id=run_id,
        name="movement-v3-e2e",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    db_session.add_all(
        [
            run,
            Location(
                id=home_id,
                run_id=run_id,
                name="Home",
                location_type="home",
                x=0,
                y=0,
                capacity=4,
            ),
            Location(
                id=park_id,
                run_id=run_id,
                name="Park",
                location_type="park",
                x=4,
                y=2,
                capacity=4,
            ),
            Agent(
                id=agent_id,
                run_id=run_id,
                name="Alice",
                occupation="resident",
                home_location_id=home_id,
                current_location_id=home_id,
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
        ]
    )
    await db_session.commit()

    service = SimulationService(db_session)
    started = await service.run_tick(
        run_id,
        [ActionIntent(agent_id=agent_id, action_type="move", target_location_id=park_id)],
    )
    assert started.tick_no == 1

    first_snapshot = (await client.get(f"/api/runs/{run_id}/world")).json()
    refreshed_snapshot = (await client.get(f"/api/runs/{run_id}/world")).json()
    first_agent = next(agent for agent in first_snapshot["agents"] if agent["id"] == agent_id)
    refreshed_agent = next(
        agent for agent in refreshed_snapshot["agents"] if agent["id"] == agent_id
    )
    movement = first_agent["movement"]

    assert first_agent["current_location_id"] is None
    assert refreshed_agent["movement"] == movement
    assert (
        movement["route_node_ids"][0] == first_snapshot["navigation"]["location_entrances"][home_id]
    )
    assert (
        movement["route_node_ids"][-1]
        == first_snapshot["navigation"]["location_entrances"][park_id]
    )
    assert movement["distance"] == 6.0
    assert movement["speed"] == 1.5
    assert movement["arrival_tick"] == 5

    run.status = "paused"
    await db_session.commit()
    paused_snapshot = (await client.get(f"/api/runs/{run_id}/world")).json()
    paused_agent = next(agent for agent in paused_snapshot["agents"] if agent["id"] == agent_id)
    assert paused_snapshot["run"]["status"] == "paused"
    assert paused_snapshot["run"]["current_tick"] == 1
    assert paused_agent["movement"] == movement

    run.status = "running"
    await db_session.commit()
    for expected_tick in (2, 3, 4):
        travelling = await service.run_tick(run_id, [])
        assert travelling.tick_no == expected_tick
        assert all(result.action_type != "move_arrived" for result in travelling.accepted)

    arrived = await service.run_tick(run_id, [])
    assert arrived.tick_no == 5
    assert any(result.action_type == "move_arrived" for result in arrived.accepted)

    final_snapshot = (await client.get(f"/api/runs/{run_id}/world")).json()
    final_agent = next(agent for agent in final_snapshot["agents"] if agent["id"] == agent_id)
    event_types = [event["event_type"] for event in final_snapshot["recent_events"]]
    assert final_agent["current_location_id"] == park_id
    assert final_agent["movement"] is None
    assert "move" in event_types
    assert "move_arrived" in event_types
