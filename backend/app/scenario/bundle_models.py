from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScenarioManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    adapter: str = Field(min_length=1)
    default: bool = False

    @model_validator(mode="before")
    @classmethod
    def _normalize_adapter_alias(cls, data):
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        adapter = normalized.get("adapter")
        legacy_runtime_adapter = normalized.get("runtime_adapter")
        if not isinstance(adapter, str) or not adapter:
            if isinstance(legacy_runtime_adapter, str) and legacy_runtime_adapter:
                normalized["adapter"] = legacy_runtime_adapter
        return normalized


class ScenarioSemantics(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject_role: str | None = None
    support_roles: list[str] = Field(default_factory=list)
    alert_metric: str | None = None


class ScenarioCapabilities(BaseModel):
    model_config = ConfigDict(extra="ignore")

    director: bool | None = None
    subject_alert_tracking: bool | None = None
    scene_guidance: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_subject_alert_tracking_alias(cls, data):
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        subject_alert_tracking = normalized.get("subject_alert_tracking")
        legacy_alert_tracking = normalized.get("alert_tracking")
        if subject_alert_tracking is None and legacy_alert_tracking is not None:
            normalized["subject_alert_tracking"] = legacy_alert_tracking
        return normalized


class ScenarioModules(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fallback_policy: str | None = None
    seed_policy: str | None = None
    state_update_policy: str | None = None
    director_policy: str | None = None
    agent_context_policy: str | None = None
    allowed_actions_policy: str | None = None
    profile_merge_policy: str | None = None


class ScenarioBundle(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    manifest: ScenarioManifest
    semantics: ScenarioSemantics = Field(default_factory=ScenarioSemantics)
    capabilities: ScenarioCapabilities = Field(default_factory=ScenarioCapabilities)
    modules: ScenarioModules = Field(default_factory=ScenarioModules)
    root: Path
    manifest_path: Path

    @property
    def agents_root(self) -> Path:
        return self.root / "agents"
