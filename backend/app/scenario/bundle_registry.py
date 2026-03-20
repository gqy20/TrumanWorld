from __future__ import annotations

from pathlib import Path

import yaml

from app.infra.settings import get_settings
from app.scenario.bundle_models import (
    ScenarioBundle,
    ScenarioCapabilities,
    ScenarioManifest,
    ScenarioSemantics,
)


class ScenarioBundleRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list_bundles(self) -> list[ScenarioBundle]:
        if not self.root.exists():
            return []

        bundles: list[ScenarioBundle] = []
        for bundle_root in sorted(path for path in self.root.iterdir() if path.is_dir()):
            manifest_path = bundle_root / "scenario.yml"
            if not manifest_path.exists():
                continue
            bundles.append(self._load_bundle(manifest_path))
        return bundles

    def get_bundle(self, scenario_id: str | None) -> ScenarioBundle | None:
        if not scenario_id:
            return None
        for bundle in self.list_bundles():
            if bundle.manifest.id == scenario_id:
                return bundle
        return None

    def get_default_scenario_id(self) -> str:
        bundles = self.list_bundles()
        if not bundles:
            return "truman_world"
        preferred = next((bundle for bundle in bundles if bundle.manifest.id == "truman_world"), None)
        return preferred.manifest.id if preferred is not None else bundles[0].manifest.id

    def _load_bundle(self, manifest_path: Path) -> ScenarioBundle:
        with manifest_path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}

        try:
            manifest = ScenarioManifest.model_validate(raw)
            semantics = ScenarioSemantics.model_validate(raw.get("semantics", {}))
            capabilities = ScenarioCapabilities.model_validate(raw.get("capabilities", {}))
        except Exception as exc:
            msg = f"Invalid scenario manifest: {manifest_path}"
            raise ValueError(msg) from exc

        return ScenarioBundle(
            manifest=manifest,
            semantics=semantics,
            capabilities=capabilities,
            root=manifest_path.parent,
            manifest_path=manifest_path,
        )

    def load_bundle_yaml(self, scenario_id: str | None, filename: str) -> dict:
        bundle = self.get_bundle(scenario_id)
        if bundle is None:
            return {}
        path = bundle.root / filename
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}
        return raw if isinstance(raw, dict) else {}


def get_scenario_bundle_registry() -> ScenarioBundleRegistry:
    settings = get_settings()
    return ScenarioBundleRegistry(settings.project_root / "scenarios")


def resolve_default_scenario_id(
    *,
    project_root: Path | None = None,
) -> str:
    settings = get_settings()
    base_root = project_root or settings.project_root
    registry = ScenarioBundleRegistry(base_root / "scenarios")
    return registry.get_default_scenario_id()


def get_scenario_bundle(
    scenario_id: str | None,
    *,
    project_root: Path | None = None,
) -> ScenarioBundle | None:
    settings = get_settings()
    base_root = project_root or settings.project_root
    registry = ScenarioBundleRegistry(base_root / "scenarios")
    return registry.get_bundle(scenario_id)


def resolve_agents_root_for_scenario(
    scenario_id: str | None,
    *,
    project_root: Path | None = None,
) -> Path:
    settings = get_settings()
    base_root = project_root or settings.project_root
    registry = ScenarioBundleRegistry(base_root / "scenarios")
    bundle = registry.get_bundle(scenario_id)
    if bundle is not None and bundle.agents_root.exists():
        return bundle.agents_root
    return base_root / "agents"


def load_world_config_for_scenario(
    scenario_id: str | None,
    *,
    project_root: Path | None = None,
) -> dict:
    settings = get_settings()
    base_root = project_root or settings.project_root
    registry = ScenarioBundleRegistry(base_root / "scenarios")
    return registry.load_bundle_yaml(scenario_id, "world.yml")


def load_director_config_dict_for_scenario(
    scenario_id: str | None,
    *,
    project_root: Path | None = None,
) -> dict:
    settings = get_settings()
    base_root = project_root or settings.project_root
    registry = ScenarioBundleRegistry(base_root / "scenarios")
    return registry.load_bundle_yaml(scenario_id, "director.yml")


def load_director_prompt_template_for_scenario(
    scenario_id: str | None,
    filename: str,
    *,
    project_root: Path | None = None,
) -> str | None:
    settings = get_settings()
    base_root = project_root or settings.project_root
    registry = ScenarioBundleRegistry(base_root / "scenarios")
    bundle = registry.get_bundle(scenario_id)
    if bundle is None:
        return None
    path = bundle.root / filename
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def load_ui_config_for_scenario(
    scenario_id: str | None,
    *,
    project_root: Path | None = None,
) -> dict:
    settings = get_settings()
    base_root = project_root or settings.project_root
    registry = ScenarioBundleRegistry(base_root / "scenarios")
    return registry.load_bundle_yaml(scenario_id, "ui.yml")


def resolve_sleep_config_for_scenario(
    scenario_id: str | None,
    *,
    project_root: Path | None = None,
) -> dict:
    world_cfg = load_world_config_for_scenario(scenario_id, project_root=project_root)
    sleep = world_cfg.get("daily_rhythm", {}).get("sleep_hours", {})
    result = {}
    if "start" in sleep:
        result["sleep_start_hour"] = int(sleep["start"])
    if "end" in sleep:
        result["sleep_end_hour"] = int(sleep["end"])
    return result
