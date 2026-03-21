from __future__ import annotations

import pytest

from app.infra.settings import get_settings


def test_runtime_world_design_package_loads_bundle_assets(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    bundle_root = tmp_path / "scenarios" / "hero_world"
    policies_root = bundle_root / "policies"
    policies_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: hero_world",
                "name: Hero World",
                "version: 1",
                "runtime_adapter: narrative_world",
                "default: true",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "world.yml").write_text(
        "\n".join(
            [
                "daily_rhythm:",
                "  lunch_time: 12:00-13:00",
                "social_norms:",
                "  - stay calm",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "rules.yml").write_text(
        "\n".join(
            [
                "version: 1",
                "rules:",
                "  - rule_id: plaza_access",
                "    name: Plaza Access",
                "    description: Plaza is accessible",
                "    trigger:",
                "      action_types:",
                "        - move",
                "    conditions: []",
                "    outcome:",
                "      decision: allowed",
                "    priority: 10",
            ]
        ),
        encoding="utf-8",
    )
    (policies_root / "default.yml").write_text(
        "\n".join(
            [
                "version: 1",
                "policy_id: default",
                "name: Default Policy",
                "values:",
                "  inspection_level: medium",
                "  closed_locations:",
                "    - plaza",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "constitution.md").write_text(
        "Residents should preserve daily continuity.",
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    from app.scenario.runtime.world_design import load_world_design_runtime_package

    package = load_world_design_runtime_package("hero_world", force_reload=True)

    assert package.scenario_id == "hero_world"
    assert package.world_config["daily_rhythm"]["lunch_time"] == "12:00-13:00"
    assert package.rules_config.version == 1
    assert len(package.rules_config.rules) == 1
    assert package.rules_config.rules[0].rule_id == "plaza_access"
    assert package.policy_config.policy_id == "default"
    assert package.policy_config.values["inspection_level"] == "medium"
    assert package.constitution_text == "Residents should preserve daily continuity."


def test_runtime_world_design_package_uses_empty_rules_and_default_policy_when_assets_missing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    bundle_root = tmp_path / "scenarios" / "hero_world"
    bundle_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: hero_world",
                "name: Hero World",
                "version: 1",
                "runtime_adapter: narrative_world",
                "default: true",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "world.yml").write_text("social_norms:\n  - stay calm\n", encoding="utf-8")

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    from app.scenario.runtime.world_design import load_world_design_runtime_package

    package = load_world_design_runtime_package("hero_world", force_reload=True)

    assert package.rules_config.version == 1
    assert package.rules_config.rules == []
    assert package.policy_config.version == 1
    assert package.policy_config.policy_id == "default"
    assert package.policy_config.values["inspection_level"] == "low"
    assert package.policy_config.values["closed_locations"] == []
    assert package.constitution_text == ""


def test_runtime_world_design_package_falls_back_to_default_bundle_world_only(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    default_root = tmp_path / "scenarios" / "hero_world"
    default_policies_root = default_root / "policies"
    default_policies_root.mkdir(parents=True)
    (default_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: hero_world",
                "name: Hero World",
                "version: 1",
                "runtime_adapter: narrative_world",
                "default: true",
            ]
        ),
        encoding="utf-8",
    )
    (default_root / "world.yml").write_text(
        "social_norms:\n  - follow the default rhythm\n",
        encoding="utf-8",
    )
    (default_root / "rules.yml").write_text(
        "\n".join(
            [
                "version: 1",
                "rules:",
                "  - rule_id: default_rule",
                "    name: Default Rule",
                "    description: Default rule",
                "    trigger:",
                "      action_types:",
                "        - rest",
                "    conditions: []",
                "    outcome:",
                "      decision: allowed",
                "    priority: 1",
            ]
        ),
        encoding="utf-8",
    )
    (default_policies_root / "default.yml").write_text(
        "\n".join(
            [
                "version: 1",
                "policy_id: default",
                "name: Default Policy",
                "values:",
                "  inspection_level: high",
            ]
        ),
        encoding="utf-8",
    )
    (default_root / "constitution.md").write_text(
        "Default constitution text.",
        encoding="utf-8",
    )

    other_root = tmp_path / "scenarios" / "mystery_world"
    other_root.mkdir(parents=True)
    (other_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: mystery_world",
                "name: Mystery World",
                "version: 1",
                "runtime_adapter: narrative_world",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    from app.scenario.runtime.world_design import load_world_design_runtime_package

    package = load_world_design_runtime_package("mystery_world", force_reload=True)

    assert package.world_config["social_norms"] == ["follow the default rhythm"]
    assert package.rules_config.rules == []
    assert package.policy_config.values["inspection_level"] == "low"
    assert package.constitution_text == ""


def test_runtime_world_design_cache_is_isolated_by_project_root(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    root_a = tmp_path / "proj_a"
    bundle_a = root_a / "scenarios" / "hero_world"
    policies_a = bundle_a / "policies"
    policies_a.mkdir(parents=True)
    (bundle_a / "scenario.yml").write_text(
        "\n".join(
            [
                "id: hero_world",
                "name: Hero World",
                "version: 1",
                "runtime_adapter: narrative_world",
                "default: true",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_a / "world.yml").write_text("social_norms:\n  - root a\n", encoding="utf-8")
    (policies_a / "default.yml").write_text(
        "version: 1\npolicy_id: default\nvalues:\n  inspection_level: medium\n",
        encoding="utf-8",
    )

    root_b = tmp_path / "proj_b"
    bundle_b = root_b / "scenarios" / "hero_world"
    policies_b = bundle_b / "policies"
    policies_b.mkdir(parents=True)
    (bundle_b / "scenario.yml").write_text(
        "\n".join(
            [
                "id: hero_world",
                "name: Hero World",
                "version: 1",
                "runtime_adapter: narrative_world",
                "default: true",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_b / "world.yml").write_text("social_norms:\n  - root b\n", encoding="utf-8")
    (policies_b / "default.yml").write_text(
        "version: 1\npolicy_id: default\nvalues:\n  inspection_level: high\n",
        encoding="utf-8",
    )

    from app.scenario.runtime.world_design import load_world_design_runtime_package

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(root_a))
    get_settings.cache_clear()
    package_a = load_world_design_runtime_package("hero_world", force_reload=True)

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(root_b))
    get_settings.cache_clear()
    package_b = load_world_design_runtime_package("hero_world")

    assert package_a.world_config["social_norms"] == ["root a"]
    assert package_a.policy_config.values["inspection_level"] == "medium"
    assert package_b.world_config["social_norms"] == ["root b"]
    assert package_b.policy_config.values["inspection_level"] == "high"
