"""Director system types and data classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.director.directives import DirectorDirective


@dataclass(init=False)
class DirectorPlan:
    """Director intervention plan."""

    scene_goal: str
    target_agent_ids: list[str]
    priority: str
    message_hint: str | None = None
    location_hint: str | None = None
    target_agent_id: str | None = None
    reason: str | None = None
    # 新增字段
    urgency: str = "advisory"  # "advisory" | "immediate" | "emergency"
    cooldown_ticks: int = 3  # 建议的冷却时间
    # 智能决策标记
    is_intelligent_decision: bool = False  # 是否由LLM智能决策生成
    strategy: str | None = None  # 干预策略描述
    source_type: str = "auto"  # "auto" | "manual"
    source_memory_id: str | None = None
    directives: list[DirectorDirective]
    trigger_subject_alert_score: float = 0.0
    trigger_continuity_risk: str = "stable"

    def __init__(
        self,
        *,
        scene_goal: str,
        target_agent_ids: list[str] | None = None,
        priority: str,
        message_hint: str | None = None,
        location_hint: str | None = None,
        target_agent_id: str | None = None,
        reason: str | None = None,
        urgency: str = "advisory",
        cooldown_ticks: int = 3,
        is_intelligent_decision: bool = False,
        strategy: str | None = None,
        source_type: str = "auto",
        source_memory_id: str | None = None,
        directives: list[DirectorDirective] | None = None,
        trigger_subject_alert_score: float = 0.0,
        trigger_continuity_risk: str = "stable",
    ) -> None:
        self.scene_goal = scene_goal
        self.target_agent_ids = list(target_agent_ids or [])
        self.priority = priority
        self.message_hint = message_hint
        self.location_hint = location_hint
        self.target_agent_id = target_agent_id
        self.reason = reason
        self.urgency = urgency
        self.cooldown_ticks = cooldown_ticks
        self.is_intelligent_decision = is_intelligent_decision
        self.strategy = strategy
        self.source_type = source_type
        self.source_memory_id = source_memory_id
        self.directives = list(directives or [])
        self.trigger_subject_alert_score = trigger_subject_alert_score
        self.trigger_continuity_risk = trigger_continuity_risk
