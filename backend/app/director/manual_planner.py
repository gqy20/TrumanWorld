"""Manual director event planner - converts manual injections to DirectorPlan.

This module provides the ManualDirectorPlanner class that transforms
manual director events (broadcast, activity, shutdown, weather_change)
into DirectorPlan objects, unifying the manual and automatic intervention
flows.
"""

from __future__ import annotations

from app.director.types import DirectorPlan
from app.protocol.simulation import (
    DIRECTOR_SCENE_ACTIVITY,
    DIRECTOR_SCENE_GATHER,
    DIRECTOR_SCENE_POWER_OUTAGE,
    DIRECTOR_SCENE_SHUTDOWN,
    DIRECTOR_SCENE_WEATHER_CHANGE,
)
from app.scenario.types import get_world_role
from app.store.models import Agent


class ManualDirectorPlanner:
    """Converts manual director events into DirectorPlan objects.

    This planner unifies manual injection with automatic intervention
    by converting event types into scene goals that Cast Agents can
    understand and act upon.
    """

    def build_plan_from_manual_event(
        self,
        event_type: str,
        payload: dict,
        location_id: str | None,
        agents: list[Agent],
        subject_agent_id: str | None = None,
        truman_agent_id: str | None = None,
    ) -> DirectorPlan | None:
        """Build a DirectorPlan from a manual event injection.

        Args:
            event_type: The type of event (broadcast, activity, shutdown, weather_change, power_outage)
            payload: Event payload containing message and other data
            location_id: Optional target location ID
            agents: List of all agents in the run
            subject_agent_id: Primary subject agent ID (if exists)
            truman_agent_id: Legacy alias for subject agent ID

        Returns:
            DirectorPlan or None if event_type is not supported
        """
        cast_agents = [a for a in agents if get_world_role(a.profile) == "cast"]
        if not cast_agents:
            return None
        resolved_subject_agent_id = (
            subject_agent_id if subject_agent_id is not None else truman_agent_id
        )

        if event_type == "broadcast":
            return self._build_gather_plan(
                payload=payload,
                location_id=location_id,
                cast_agents=cast_agents,
                subject_agent_id=resolved_subject_agent_id,
            )

        if event_type == "activity":
            return self._build_activity_plan(
                payload=payload,
                location_id=location_id,
                cast_agents=cast_agents,
                subject_agent_id=resolved_subject_agent_id,
            )

        if event_type == "shutdown":
            return self._build_shutdown_plan(
                payload=payload,
                location_id=location_id,
                cast_agents=cast_agents,
                subject_agent_id=resolved_subject_agent_id,
            )

        if event_type == "weather_change":
            return self._build_weather_plan(
                payload=payload,
                location_id=location_id,
                cast_agents=cast_agents,
                subject_agent_id=resolved_subject_agent_id,
            )

        if event_type == "power_outage":
            return self._build_power_outage_plan(
                payload=payload,
                location_id=location_id,
                cast_agents=cast_agents,
                subject_agent_id=resolved_subject_agent_id,
            )

        return None

    def _build_gather_plan(
        self,
        payload: dict,
        location_id: str | None,
        cast_agents: list[Agent],
        subject_agent_id: str | None,
    ) -> DirectorPlan:
        """Build a gather plan for broadcast events.

        Example: "12点钟集合" -> Cast Agents should gather at location
        """
        message = payload.get("message", "")
        target_agent_ids = [a.id for a in cast_agents]

        return DirectorPlan(
            scene_goal=DIRECTOR_SCENE_GATHER,
            target_agent_ids=target_agent_ids,
            priority="high",
            urgency="immediate",
            message_hint=message,
            location_hint=location_id,
            target_agent_id=subject_agent_id,
            reason=f"导演广播: {message}",
            cooldown_ticks=2,
        )

    def _build_activity_plan(
        self,
        payload: dict,
        location_id: str | None,
        cast_agents: list[Agent],
        subject_agent_id: str | None,
    ) -> DirectorPlan:
        """Build an activity plan for activity events.

        Example: "咖啡馆派对" -> Cast Agents should participate in activity
        """
        message = payload.get("message", "")
        target_agent_ids = [a.id for a in cast_agents]

        return DirectorPlan(
            scene_goal=DIRECTOR_SCENE_ACTIVITY,
            target_agent_ids=target_agent_ids,
            priority="high",
            urgency="immediate",
            message_hint=message,
            location_hint=location_id,
            target_agent_id=subject_agent_id,
            reason=f"举办活动: {message}",
            cooldown_ticks=4,
        )

    def _build_shutdown_plan(
        self,
        payload: dict,
        location_id: str | None,
        cast_agents: list[Agent],
        subject_agent_id: str | None,
    ) -> DirectorPlan:
        """Build a shutdown plan for location shutdown events.

        Example: "医院临时关闭" -> Cast Agents should avoid location
        """
        message = payload.get("message", "")
        target_agent_ids = [a.id for a in cast_agents]

        return DirectorPlan(
            scene_goal=DIRECTOR_SCENE_SHUTDOWN,
            target_agent_ids=target_agent_ids,
            priority="high",
            urgency="immediate",
            message_hint=message,
            location_hint=location_id,
            target_agent_id=subject_agent_id,
            reason=f"地点关闭: {message}",
            cooldown_ticks=3,
        )

    def _build_weather_plan(
        self,
        payload: dict,
        location_id: str | None,
        cast_agents: list[Agent],
        subject_agent_id: str | None,
    ) -> DirectorPlan:
        """Build a weather change plan for weather events.

        Example: "暴雨预警" -> Cast Agents should react to weather
        """
        message = payload.get("message", "")
        target_agent_ids = [a.id for a in cast_agents]

        return DirectorPlan(
            scene_goal=DIRECTOR_SCENE_WEATHER_CHANGE,
            target_agent_ids=target_agent_ids,
            priority="normal",
            urgency="advisory",
            message_hint=message,
            location_hint=location_id,
            target_agent_id=subject_agent_id,
            reason=f"天气变化: {message}",
            cooldown_ticks=2,
        )

    def _build_power_outage_plan(
        self,
        payload: dict,
        location_id: str | None,
        cast_agents: list[Agent],
        subject_agent_id: str | None,
    ) -> DirectorPlan:
        """Build a power outage plan that combines world change and cast reaction."""
        message = payload.get("message", "")
        target_agent_ids = [a.id for a in cast_agents]

        return DirectorPlan(
            scene_goal=DIRECTOR_SCENE_POWER_OUTAGE,
            target_agent_ids=target_agent_ids,
            priority="high",
            urgency="immediate",
            message_hint=message,
            location_hint=location_id,
            target_agent_id=subject_agent_id,
            reason=f"停电影响: {message}",
            cooldown_ticks=3,
        )
