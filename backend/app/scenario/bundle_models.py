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
    def reject_removed_adapter_field(cls, data: object) -> object:
        if isinstance(data, dict) and "runtime_adapter" in data:
            raise ValueError("runtime_adapter was removed; use adapter")
        return data


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
    def reject_removed_alert_tracking_field(cls, data: object) -> object:
        if isinstance(data, dict) and "alert_tracking" in data:
            raise ValueError("alert_tracking was removed; use subject_alert_tracking")
        return data


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
