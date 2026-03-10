"""Generic scenario types shared across all scenario implementations.

These types are scenario-agnostic and must not import from any concrete
scenario (e.g. truman_world).  Concrete scenarios may extend these types
with their own private structures.
"""

from __future__ import annotations

from typing import Any, Mapping, TypedDict, cast


# ---------------------------------------------------------------------------
# World role
# ---------------------------------------------------------------------------

# Each scenario defines its own role names as plain strings.
# The generic layer does not enumerate them.
WorldRole = str


# ---------------------------------------------------------------------------
# Agent profile – generic key/value bag stored on Agent.profile
# ---------------------------------------------------------------------------


class AgentProfile(TypedDict, total=False):
    bio: str
    agent_config_id: str
    world_role: str          # scenario-defined role name
    workplace: str
    workplace_location_id: str
    work_description: str


# ---------------------------------------------------------------------------
# Scenario guidance – generic director/coordinator hints for agents
# ---------------------------------------------------------------------------


class ScenarioGuidance(TypedDict, total=False):
    scene_goal: str
    priority: str
    message_hint: str
    target_agent_id: str
    location_hint: str
    reason: str


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def get_world_role(profile: Mapping[str, Any] | None) -> str | None:
    """Return the world_role field from an agent profile, or None."""
    if not profile:
        return None
    role = profile.get("world_role")
    return role if isinstance(role, str) and role else None


def get_agent_config_id(profile: Mapping[str, Any] | None) -> str | None:
    """Return the agent_config_id field from an agent profile, or None."""
    if not profile:
        return None
    config_id = profile.get("agent_config_id")
    return config_id if isinstance(config_id, str) and config_id else None


def build_agent_profile(
    *,
    agent_config_id: str | None = None,
    world_role: str | None = None,
    bio: str | None = None,
    workplace: str | None = None,
    workplace_location_id: str | None = None,
    work_description: str | None = None,
    extras: Mapping[str, Any] | None = None,
) -> AgentProfile:
    """Build an AgentProfile dict from keyword arguments."""
    profile = cast(AgentProfile, dict(extras or {}))
    if bio is not None:
        profile["bio"] = bio
    if agent_config_id is not None:
        profile["agent_config_id"] = agent_config_id
    if world_role is not None:
        profile["world_role"] = world_role
    if workplace is not None:
        profile["workplace"] = workplace
    if workplace_location_id is not None:
        profile["workplace_location_id"] = workplace_location_id
    if work_description is not None:
        profile["work_description"] = work_description
    return profile


def merge_agent_profile(
    profile: Mapping[str, Any] | None,
    guidance: ScenarioGuidance | None = None,
) -> AgentProfile:
    """Merge an existing profile dict with optional scenario guidance."""
    base = cast(AgentProfile, dict(profile or {}))
    if guidance:
        base.update(guidance)
    return base
