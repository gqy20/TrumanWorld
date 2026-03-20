from __future__ import annotations

import pytest

from app.infra.settings import get_settings
from app.scenario.adapter_registry import ScenarioAdapterRegistry
from app.scenario.factory import create_scenario
from app.scenario.open_world.scenario import OpenWorldScenario
from app.scenario.narrative_world.scenario import NarrativeWorldScenario


def test_factory_resolves_runtime_adapter_from_bundle_registry(tmp_path, monkeypatch: pytest.MonkeyPatch):
    scenarios_root = tmp_path / "scenarios"
    truman_root = scenarios_root / "narrative_world"
    truman_root.mkdir(parents=True)
    (truman_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: narrative_world",
                "name: Narrative World",
                "version: 1",
                "adapter: narrative_world",
            ]
        ),
        encoding="utf-8",
    )
    open_world_root = scenarios_root / "open_world"
    open_world_root.mkdir(parents=True)
    (open_world_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: open_world",
                "name: Open World",
                "version: 1",
                "adapter: open_world",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    open_world = create_scenario("open_world")
    narrative_world = create_scenario("narrative_world")

    assert isinstance(open_world, OpenWorldScenario)
    assert isinstance(narrative_world, NarrativeWorldScenario)


def test_factory_falls_back_to_default_scenario_when_bundle_missing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    scenarios_root = tmp_path / "scenarios"
    truman_root = scenarios_root / "narrative_world"
    truman_root.mkdir(parents=True)
    (truman_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: narrative_world",
                "name: Narrative World",
                "version: 1",
                "adapter: narrative_world",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    scenario = create_scenario("unknown_world")

    assert isinstance(scenario, NarrativeWorldScenario)


def test_factory_supports_legacy_runtime_adapter_alias(tmp_path, monkeypatch: pytest.MonkeyPatch):
    scenarios_root = tmp_path / "scenarios"
    truman_root = scenarios_root / "narrative_world"
    truman_root.mkdir(parents=True)
    (truman_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: narrative_world",
                "name: Narrative World",
                "version: 1",
                "runtime_adapter: narrative_world",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    scenario = create_scenario("narrative_world")

    assert isinstance(scenario, NarrativeWorldScenario)


def test_adapter_registry_builds_registered_adapter():
    registry = ScenarioAdapterRegistry()

    registry.register(
        "custom_world",
        lambda scenario_id, session: NarrativeWorldScenario(session, scenario_id=scenario_id),
    )

    scenario = registry.build("custom_world", scenario_id="custom_world")

    assert isinstance(scenario, NarrativeWorldScenario)
    assert scenario.scenario_id == "custom_world"


def test_adapter_registry_raises_clear_error_for_unknown_adapter():
    registry = ScenarioAdapterRegistry()

    with pytest.raises(ValueError, match="Unknown scenario adapter: missing_adapter"):
        registry.build("missing_adapter", scenario_id="unknown_world")


def test_factory_raises_clear_error_for_unknown_manifest_adapter(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    scenarios_root = tmp_path / "scenarios"
    bundle_root = scenarios_root / "unknown_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: unknown_world",
                "name: Unknown World",
                "version: 1",
                "adapter: missing_adapter",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Unknown scenario adapter: missing_adapter"):
        create_scenario("unknown_world")
