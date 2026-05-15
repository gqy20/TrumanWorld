from __future__ import annotations

from datetime import datetime

from app.api.schemas.simulation import (
    TimelineEventResponse,
    WorldClockResponse,
    WorldEventResponse,
)
from app.sim.world_time import tick_to_world_time


def enrich_event_payload(
    event, agent_name_map: dict[str, str], location_name_map: dict[str, str]
) -> dict:
    """Fill display names in event payloads without mutating stored payloads."""
    payload = dict(event.payload or {})
    if event.actor_agent_id and "actor_name" not in payload:
        payload["actor_name"] = agent_name_map.get(event.actor_agent_id, event.actor_agent_id)
    if event.target_agent_id and "target_name" not in payload:
        payload["target_name"] = agent_name_map.get(event.target_agent_id, event.target_agent_id)
    if event.location_id and "location_name" not in payload:
        payload["location_name"] = location_name_map.get(event.location_id, event.location_id)

    to_loc_id = payload.get("to_location_id")
    if to_loc_id and "to_location_name" not in payload:
        payload["to_location_name"] = location_name_map.get(str(to_loc_id), str(to_loc_id))

    from_loc_id = payload.get("from_location_id")
    if from_loc_id and "from_location_name" not in payload:
        payload["from_location_name"] = location_name_map.get(str(from_loc_id), str(from_loc_id))
    return payload


def build_world_event_response(
    event, agent_name_map: dict[str, str], location_name_map: dict[str, str]
) -> WorldEventResponse:
    return WorldEventResponse(
        id=event.id,
        tick_no=event.tick_no,
        event_type=event.event_type,
        location_id=event.location_id,
        actor_agent_id=event.actor_agent_id,
        target_agent_id=event.target_agent_id,
        actor_name=agent_name_map.get(event.actor_agent_id) if event.actor_agent_id else None,
        target_name=agent_name_map.get(event.target_agent_id) if event.target_agent_id else None,
        location_name=location_name_map.get(event.location_id) if event.location_id else None,
        payload=enrich_event_payload(event, agent_name_map, location_name_map),
    )


def build_timeline_event_response(
    event,
    agent_name_map: dict[str, str],
    location_name_map: dict[str, str],
    world_start: datetime,
    tick_minutes: int,
) -> TimelineEventResponse:
    world_time, world_date = tick_to_world_time(event.tick_no, world_start, tick_minutes)
    return TimelineEventResponse(
        id=event.id,
        tick_no=event.tick_no,
        event_type=event.event_type,
        importance=event.importance,
        payload=enrich_event_payload(event, agent_name_map, location_name_map),
        world_time=world_time,
        world_date=world_date,
    )


def build_world_clock(world_time: datetime) -> WorldClockResponse:
    weekday = world_time.weekday()
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_names_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

    hour = world_time.hour
    if hour < 5:
        time_period = "night"
        time_period_cn = "深夜"
    elif hour < 7:
        time_period = "dawn"
        time_period_cn = "黎明"
    elif hour < 12:
        time_period = "morning"
        time_period_cn = "上午"
    elif hour < 14:
        time_period = "noon"
        time_period_cn = "中午"
    elif hour < 18:
        time_period = "afternoon"
        time_period_cn = "下午"
    elif hour < 21:
        time_period = "evening"
        time_period_cn = "傍晚"
    else:
        time_period = "night"
        time_period_cn = "夜晚"

    return WorldClockResponse(
        iso=world_time.isoformat(),
        date=world_time.strftime("%Y-%m-%d"),
        time=world_time.strftime("%H:%M"),
        year=world_time.year,
        month=world_time.month,
        day=world_time.day,
        hour=hour,
        minute=world_time.minute,
        weekday=weekday,
        weekday_name=weekday_names[weekday],
        weekday_name_cn=weekday_names_cn[weekday],
        is_weekend=weekday >= 5,
        time_period=time_period,
        time_period_cn=time_period_cn,
    )
