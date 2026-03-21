"""Runtime-level director configuration loader."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.infra.logging import get_logger
from app.infra.settings import get_settings
from app.scenario.bundle_registry import (
    load_director_config_dict_for_scenario,
    load_director_prompt_template_for_scenario,
    resolve_default_scenario_id,
)

logger = get_logger(__name__)

_LEGACY_SCENARIO_DIR = Path(__file__).resolve().parents[1] / "bundle_world"
_LEGACY_DIRECTOR_CONFIG_PATH = _LEGACY_SCENARIO_DIR / "director.yml"

_config_cache: dict[tuple[str, str], dict[str, Any]] = {}
_config_load_time: dict[tuple[str, str], float] = {}
_CONFIG_CACHE_TTL = 30


@dataclass
class DirectorLLMConfig:
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2000
    max_budget_usd: float = 0.1
    max_turns: int = 1


@dataclass
class DirectorPromptConfig:
    file: str = "director_prompt.md"
    recent_events_limit: int = 10
    recent_interventions_limit: int = 5


@dataclass
class DirectorStrategy:
    name: str
    description: str
    condition: dict[str, Any]
    action: dict[str, Any]
    message_hint: str = ""


@dataclass
class DirectorEffectivenessConfig:
    evaluation_delay_ticks: int = 5
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class DirectorConfig:
    enabled: bool = True
    llm: DirectorLLMConfig = field(default_factory=DirectorLLMConfig)
    decision_interval: int = 5
    prompt: DirectorPromptConfig = field(default_factory=DirectorPromptConfig)
    strategies: dict[str, DirectorStrategy] = field(default_factory=dict)
    effectiveness: DirectorEffectivenessConfig = field(default_factory=DirectorEffectivenessConfig)
    scene_goals: dict[str, dict[str, str]] = field(default_factory=dict)
    scenario_id: str = "narrative_world"
    _prompt_template: str | None = None

    def get_prompt_template(self) -> str:
        if self._prompt_template is None:
            template = load_director_prompt_template_for_scenario(
                self.scenario_id, self.prompt.file
            )
            if template is not None:
                self._prompt_template = template
            else:
                logger.warning("Director prompt file not found for scenario %s", self.scenario_id)
                self._prompt_template = self._get_default_prompt()
        return self._prompt_template

    def render_prompt(self, context: dict[str, Any]) -> str:
        template = self.get_prompt_template()
        for key, value in context.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))
        return template

    def _get_default_prompt(self) -> str:
        return """You are the Director of the simulation.

Current Tick: {{current_tick}}
Subject Alert Score: {{subject_alert_score}}
Isolation Ticks: {{subject_isolation_ticks}}

Decide whether to intervene. Output JSON with should_intervene, scene_goal, target_agent_names, priority, urgency, reasoning, message_hint, strategy, cooldown_ticks."""

    def get_strategy(self, strategy_id: str) -> DirectorStrategy | None:
        return self.strategies.get(strategy_id)

    def list_strategies(self) -> list[DirectorStrategy]:
        return list(self.strategies.values())


def load_director_config(
    scenario_id: str | None = None,
    force_reload: bool = False,
) -> DirectorConfig:
    current_time = time.time()
    project_root = get_settings().project_root
    resolved_scenario_id = scenario_id or resolve_default_scenario_id(project_root=project_root)
    cache_key = _build_cache_key(project_root, resolved_scenario_id)
    if not force_reload and cache_key in _config_cache:
        if current_time - _config_load_time.get(cache_key, 0) < _CONFIG_CACHE_TTL:
            return _parse_config(_config_cache[cache_key], scenario_id=resolved_scenario_id)

    try:
        config_dict = load_director_config_dict_for_scenario(
            resolved_scenario_id, project_root=project_root
        )
        default_scenario_id = resolve_default_scenario_id(project_root=project_root)
        if not config_dict and resolved_scenario_id != default_scenario_id:
            config_dict = load_director_config_dict_for_scenario(
                default_scenario_id, project_root=project_root
            )
        if not config_dict:
            with open(_LEGACY_DIRECTOR_CONFIG_PATH, encoding="utf-8") as f:
                config_dict = yaml.safe_load(f)
        _config_cache[cache_key] = config_dict
        _config_load_time[cache_key] = current_time
        logger.debug("Loaded director config for %s", resolved_scenario_id)
    except FileNotFoundError:
        logger.warning("Director config file not found: %s", _LEGACY_DIRECTOR_CONFIG_PATH)
        return DirectorConfig(scenario_id=resolved_scenario_id)
    except yaml.YAMLError as exc:
        logger.error("Failed to parse director config: %s", exc)
        return DirectorConfig(scenario_id=resolved_scenario_id)

    return _parse_config(_config_cache[cache_key], scenario_id=resolved_scenario_id)


def _parse_config(
    config_dict: dict[str, Any],
    *,
    scenario_id: str = "narrative_world",
) -> DirectorConfig:
    if not config_dict:
        return DirectorConfig(scenario_id=scenario_id)

    llm_config = DirectorLLMConfig()
    if "llm" in config_dict:
        llm_dict = config_dict["llm"]
        llm_config.model = llm_dict.get("model")
        llm_config.temperature = llm_dict.get("temperature", 0.7)
        llm_config.max_tokens = llm_dict.get("max_tokens", 2000)
        llm_config.max_budget_usd = llm_dict.get("max_budget_usd", 0.1)
        llm_config.max_turns = llm_dict.get("max_turns", 1)

    prompt_config = DirectorPromptConfig()
    if "prompt" in config_dict:
        prompt_dict = config_dict["prompt"]
        prompt_config.file = prompt_dict.get("file", "director_prompt.md")
        prompt_config.recent_events_limit = prompt_dict.get("recent_events_limit", 10)
        prompt_config.recent_interventions_limit = prompt_dict.get(
            "recent_interventions_limit", 5
        )

    strategies: dict[str, DirectorStrategy] = {}
    if "strategies" in config_dict:
        for strategy_id, strategy_dict in config_dict["strategies"].items():
            strategies[strategy_id] = DirectorStrategy(
                name=strategy_dict.get("name", strategy_id),
                description=strategy_dict.get("description", ""),
                condition=strategy_dict.get("condition", {}),
                action=strategy_dict.get("action", {}),
                message_hint=strategy_dict.get("message_hint", ""),
            )

    effectiveness_config = DirectorEffectivenessConfig()
    if "effectiveness" in config_dict:
        eff_dict = config_dict["effectiveness"]
        effectiveness_config.evaluation_delay_ticks = eff_dict.get("evaluation_delay_ticks", 5)
        effectiveness_config.metrics = eff_dict.get("metrics", {})

    scene_goals = config_dict.get("scene_goals", {})

    return DirectorConfig(
        enabled=config_dict.get("enabled", True),
        llm=llm_config,
        decision_interval=config_dict.get("decision_interval", 5),
        prompt=prompt_config,
        strategies=strategies,
        effectiveness=effectiveness_config,
        scene_goals=scene_goals,
        scenario_id=scenario_id,
    )


def _build_cache_key(project_root: Path, scenario_id: str) -> tuple[str, str]:
    return (str(project_root.resolve()), scenario_id)
