from __future__ import annotations

import pytest

from app.infra.settings import get_settings
from app.scenario.bundle_registry import (
    ScenarioBundleRegistry,
    load_director_config_dict_for_scenario,
    load_director_prompt_template_for_scenario,
    load_ui_config_for_scenario,
    load_world_config_for_scenario,
    resolve_default_scenario_id,
    resolve_agents_root_for_scenario,
    resolve_sleep_config_for_scenario,
)


def test_bundle_registry_loads_scenarios_from_directory(tmp_path):
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

    open_world_root = scenarios_root / "open_world"
    open_world_root.mkdir(parents=True)
    (open_world_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: open_world",
                "name: Open World",
                "version: 1",
                "runtime_adapter: open_world",
            ]
        ),
        encoding="utf-8",
    )

    registry = ScenarioBundleRegistry(scenarios_root)

    bundles = registry.list_bundles()

    assert [bundle.manifest.id for bundle in bundles] == ["narrative_world", "open_world"]
    assert bundles[0].root == truman_root
    assert bundles[1].root == open_world_root


def test_bundle_registry_returns_bundle_by_id(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    bundle_root = scenarios_root / "narrative_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
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

    registry = ScenarioBundleRegistry(scenarios_root)
    bundle = registry.get_bundle("narrative_world")

    assert bundle is not None
    assert bundle.manifest.name == "Narrative World"


def test_bundle_registry_loads_scenario_semantics_and_capabilities(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    bundle_root = scenarios_root / "hero_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: hero_world",
                "name: Hero World",
                "version: 1",
                "adapter: narrative_world",
                "semantics:",
                "  subject_role: protagonist",
                "  support_roles:",
                "    - cast",
                "    - ally",
                "  alert_metric: anomaly_score",
                "capabilities:",
                "  director: true",
                "  subject_alert_tracking: false",
                "  scene_guidance: true",
            ]
        ),
        encoding="utf-8",
    )

    bundle = ScenarioBundleRegistry(scenarios_root).get_bundle("hero_world")

    assert bundle is not None
    assert bundle.semantics.subject_role == "protagonist"
    assert bundle.semantics.support_roles == ["cast", "ally"]
    assert bundle.semantics.alert_metric == "anomaly_score"
    assert bundle.capabilities.director is True
    assert bundle.capabilities.subject_alert_tracking is False
    assert bundle.capabilities.scene_guidance is True


def test_bundle_registry_uses_empty_defaults_when_semantics_and_capabilities_missing(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    bundle_root = scenarios_root / "open_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
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

    bundle = ScenarioBundleRegistry(scenarios_root).get_bundle("open_world")

    assert bundle is not None
    assert bundle.semantics.subject_role is None
    assert bundle.semantics.support_roles == []
    assert bundle.semantics.alert_metric is None
    assert bundle.capabilities.director is None
    assert bundle.capabilities.subject_alert_tracking is None
    assert bundle.capabilities.scene_guidance is None


def test_bundle_registry_prefers_narrative_world_as_default_when_present(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    for scenario_id, adapter in (("open_world", "open_world"), ("narrative_world", "narrative_world")):
        bundle_root = scenarios_root / scenario_id
        bundle_root.mkdir(parents=True)
        (bundle_root / "scenario.yml").write_text(
            "\n".join(
                [
                    f"id: {scenario_id}",
                    f"name: {scenario_id}",
                    "version: 1",
                    f"adapter: {adapter}",
                ]
            ),
            encoding="utf-8",
        )

    registry = ScenarioBundleRegistry(scenarios_root)

    assert registry.get_default_scenario_id() == "narrative_world"


def test_resolve_default_scenario_id_uses_first_bundle_when_truman_missing(tmp_path, monkeypatch):
    scenarios_root = tmp_path / "scenarios"
    for scenario_id in ("alpha_world", "open_world"):
        bundle_root = scenarios_root / scenario_id
        bundle_root.mkdir(parents=True)
        (bundle_root / "scenario.yml").write_text(
            "\n".join(
                [
                    f"id: {scenario_id}",
                    f"name: {scenario_id}",
                    "version: 1",
                    "adapter: open_world",
                ]
            ),
            encoding="utf-8",
        )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    assert resolve_default_scenario_id() == "alpha_world"


def test_bundle_registry_normalizes_legacy_alert_tracking_capability(tmp_path):
    scenario_root = tmp_path / "scenarios" / "legacy_alert_world"
    scenario_root.mkdir(parents=True)
    (scenario_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: legacy_alert_world",
                "name: Legacy Alert World",
                "version: 1",
                "adapter: narrative_world",
                "capabilities:",
                "  alert_tracking: false",
            ]
        ),
        encoding="utf-8",
    )

    registry = ScenarioBundleRegistry(tmp_path / "scenarios")

    bundle = registry.get_bundle("legacy_alert_world")

    assert bundle is not None
    assert bundle.capabilities.subject_alert_tracking is False


