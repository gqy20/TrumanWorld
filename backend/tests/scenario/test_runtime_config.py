from app.scenario.runtime_config import build_scenario_runtime_config


def test_build_scenario_runtime_config_uses_defaults_when_bundle_missing(monkeypatch):
    monkeypatch.delenv("TRUMANWORLD_PROJECT_ROOT", raising=False)

    config = build_scenario_runtime_config("missing_world")

    assert config.subject_role == "truman"
    assert config.support_roles == ["cast"]
    assert config.alert_metric == "suspicion_score"
    assert config.subject_alert_tracking is True


def test_build_scenario_runtime_config_reads_bundle_semantics_and_capabilities(
    tmp_path, monkeypatch
):
    scenario_root = tmp_path / "scenarios" / "alt_world"
    scenario_root.mkdir(parents=True)
    (scenario_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: alt_world",
                "name: Alt World",
                "version: 1",
                "adapter: truman_world",
                "semantics:",
                "  subject_role: protagonist",
                "  support_roles:",
                "    - ally",
                "  alert_metric: anomaly_score",
                "capabilities:",
                "  subject_alert_tracking: false",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))

    config = build_scenario_runtime_config("alt_world")

    assert config.subject_role == "protagonist"
    assert config.support_roles == ["ally"]
    assert config.alert_metric == "anomaly_score"
    assert config.subject_alert_tracking is False
