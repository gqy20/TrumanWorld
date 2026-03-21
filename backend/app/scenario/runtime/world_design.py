"""Runtime package loader for world design assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.infra.settings import get_settings
from app.scenario.bundle_registry import (
    load_constitution_text_for_scenario,
    load_policy_config_dict_for_scenario,
    load_rules_config_for_scenario,
    resolve_default_scenario_id,
)
from app.scenario.runtime.world_config import load_world_config
from app.scenario.runtime.world_design_models import (
    PolicyConfig,
    RulesConfig,
    WorldDesignRuntimePackage,
)

_WORLD_DESIGN_PACKAGE_CACHE: dict[tuple[str, str], WorldDesignRuntimePackage] = {}

_DEFAULT_POLICY_VALUES: dict[str, Any] = {
    "closed_locations": [],
    "restricted_locations": [],
    "power_outage_locations": [],
    "sensitive_locations": [],
    "high_attention_locations": [],
    "inspection_level": "low",
    "subject_protection_bias": "medium",
    "continuity_protection_level": "high",
    "talk_risk_after_hour": 23,
    "night_restriction_start_hour": 23,
    "night_restriction_end_hour": 6,
    "social_boost_locations": {},
    "warn_attention_delta": 0.05,
    "block_attention_delta": 0.15,
    "attention_score_cap": 1.0,
    "attention_decay_per_day": 0.05,
}


def load_world_design_runtime_package(
    scenario_id: str | None = None,
    *,
    force_reload: bool = False,
) -> WorldDesignRuntimePackage:
    project_root = get_settings().project_root
    resolved_scenario_id = scenario_id or resolve_default_scenario_id(project_root=project_root)
    cache_key = _build_cache_key(project_root, resolved_scenario_id)
    if not force_reload and cache_key in _WORLD_DESIGN_PACKAGE_CACHE:
        return _WORLD_DESIGN_PACKAGE_CACHE[cache_key]

    package = WorldDesignRuntimePackage(
        scenario_id=resolved_scenario_id,
        world_config=load_world_config(resolved_scenario_id, force_reload=force_reload),
        rules_config=_load_rules_config(resolved_scenario_id, project_root=project_root),
        policy_config=_load_policy_config(resolved_scenario_id, project_root=project_root),
        constitution_text=_load_constitution_text(resolved_scenario_id, project_root=project_root),
    )
    _WORLD_DESIGN_PACKAGE_CACHE[cache_key] = package
    return package


def _load_rules_config(
    scenario_id: str,
    *,
    project_root: Path,
) -> RulesConfig:
    raw = load_rules_config_for_scenario(scenario_id, project_root=project_root)
    return RulesConfig.model_validate(raw or {"version": 1, "rules": []})


def _load_policy_config(
    scenario_id: str,
    *,
    project_root: Path,
) -> PolicyConfig:
    raw = load_policy_config_dict_for_scenario(scenario_id, project_root=project_root)
    if not raw:
        raw = {"version": 1, "policy_id": "default", "values": {}}

    merged = {
        **raw,
        "values": {
            **_DEFAULT_POLICY_VALUES,
            **(raw.get("values") or {}),
        },
    }
    return PolicyConfig.model_validate(merged)


def _load_constitution_text(
    scenario_id: str,
    *,
    project_root: Path,
) -> str:
    return load_constitution_text_for_scenario(scenario_id, project_root=project_root) or ""


def _build_cache_key(project_root: Path, scenario_id: str) -> tuple[str, str]:
    return (str(project_root.resolve()), scenario_id)
