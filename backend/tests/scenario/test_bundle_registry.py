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
    resolve_visual_asset_id_for_scenario,
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
                "adapter: bundle_world",
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
                "adapter: bundle_world",
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
                "adapter: bundle_world",
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


def test_bundle_registry_loads_module_selection_from_manifest(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    bundle_root = scenarios_root / "hero_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: hero_world",
                "name: Hero World",
                "version: 1",
                "adapter: bundle_world",
                "modules:",
                "  fallback_policy: social_default",
                "  seed_policy: standard_bundle_seed",
                "  state_update_policy: alert_tracking",
            ]
        ),
        encoding="utf-8",
    )

    bundle = ScenarioBundleRegistry(scenarios_root).get_bundle("hero_world")

    assert bundle is not None
    assert bundle.modules.fallback_policy == "social_default"
    assert bundle.modules.seed_policy == "standard_bundle_seed"
    assert bundle.modules.state_update_policy == "alert_tracking"


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


@pytest.mark.parametrize(
    "removed_line",
    ["runtime_adapter: bundle_world", "capabilities:\n  alert_tracking: true"],
)
def test_bundle_registry_rejects_removed_manifest_fields(tmp_path, removed_line):
    scenario_root = tmp_path / "scenarios" / "invalid_world"
    scenario_root.mkdir(parents=True)
    (scenario_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: invalid_world",
                "name: Invalid World",
                "version: 1",
                "adapter: bundle_world",
                removed_line,
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid scenario manifest"):
        ScenarioBundleRegistry(tmp_path / "scenarios").get_bundle("invalid_world")


def test_bundle_registry_prefers_narrative_world_as_default_when_present(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    for scenario_id, adapter in (
        ("open_world", "open_world"),
        ("narrative_world", "bundle_world"),
    ):
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


def test_bundle_registry_prefers_manifest_default_flag_over_conventional_default(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    for scenario_id, adapter, is_default in (
        ("narrative_world", "bundle_world", False),
        ("hero_world", "bundle_world", True),
    ):
        bundle_root = scenarios_root / scenario_id
        bundle_root.mkdir(parents=True)
        manifest_lines = [
            f"id: {scenario_id}",
            f"name: {scenario_id}",
            "version: 1",
            f"adapter: {adapter}",
        ]
        if is_default:
            manifest_lines.append("default: true")
        (bundle_root / "scenario.yml").write_text(
            "\n".join(manifest_lines),
            encoding="utf-8",
        )

    registry = ScenarioBundleRegistry(scenarios_root)

    assert registry.get_default_scenario_id() == "hero_world"


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


def test_resolve_default_scenario_id_uses_manifest_default_flag(tmp_path, monkeypatch):
    scenarios_root = tmp_path / "scenarios"
    for scenario_id, is_default in (("alpha_world", False), ("beta_world", True)):
        bundle_root = scenarios_root / scenario_id
        bundle_root.mkdir(parents=True)
        manifest_lines = [
            f"id: {scenario_id}",
            f"name: {scenario_id}",
            "version: 1",
            "adapter: bundle_world",
        ]
        if is_default:
            manifest_lines.append("default: true")
        (bundle_root / "scenario.yml").write_text(
            "\n".join(manifest_lines),
            encoding="utf-8",
        )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    assert resolve_default_scenario_id() == "beta_world"


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
                "adapter: bundle_world",
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
                "adapter: bundle_world",
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


def test_visual_asset_id_requires_scenario_owned_appearance(tmp_path, monkeypatch):
    bundle_root = tmp_path / "scenarios" / "narrative_world"
    agent_root = bundle_root / "agents" / "truman"
    agent_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "id: narrative_world\nname: Narrative World\nversion: 1\nadapter: bundle_world\n",
        encoding="utf-8",
    )
    (agent_root / "appearance.yml").write_text("schema_version: 1\n", encoding="utf-8")
    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    assert (
        resolve_visual_asset_id_for_scenario("narrative_world", "truman")
        == "narrative_world/truman"
    )
    assert resolve_visual_asset_id_for_scenario("narrative_world", "missing") is None
    assert resolve_visual_asset_id_for_scenario("missing", "truman") is None


def test_load_world_config_for_scenario_reads_bundle_world_file(tmp_path, monkeypatch):
    bundle_root = tmp_path / "scenarios" / "narrative_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: narrative_world",
                "name: Narrative World",
                "version: 1",
                "adapter: bundle_world",
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
                "adapter: bundle_world",
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
                "adapter: bundle_world",
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
                "adapter: bundle_world",
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
                "adapter: bundle_world",
            ]
        ),
        encoding="utf-8",
    )

    registry = ScenarioBundleRegistry(scenarios_root)

    with pytest.raises(ValueError, match="Invalid scenario manifest"):
        registry.list_bundles()
