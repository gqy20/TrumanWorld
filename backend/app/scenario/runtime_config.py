from __future__ import annotations

from dataclasses import dataclass, field

from app.scenario.bundle_registry import get_scenario_bundle


@dataclass
class ScenarioRuntimeConfig:
    subject_role: str = "truman"
    support_roles: list[str] = field(default_factory=lambda: ["cast"])
    alert_metric: str = "suspicion_score"
    subject_alert_tracking: bool = True

    def support_role_set(self) -> set[str]:
        return set(self.support_roles)


def build_scenario_runtime_config(scenario_id: str) -> ScenarioRuntimeConfig:
    bundle = get_scenario_bundle(scenario_id)
    semantics = bundle.semantics if bundle is not None else None
    capabilities = bundle.capabilities if bundle is not None else None
    return ScenarioRuntimeConfig(
        subject_role=semantics.subject_role or "truman" if semantics else "truman",
        support_roles=semantics.support_roles or ["cast"] if semantics else ["cast"],
        alert_metric=(
            semantics.alert_metric or "suspicion_score" if semantics else "suspicion_score"
        ),
        subject_alert_tracking=(
            capabilities.subject_alert_tracking
            if capabilities is not None and capabilities.subject_alert_tracking is not None
            else True
        ),
    )
