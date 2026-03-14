from __future__ import annotations

from typing import TYPE_CHECKING

from app.director.manual_planner import ManualDirectorPlanner
from app.protocol.simulation import build_director_event_type
from app.scenario.types import get_world_role
from app.sim.context import get_run_world_time
from app.sim.event_utils import build_event
from app.store.repositories import (
    AgentRepository,
    DirectorMemoryRepository,
    EventRepository,
    LocationRepository,
    RunRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class DirectorEventService:
    def __init__(self, session: AsyncSession) -> None:
        self.run_repo = RunRepository(session)
        self.agent_repo = AgentRepository(session)
        self.director_memory_repo = DirectorMemoryRepository(session)
        self.event_repo = EventRepository(session)
        self.location_repo = LocationRepository(session)
        self.manual_planner = ManualDirectorPlanner()

    async def inject_event(
        self,
        *,
        run_id: str,
        event_type: str,
        payload: dict,
        location_id: str | None = None,
        importance: float = 0.5,
    ) -> None:
        run = await self.run_repo.get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)

        if location_id is not None:
            locations = await self.location_repo.list_for_run(run_id)
            valid_location_ids = {location.id for location in locations}
            if location_id not in valid_location_ids:
                msg = f"Invalid location_id for this run: {location_id}"
                raise ValueError(msg)

        if event_type == "power_outage" and location_id is None:
            msg = "power_outage requires location_id"
            raise ValueError(msg)

        agents = await self.agent_repo.list_for_run(run_id)
        truman = next(
            (agent for agent in agents if get_world_role(agent.profile) == "truman"), None
        )
        plan = self.manual_planner.build_plan_from_manual_event(
            event_type=event_type,
            payload=payload,
            location_id=location_id,
            agents=agents,
            truman_agent_id=truman.id if truman else None,
        )
        if plan is None:
            msg = f"Unsupported director event type: {event_type}"
            raise ValueError(msg)

        await self.director_memory_repo.create(
            run_id=run_id,
            tick_no=run.current_tick,
            scene_goal=plan.scene_goal,
            target_cast_ids=plan.target_cast_ids,
            priority=plan.priority,
            urgency=plan.urgency,
            message_hint=plan.message_hint,
            target_agent_id=plan.target_agent_id,
            reason=plan.reason,
            trigger_suspicion_score=0.0,
            trigger_continuity_risk="stable",
            cooldown_ticks=plan.cooldown_ticks,
            location_hint=plan.location_hint,
        )

        if event_type == "power_outage":
            await self._persist_power_outage_effect(
                run=run,
                location_id=location_id,
                payload=payload,
            )

        event = build_event(
            run_id=run_id,
            tick_no=run.current_tick,
            world_time=get_run_world_time(run).isoformat(),
            action_type=build_director_event_type(event_type),
            payload=payload,
            accepted=True,
        )
        event.location_id = location_id
        event.importance = importance
        event.visibility = "public" if event_type == "power_outage" else "system"
        await self.event_repo.create(event)

    async def _persist_power_outage_effect(
        self,
        *,
        run,
        location_id: str | None,
        payload: dict,
    ) -> None:
        if location_id is None:
            return

        metadata = dict(run.metadata_json or {})
        world_effects = dict(metadata.get("world_effects") or {})
        power_outages = list(world_effects.get("power_outages") or [])
        duration_ticks = payload.get("duration_ticks", 3)
        try:
            duration_ticks = int(duration_ticks)
        except (TypeError, ValueError):
            duration_ticks = 3
        duration_ticks = max(1, duration_ticks)

        power_outages.append(
            {
                "location_id": location_id,
                "start_tick": run.current_tick,
                "end_tick": run.current_tick + duration_ticks,
                "message": payload.get("message", ""),
            }
        )
        world_effects["power_outages"] = power_outages
        metadata["world_effects"] = world_effects
        run.metadata_json = metadata
        await self.run_repo.session.commit()
        await self.run_repo.session.refresh(run)