def test_bundle_registry_prefers_bundle_agents_directory(tmp_path, monkeypatch):
    scenarios_root = tmp_path / "scenarios"
    bundle_root = scenarios_root / "narrative_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
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
    agents_root = bundle_root / "agents"
    agents_root.mkdir()

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    registry = ScenarioBundleRegistry(scenarios_root)
    bundle = registry.get_bundle("narrative_world")

    assert bundle is not None
    assert bundle.agents_root == agents_root


def test_resolve_agents_root_falls_back_to_project_agents_when_bundle_agents_missing(
    tmp_path, monkeypatch
):
    scenarios_root = tmp_path / "scenarios"
    bundle_root = scenarios_root / "narrative_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
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
    project_agents_root = tmp_path / "agents"
    project_agents_root.mkdir()

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    resolved = resolve_agents_root_for_scenario("narrative_world")

    assert resolved == project_agents_root


def test_load_world_config_for_scenario_reads_bundle_world_file(tmp_path, monkeypatch):
    bundle_root = tmp_path / "scenarios" / "narrative_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
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
    (bundle_root / "world.yml").write_text(
        "\n".join(
            [
                "daily_rhythm:",
                "  sleep_hours:",
                "    start: 22",
                "    end: 7",
                "health_metrics:",
                "  continuity:",
                "    penalty_factor: 150",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    world_config = load_world_config_for_scenario("narrative_world")

    assert world_config["daily_rhythm"]["sleep_hours"]["start"] == 22
    assert world_config["health_metrics"]["continuity"]["penalty_factor"] == 150


def test_resolve_sleep_config_for_scenario_reads_bundle_world_file(tmp_path, monkeypatch):
    bundle_root = tmp_path / "scenarios" / "narrative_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
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
    (bundle_root / "world.yml").write_text(
        "\n".join(
            [
                "daily_rhythm:",
                "  sleep_hours:",
                "    start: 21",
                "    end: 8",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    sleep_config = resolve_sleep_config_for_scenario("narrative_world")

    assert sleep_config == {"sleep_start_hour": 21, "sleep_end_hour": 8}


def test_load_director_config_and_prompt_for_scenario_reads_bundle_files(tmp_path, monkeypatch):
    bundle_root = tmp_path / "scenarios" / "narrative_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
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
    (bundle_root / "director.yml").write_text(
        "\n".join(
            [
                "enabled: true",
                "decision_interval: 9",
                "prompt:",
                "  file: director_prompt.md",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "director_prompt.md").write_text(
        "Director prompt from scenario bundle",
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    director_config = load_director_config_dict_for_scenario("narrative_world")
    prompt_template = load_director_prompt_template_for_scenario(
        "narrative_world", "director_prompt.md"
    )

    assert director_config["decision_interval"] == 9
    assert prompt_template == "Director prompt from scenario bundle"


def test_load_ui_config_for_scenario_reads_bundle_ui_file(tmp_path, monkeypatch):
    bundle_root = tmp_path / "scenarios" / "narrative_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
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
    (bundle_root / "ui.yml").write_text(
        "\n".join(
            [
                "location_detail:",
                "  max_events_display: 42",
                "intelligence_stream:",
                "  poll_interval_ms: 1234",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    ui_config = load_ui_config_for_scenario("narrative_world")

    assert ui_config["location_detail"]["max_events_display"] == 42
    assert ui_config["intelligence_stream"]["poll_interval_ms"] == 1234


def test_bundle_registry_rejects_invalid_manifest(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    invalid_root = scenarios_root / "broken"
    invalid_root.mkdir(parents=True)
    (invalid_root / "scenario.yml").write_text(
        "\n".join(
            [
                "name: Missing Id",
                "version: 1",
                "runtime_adapter: narrative_world",
            ]
        ),
        encoding="utf-8",
    )

    registry = ScenarioBundleRegistry(scenarios_root)

    with pytest.raises(ValueError, match="Invalid scenario manifest"):
        registry.list_bundles()
