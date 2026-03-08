from __future__ import annotations

from typing import Literal, TypeAlias

ACTION_MOVE = "move"
ACTION_TALK = "talk"
ACTION_WORK = "work"
ACTION_REST = "rest"

EVENT_MOVE = ACTION_MOVE
EVENT_TALK = ACTION_TALK
EVENT_WORK = ACTION_WORK
EVENT_REST = ACTION_REST
EVENT_PLAN = "plan"
EVENT_REFLECT = "reflect"

DIRECTOR_EVENT_PREFIX = "director_"
DIRECTOR_EVENT_INJECT = f"{DIRECTOR_EVENT_PREFIX}inject"
DIRECTOR_EVENT_BROADCAST = f"{DIRECTOR_EVENT_PREFIX}broadcast"
DIRECTOR_EVENT_ACTIVITY = f"{DIRECTOR_EVENT_PREFIX}activity"
DIRECTOR_EVENT_SHUTDOWN = f"{DIRECTOR_EVENT_PREFIX}shutdown"
DIRECTOR_EVENT_WEATHER_CHANGE = f"{DIRECTOR_EVENT_PREFIX}weather_change"
DIRECTOR_EVENT_KINDS = ("activity", "shutdown", "broadcast", "weather_change")

# 导演场景目标常量
DIRECTOR_SCENE_SOFT_CHECK_IN = "soft_check_in"
DIRECTOR_SCENE_KEEP_NATURAL = "keep_scene_natural"
DIRECTOR_SCENE_PREEMPTIVE_COMFORT = "preemptive_comfort"  # 预防性安抚
DIRECTOR_SCENE_BREAK_ISOLATION = "break_isolation"  # 打破隔离
DIRECTOR_SCENE_REJECTION_RECOVERY = "rejection_recovery"  # 拒绝恢复

ActionType: TypeAlias = Literal[
    "move",
    "talk",
    "work",
    "rest",
    "plan",
    "reflect",
    "director_inject",
    "director_broadcast",
    "director_activity",
    "director_shutdown",
    "director_weather_change",
]
RejectedActionEventType: TypeAlias = Literal[
    "move_rejected",
    "talk_rejected",
    "work_rejected",
    "rest_rejected",
    "plan_rejected",
    "reflect_rejected",
    "director_inject_rejected",
    "director_broadcast_rejected",
    "director_activity_rejected",
    "director_shutdown_rejected",
    "director_weather_change_rejected",
]
EventType: TypeAlias = ActionType | RejectedActionEventType
DirectorSceneGoal: TypeAlias = Literal[
    "soft_check_in",
    "keep_scene_natural",
    "preemptive_comfort",
    "break_isolation",
    "rejection_recovery",
]


def build_rejected_event_type(action_type: ActionType) -> RejectedActionEventType:
    return f"{action_type}_rejected"


def build_director_event_type(event_type: str) -> str:
    if event_type not in DIRECTOR_EVENT_KINDS:
        msg = f"Unsupported director event type: {event_type}"
        raise ValueError(msg)
    return f"{DIRECTOR_EVENT_PREFIX}{event_type}"
