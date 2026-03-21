"""Models for world design runtime assets."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


RuleDecision = Literal["allowed", "violates_rule", "impossible", "soft_risk"]


class RuleTriggerConfig(BaseModel):
    action_types: list[str] = Field(default_factory=list)


class RuleConditionConfig(BaseModel):
    fact: str
    op: str
    value: Any | None = None
    value_from: str | None = None


class RuleOutcomeConfig(BaseModel):
    decision: RuleDecision
    reason: str | None = None
    risk_level: str | None = None
    tags: list[str] = Field(default_factory=list)


class RuleConfigItem(BaseModel):
    rule_id: str
    name: str
    description: str = ""
    trigger: RuleTriggerConfig = Field(default_factory=RuleTriggerConfig)
    conditions: list[RuleConditionConfig] = Field(default_factory=list)
    outcome: RuleOutcomeConfig
    priority: int = 0
    scope: str | None = None
    explanation_key: str | None = None
    tags: list[str] = Field(default_factory=list)


class RulesConfig(BaseModel):
    version: int = 1
    rules: list[RuleConfigItem] = Field(default_factory=list)


class PolicyConfig(BaseModel):
    version: int = 1
    policy_id: str = "default"
    name: str = "Default Governance Policy"
    description: str = ""
    values: dict[str, Any] = Field(default_factory=dict)


class WorldDesignRuntimePackage(BaseModel):
    scenario_id: str
    world_config: dict[str, Any] = Field(default_factory=dict)
    rules_config: RulesConfig = Field(default_factory=RulesConfig)
    policy_config: PolicyConfig = Field(default_factory=PolicyConfig)
    constitution_text: str = ""
    facts_schema_version: int = 1
    rule_schema_version: int = 1
    policy_schema_version: int = 1
