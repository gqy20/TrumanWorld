"""Compatibility facade for store repositories."""

from app.store.repository_modules.agents import AgentRepository
from app.store.repository_modules.director_memories import DirectorMemoryRepository
from app.store.repository_modules.director_directives import DirectorDirectiveRepository
from app.store.repository_modules.economic import (
    AgentEconomicStateRepository,
    EconomicEffectLogRepository,
)
from app.store.repository_modules.events import EventRepository
from app.store.repository_modules.governance import (
    GovernanceCaseRepository,
    GovernanceRecordRepository,
    GovernanceRestrictionRepository,
)
from app.store.repository_modules.llm_calls import LlmCallRepository
from app.store.repository_modules.locations import LocationRepository
from app.store.repository_modules.memories import MemoryRepository
from app.store.repository_modules.relationships import RelationshipRepository
from app.store.repository_modules.runs import RunRepository
from app.store.repository_modules.world_stats import WorldStatsRepository

__all__ = [
    "AgentEconomicStateRepository",
    "AgentRepository",
    "DirectorDirectiveRepository",
    "DirectorMemoryRepository",
    "EconomicEffectLogRepository",
    "EventRepository",
    "GovernanceCaseRepository",
    "GovernanceRecordRepository",
    "GovernanceRestrictionRepository",
    "LlmCallRepository",
    "LocationRepository",
    "MemoryRepository",
    "RelationshipRepository",
    "RunRepository",
    "WorldStatsRepository",
]
