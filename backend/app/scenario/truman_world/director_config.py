"""Director configuration loader for TrumanWorld scenario.

This module provides configuration management for the Director Agent,
loading settings from YAML files and providing a clean interface for access.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.infra.logging import get_logger
from app.scenario.bundle_registry import (
    load_director_config_dict_for_scenario,
    load_director_prompt_template_for_scenario,
)

logger = get_logger(__name__)

# Configuration file paths
_SCENARIO_DIR = Path(__file__).parent
_DIRECTOR_CONFIG_PATH = _SCENARIO_DIR / "director.yml"
_DIRECTOR_PROMPT_PATH = _SCENARIO_DIR / "director_prompt.md"

# Cache for configuration
_config_cache: dict[str, dict[str, Any]] = {}
_config_load_time: dict[str, float] = {}
_CONFIG_CACHE_TTL = 30  # 30 seconds cache TTL for development


@dataclass
class DirectorLLMConfig:
    """LLM configuration for Director Agent."""

    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2000
    max_budget_usd: float = 0.1
    max_turns: int = 1


@dataclass
class DirectorPromptConfig:
    """Prompt configuration for Director Agent."""

    file: str = "director_prompt.md"
    recent_events_limit: int = 10
    recent_interventions_limit: int = 5


@dataclass
class DirectorStrategy:
    """Strategy rule configuration."""

    name: str
    description: str
    condition: dict[str, Any]
    action: dict[str, Any]
    message_hint: str = ""


@dataclass
class DirectorEffectivenessConfig:
    """Effectiveness evaluation configuration."""

    evaluation_delay_ticks: int = 5
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class DirectorConfig:
    """Complete Director Agent configuration."""

    enabled: bool = True
    llm: DirectorLLMConfig = field(default_factory=DirectorLLMConfig)
    decision_interval: int = 5  # 默认 5 个 tick 一次
    prompt: DirectorPromptConfig = field(default_factory=DirectorPromptConfig)
    strategies: dict[str, DirectorStrategy] = field(default_factory=dict)
    effectiveness: DirectorEffectivenessConfig = field(default_factory=DirectorEffectivenessConfig)
    scene_goals: dict[str, dict[str, str]] = field(default_factory=dict)
    scenario_id: str = "truman_world"

    # Internal
    _prompt_template: str | None = None

    def get_prompt_template(self) -> str:
        """Get the prompt template, loading from file if needed."""
        if self._prompt_template is None:
            template = load_director_prompt_template_for_scenario(self.scenario_id, self.prompt.file)
            if template is not None:
                self._prompt_template = template
            else:
                prompt_path = _SCENARIO_DIR / self.prompt.file
                logger.warning(f"Director prompt file not found: {prompt_path}")
                self._prompt_template = self._get_default_prompt()
        return self._prompt_template

    def render_prompt(self, context: dict[str, Any]) -> str:
        """Render the prompt template with context variables."""
        template = self.get_prompt_template()

        # Simple template substitution
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            template = template.replace(placeholder, str(value))

        return template

    def _get_default_prompt(self) -> str:
        """Get default prompt if file is not found."""
        return """You are the Director of the Truman World simulation.

Current Tick: {{current_tick}}
Truman Suspicion: {{truman_suspicion_score}}
Isolation Ticks: {{truman_isolation_ticks}}

Decide whether to intervene. Output JSON with should_intervene, scene_goal, target_agent_names, priority, urgency, reasoning, message_hint, strategy, cooldown_ticks. Legacy target_cast_names is still accepted for compatibility."""

    def get_strategy(self, strategy_id: str) -> DirectorStrategy | None:
        """Get a strategy by ID."""
        return self.strategies.get(strategy_id)

    def list_strategies(self) -> list[DirectorStrategy]:
        """List all available strategies."""
        return list(self.strategies.values())


def load_director_config(
    scenario_id: str = "truman_world",
    force_reload: bool = False,
) -> DirectorConfig:
    """Load director configuration from YAML file.

    Uses caching to avoid repeated file reads. In development mode,
    the cache is invalidated every 30 seconds to allow hot-reloading.

    Args:
        force_reload: Force reload configuration from file

    Returns:
        DirectorConfig instance
    """
    current_time = time.time()

    # Check if we can use cached config
    if not force_reload and scenario_id in _config_cache:
        if current_time - _config_load_time.get(scenario_id, 0) < _CONFIG_CACHE_TTL:
            return _parse_config(_config_cache[scenario_id], scenario_id=scenario_id)

    # Load from file
    try:
        config_dict = load_director_config_dict_for_scenario(scenario_id)
        if not config_dict and scenario_id != "truman_world":
            config_dict = load_director_config_dict_for_scenario("truman_world")
        if not config_dict:
            with open(_DIRECTOR_CONFIG_PATH, encoding="utf-8") as f:
                config_dict = yaml.safe_load(f)
        _config_cache[scenario_id] = config_dict
        _config_load_time[scenario_id] = current_time
        logger.debug(f"Loaded director config for {scenario_id}")
    except FileNotFoundError:
        logger.warning(f"Director config file not found: {_DIRECTOR_CONFIG_PATH}")
        return DirectorConfig()  # Return default config
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse director config: {e}")
        return DirectorConfig()  # Return default config

    return _parse_config(_config_cache[scenario_id], scenario_id=scenario_id)


def _parse_config(
    config_dict: dict[str, Any],
    *,
    scenario_id: str = "truman_world",
) -> DirectorConfig:
    """Parse configuration dictionary into DirectorConfig."""
    if not config_dict:
        return DirectorConfig()

    # Parse LLM config
    llm_config = DirectorLLMConfig()
    if "llm" in config_dict:
        llm_dict = config_dict["llm"]
        llm_config.model = llm_dict.get("model")
        llm_config.temperature = llm_dict.get("temperature", 0.7)
        llm_config.max_tokens = llm_dict.get("max_tokens", 2000)
        llm_config.max_budget_usd = llm_dict.get("max_budget_usd", 0.1)
        llm_config.max_turns = llm_dict.get("max_turns", 1)

    # Parse prompt config
    prompt_config = DirectorPromptConfig()
    if "prompt" in config_dict:
        prompt_dict = config_dict["prompt"]
        prompt_config.file = prompt_dict.get("file", "director_prompt.md")
        prompt_config.recent_events_limit = prompt_dict.get("recent_events_limit", 10)
        prompt_config.recent_interventions_limit = prompt_dict.get("recent_interventions_limit", 5)

    # Parse strategies
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

    # Parse effectiveness config
    effectiveness_config = DirectorEffectivenessConfig()
    if "effectiveness" in config_dict:
        eff_dict = config_dict["effectiveness"]
        effectiveness_config.evaluation_delay_ticks = eff_dict.get("evaluation_delay_ticks", 5)
        effectiveness_config.metrics = eff_dict.get("metrics", {})

    # Parse scene goals
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
