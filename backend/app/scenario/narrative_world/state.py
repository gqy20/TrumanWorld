"""Compatibility wrappers for the legacy narrative-world state module."""

from app.scenario.bundle_world.state import (
    BundleWorldStateUpdater,
    NarrativeWorldStateUpdater,
    build_alert_state_semantics,
)

__all__ = [
    "BundleWorldStateUpdater",
    "NarrativeWorldStateUpdater",
    "build_alert_state_semantics",
]
