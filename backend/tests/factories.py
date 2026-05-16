from __future__ import annotations

from pathlib import Path
from typing import Any

from app.store.models import Agent, Event, Location, SimulationRun


def make_run(
    run_id: str,
    *,
    name: str | None = None,
    status: str = "running",
    scenario_type: str | None = None,
    current_tick: int = 0,
    tick_minutes: int = 5,
    metadata_json: dict[str, Any] | None = None,
) -> SimulationRun:
    kwargs: dict[str, Any] = {
        "id": run_id,
        "name": name or run_id,
        "status": status,
        "current_tick": current_tick,
        "tick_minutes": tick_minutes,
    }
    if scenario_type is not None:
        kwargs["scenario_type"] = scenario_type
    if metadata_json is not None:
        kwargs["metadata_json"] = metadata_json
    return SimulationRun(**kwargs)


def make_location(
    location_id: str,
    *,
    run_id: str,
    name: str = "Location",
    location_type: str = "plaza",
    capacity: int = 4,
    x: int = 0,
    y: int = 0,
    attributes: dict[str, Any] | None = None,
) -> Location:
    return Location(
        id=location_id,
        run_id=run_id,
        name=name,
        location_type=location_type,
        capacity=capacity,
        x=x,
        y=y,
        attributes=attributes or {},
    )


def make_agent(
    agent_id: str,
    *,
    run_id: str,
    location_id: str | None = None,
    name: str = "Agent",
    occupation: str = "resident",
    current_goal: str | None = None,
    profile: dict[str, Any] | None = None,
    status: dict[str, Any] | None = None,
    personality: dict[str, Any] | None = None,
    current_plan: dict[str, Any] | None = None,
) -> Agent:
    return Agent(
        id=agent_id,
        run_id=run_id,
        name=name,
        occupation=occupation,
        home_location_id=location_id,
        current_location_id=location_id,
        current_goal=current_goal,
        personality=personality or {},
        profile=profile or {},
        status=status or {},
        current_plan=current_plan or {},
    )


def make_event(
    event_id: str,
    *,
    run_id: str,
    event_type: str,
    tick_no: int = 1,
    actor_agent_id: str | None = None,
    target_agent_id: str | None = None,
    location_id: str | None = None,
    importance: float = 0.5,
    visibility: str = "public",
    payload: dict[str, Any] | None = None,
) -> Event:
    return Event(
        id=event_id,
        run_id=run_id,
        tick_no=tick_no,
        event_type=event_type,
        actor_agent_id=actor_agent_id,
        target_agent_id=target_agent_id,
        location_id=location_id,
        importance=importance,
        visibility=visibility,
        payload=payload or {},
    )


def write_agent_config(
    root: Path,
    agent_id: str,
    *,
    name: str = "Agent",
    occupation: str = "resident",
    home: str = "home",
    world_role: str | None = None,
    prompt: str | None = None,
) -> Path:
    agent_dir = root / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"id: {agent_id}",
        f"name: {name}",
        f"occupation: {occupation}",
        f"home: {home}",
    ]
    if world_role is not None:
        lines.insert(2, f"world_role: {world_role}")
    (agent_dir / "agent.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (agent_dir / "prompt.md").write_text(prompt or f"# {name}\nBase prompt", encoding="utf-8")
    return agent_dir
