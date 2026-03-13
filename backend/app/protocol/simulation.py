from __future__ import annotations

from typing import Literal, TypeAlias

ACTION_MOVE = "move"
ACTION_TALK = "talk"
ACTION_LISTEN = "listen"
ACTION_CONVERSATION_STARTED = "conversation_started"
ACTION_CONVERSATION_JOINED = "conversation_joined"
ACTION_WORK = "work"
ACTION_REST = "rest"

EVENT_MOVE = ACTION_MOVE
EVENT_TALK = ACTION_TALK
EVENT_SPEECH = "speech"
EVENT_LISTEN = ACTION_LISTEN
EVENT_CONVERSATION_STARTED = ACTION_CONVERSATION_STARTED
EVENT_CONVERSATION_JOINED = ACTION_CONVERSATION_JOINED
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
DIRECTOR_EVENT_POWER_OUTAGE = f"{DIRECTOR_EVENT_PREFIX}power_outage"
DIRECTOR_EVENT_KINDS = ("activity", "shutdown", "broadcast", "weather_change", "power_outage")

# 导演场景目标常量 - 自动干预
DIRECTOR_SCENE_SOFT_CHECK_IN = "soft_check_in"
DIRECTOR_SCENE_KEEP_NATURAL = "keep_scene_natural"
DIRECTOR_SCENE_PREEMPTIVE_COMFORT = "preemptive_comfort"  # 预防性安抚
DIRECTOR_SCENE_BREAK_ISOLATION = "break_isolation"  # 打破隔离
DIRECTOR_SCENE_REJECTION_RECOVERY = "rejection_recovery"  # 拒绝恢复

# 导演场景目标常量 - 手动注入
DIRECTOR_SCENE_GATHER = "gather"  # 集合场景
DIRECTOR_SCENE_ACTIVITY = "activity"  # 活动场景
DIRECTOR_SCENE_SHUTDOWN = "shutdown"  # 关闭场景
DIRECTOR_SCENE_WEATHER_CHANGE = "weather_change"  # 天气变化场景
DIRECTOR_SCENE_POWER_OUTAGE = "power_outage"  # 停电场景

ActionType: TypeAlias = Literal[
    "move",
    "talk",
    "listen",
    "conversation_started",
    "conversation_joined",
    "work",
    "rest",
    "plan",
    "reflect",
    "director_inject",
    "director_broadcast",
    "director_activity",
    "director_shutdown",
    "director_weather_change",
    "director_power_outage",
]
RejectedActionEventType: TypeAlias = Literal[
    "move_rejected",
    "talk_rejected",
    "listen_rejected",
    "conversation_started_rejected",
    "conversation_joined_rejected",
    "work_rejected",
    "rest_rejected",
    "plan_rejected",
    "reflect_rejected",
    "director_inject_rejected",
    "director_broadcast_rejected",
    "director_activity_rejected",
    "director_shutdown_rejected",
    "director_weather_change_rejected",
    "director_power_outage_rejected",
]
EventType: TypeAlias = ActionType | RejectedActionEventType | Literal["speech"]
DirectorSceneGoal: TypeAlias = Literal[
    # 自动干预
    "soft_check_in",
    "keep_scene_natural",
    "preemptive_comfort",
    "break_isolation",
    "rejection_recovery",
    # 手动注入
    "gather",
    "activity",
    "shutdown",
    "weather_change",
    "power_outage",
]


def build_rejected_event_type(action_type: ActionType) -> RejectedActionEventType:
    return f"{action_type}_rejected"


def build_director_event_type(event_type: str) -> str:
    if event_type not in DIRECTOR_EVENT_KINDS:
        msg = f"Unsupported director event type: {event_type}"
        raise ValueError(msg)
    return f"{DIRECTOR_EVENT_PREFIX}{event_type}"
