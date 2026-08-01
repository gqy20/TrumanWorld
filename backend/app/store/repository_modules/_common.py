from __future__ import annotations
# ruff: noqa: F401

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Select, String, and_, case, cast, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.store.models import (
    Agent,
    AgentEconomicState,
    DirectorMemory,
    EconomicEffectLog,
    Event,
    GovernanceCase,
    GovernanceRecord,
    GovernanceRestriction,
    LlmCall,
    Location,
    Memory,
    Relationship,
    SimulationRun,
)


@dataclass(slots=True)
class AgentNameRow:
    id: str
    name: str


@dataclass(slots=True)
class AgentWorldRow:
    id: str
    name: str
    occupation: str | None
    current_goal: str | None
    current_location_id: str | None
    status: dict
    profile: dict
    movement: dict


@dataclass(slots=True)
class LocationNameRow:
    id: str
    name: str


@dataclass(slots=True)
class LocationWorldRow:
    id: str
    name: str
    location_type: str | None
    x: int
    y: int
    capacity: int


@dataclass(slots=True)
class EventApiRow:
    id: str
    tick_no: int
    world_time: datetime | None
    event_type: str
    actor_agent_id: str | None
    target_agent_id: str | None
    location_id: str | None
    importance: float
    visibility: str
    payload: dict
    created_at: datetime
