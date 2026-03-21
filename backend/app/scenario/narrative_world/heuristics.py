"""Compatibility wrappers for the legacy narrative-world heuristics module."""

from app.scenario.bundle_world.heuristics import (
    build_bundle_world_decision,
    build_narrative_world_decision,
)

__all__ = ["build_bundle_world_decision", "build_narrative_world_decision"]
