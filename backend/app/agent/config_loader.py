from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentCapabilities(BaseModel):
    reflection: bool = True
    dialogue: bool = True
    mcp: bool = False
    subagents: bool = False


class WorkSchedule(BaseModel):
    """工作日程配置"""

    start_hour: int | None = None
    end_hour: int | None = None
    work_days: list[str] | None = None
    type: str | None = None  # 如 "shift" 表示轮班
    shifts: list[str] | None = None


class AgentModelConfig(BaseModel):
    max_turns: int = 8
    max_budget_usd: float = 1.0


# =============================================================================
# 新增配置模型：关系、初始状态、初始计划
# =============================================================================


class RelationConfig(BaseModel):
    """单个关系配置 - 从当前 agent 视角看另一个 agent"""

    familiarity: float = Field(default=0.5, ge=0.0, le=1.0)
    trust: float = Field(default=0.5, ge=0.0, le=1.0)
    affinity: float = Field(default=0.5, ge=0.0, le=1.0)
    relation_type: str = "acquaintance"


class InitialStatusConfig(BaseModel):
    """初始状态配置"""

    model_config = ConfigDict(extra="allow")

    energy: float = Field(default=0.75, ge=0.0, le=1.0)
    alert_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def reject_removed_alert_field(cls, data: object) -> object:
        if isinstance(data, dict) and "suspicion_score" in data:
            raise ValueError("status.suspicion_score was removed; use status.alert_score")
        return data


class InitialPlanConfig(BaseModel):
    """初始日计划配置"""

    model_config = ConfigDict(extra="allow")

    morning: str = "work"
    daytime: str = "work"
    evening: str = "rest"


class InitialSpawnConfig(BaseModel):
    """通用初始生成配置"""

    location: str | None = None
    goal: str | None = None


class AgentInitialConfig(BaseModel):
    """initial.yml 的完整结构"""

    model_config = ConfigDict(extra="forbid")

    status: InitialStatusConfig = Field(default_factory=InitialStatusConfig)
    plan: InitialPlanConfig = Field(default_factory=InitialPlanConfig)
    spawn: InitialSpawnConfig = Field(default_factory=InitialSpawnConfig)


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    world_role: str = "cast"  # scenario-defined role; not restricted to a fixed enum
    occupation: str = "resident"
    workplace: str | None = None
    work_schedule: WorkSchedule | None = None
    work_description: str | None = None  # inline work description (replaces WORK_DESCRIPTIONS dict)
    home: str
    personality: dict = Field(default_factory=dict)
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    model: AgentModelConfig = Field(default_factory=AgentModelConfig)
    root_dir: Path | None = None

    @property
    def prompt_path(self) -> Path:
        if self.root_dir is None:
            msg = "Agent root_dir is not set"
            raise ValueError(msg)
        return self.root_dir / "prompt.md"

    @property
    def logo_path(self) -> Path | None:
        """Return the path to the agent's logo SVG file, if it exists."""
        if self.root_dir is None:
            return None
        logo = self.root_dir / "logo.svg"
        return logo if logo.exists() else None

    @property
    def logo_url(self) -> str | None:
        """Return the URL path to the agent's logo for frontend use."""
        # Logo files are served from /agents/{agent_id}.svg
        return f"/agents/{self.id}.svg"


class AgentConfigLoader:
    """Parses agent.yml files into runtime configuration."""

    def load(self, path: Path) -> AgentConfig:
        with path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}

        config = AgentConfig.model_validate(raw)
        config.root_dir = path.parent
        return config


class RelationsLoader:
    """Parses relations.yml files into relation configuration."""

    def load(self, path: Path) -> dict[str, RelationConfig]:
        """Load relations from relations.yml file.

        Returns a dict mapping other_agent_id -> RelationConfig
        """
        if not path.exists():
            return {}

        with path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}

        relations: dict[str, RelationConfig] = {}
        for other_id, attrs in raw.items():
            if isinstance(attrs, dict):
                relations[other_id] = RelationConfig.model_validate(attrs)
            else:
                relations[other_id] = RelationConfig()
        return relations


class InitialConfigLoader:
    """Parses initial.yml files into initial state configuration."""

    def load(self, path: Path) -> AgentInitialConfig:
        """Load initial config from initial.yml file."""
        if not path.exists():
            return AgentInitialConfig()

        with path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}

        return AgentInitialConfig.model_validate(raw)
