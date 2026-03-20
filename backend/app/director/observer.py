from __future__ import annotations

from dataclasses import dataclass, field

from app.protocol.simulation import DIRECTOR_EVENT_PREFIX
from app.scenario.runtime_config import ScenarioRuntimeConfig
from app.scenario.types import get_world_role
from app.store.models import Agent, Event


@dataclass
class SuspicionTrend:
    """主体告警度变化趋势"""

    current_score: float
    previous_score: float
    delta: float  # 变化量
    trend_type: str  # "rapid_rise" | "gradual_rise" | "stable" | "declining"


@dataclass(init=False)
class DirectorAssessment:
    run_id: str
    current_tick: int
    subject_agent_id: str | None
    subject_alert_score: float
    subject_alert_tracking_enabled: bool
    suspicion_level: str
    continuity_risk: str
    suspicion_trend: SuspicionTrend | None = None
    focus_agent_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    subject_isolation_ticks: int = 0
    recent_rejections: int = 0  # 最近被拒绝的次数
    active_support_count: int = 0  # 当前可用的支援角色数量

    def __init__(
        self,
        *,
        run_id: str,
        current_tick: int,
        subject_agent_id: str | None = None,
        subject_alert_score: float = 0.0,
        subject_alert_tracking_enabled: bool = True,
        suspicion_level: str,
        continuity_risk: str,
        suspicion_trend: SuspicionTrend | None = None,
        focus_agent_ids: list[str] | None = None,
        notes: list[str] | None = None,
        subject_isolation_ticks: int = 0,
        truman_isolation_ticks: int = 0,
        recent_rejections: int = 0,
        active_support_count: int | None = None,
        active_cast_count: int | None = None,
    ) -> None:
        resolved_subject_isolation_ticks = max(subject_isolation_ticks, truman_isolation_ticks)
        resolved_active_support_count = (
            active_support_count if active_support_count is not None else active_cast_count or 0
        )

        self.run_id = run_id
        self.current_tick = current_tick
        self.subject_agent_id = subject_agent_id
        self.subject_alert_score = subject_alert_score
        self.subject_alert_tracking_enabled = subject_alert_tracking_enabled
        self.suspicion_level = suspicion_level
        self.continuity_risk = continuity_risk
        self.suspicion_trend = suspicion_trend
        self.focus_agent_ids = list(focus_agent_ids or [])
        self.notes = list(notes or [])
        self.subject_isolation_ticks = resolved_subject_isolation_ticks
        self.recent_rejections = recent_rejections
        self.active_support_count = resolved_active_support_count

    @property
    def truman_isolation_ticks(self) -> int:
        return self.subject_isolation_ticks

    @truman_isolation_ticks.setter
    def truman_isolation_ticks(self, value: int) -> None:
        self.subject_isolation_ticks = value

    @property
    def active_cast_count(self) -> int:
        return self.active_support_count

    @active_cast_count.setter
    def active_cast_count(self, value: int) -> None:
        self.active_support_count = value


DirectorObserverSemantics = ScenarioRuntimeConfig


class DirectorObserver:
    """Read-only observer for world stability and subject alert signals."""

    def __init__(self, semantics: DirectorObserverSemantics | None = None) -> None:
        self._semantics = semantics or DirectorObserverSemantics()

    def assess(
        self,
        *,
        run_id: str,
        current_tick: int,
        agents: list[Agent],
        events: list[Event],
        previous_subject_alert_score: float = 0.0,
        previous_suspicion_score: float = 0.0,
        subject_isolation_ticks: int = 0,
        truman_isolation_ticks: int = 0,
    ) -> DirectorAssessment:
        previous_alert_score = previous_subject_alert_score or previous_suspicion_score
        isolation_ticks = max(subject_isolation_ticks, truman_isolation_ticks)
        subject = next(
            (
                agent
                for agent in agents
                if get_world_role(agent.profile) == self._semantics.subject_role
            ),
            None,
        )
        subject_alert_score = 0.0
        if self._semantics.subject_alert_tracking and subject:
            subject_alert_score = float(
                (subject.status or {}).get(self._semantics.alert_metric, 0.0) or 0.0
            )

        rejected_count = sum(1 for event in events if event.event_type.endswith("_rejected"))
        director_count = sum(
            1 for event in events if event.event_type.startswith(DIRECTOR_EVENT_PREFIX)
        )
        continuity_score = min(1.0, (rejected_count * 0.18) + (director_count * 0.22))

        # 计算告警度趋势
        suspicion_trend = (
            self._compute_suspicion_trend(
                current_score=subject_alert_score,
                previous_score=previous_alert_score,
            )
            if self._semantics.subject_alert_tracking
            else None
        )

        focus_agent_ids = [subject.id] if subject else []
        for event in events:
            for agent_id in (event.actor_agent_id, event.target_agent_id):
                if not agent_id or agent_id in focus_agent_ids:
                    continue
                focus_agent_ids.append(agent_id)
                if len(focus_agent_ids) >= 3:
                    break
            if len(focus_agent_ids) >= 3:
                break

        # 计算支援角色数量
        support_count = sum(
            1
            for agent in agents
            if get_world_role(agent.profile) in self._semantics.support_role_set()
        )

        notes: list[str] = []
        if self._semantics.subject_alert_tracking and subject_alert_score >= 0.6:
            notes.append("主体告警值已进入需要重点观察的区间。")
        if suspicion_trend and suspicion_trend.trend_type == "rapid_rise":
            notes.append(f"警告：主体告警值正在快速上升（+{suspicion_trend.delta:.2f}）。")
        if rejected_count > 0:
            notes.append("最近存在被拒绝或受阻的动作，可能削弱世界的自然感。")
        if director_count > 0:
            notes.append("最近出现了导演级事件，需要关注连续性修补效果。")
        if isolation_ticks >= 3:
            notes.append(f"主体已经连续 {isolation_ticks} 个 tick 独处，可能感到孤独。")
        if not notes:
            notes.append("世界整体保持平稳，暂无明显异常信号。")

        return DirectorAssessment(
            run_id=run_id,
            current_tick=current_tick,
            subject_agent_id=subject.id if subject else None,
            subject_alert_score=subject_alert_score,
            subject_alert_tracking_enabled=self._semantics.subject_alert_tracking,
            suspicion_level=(
                self._label_suspicion(subject_alert_score)
                if self._semantics.subject_alert_tracking
                else "low"
            ),
            suspicion_trend=suspicion_trend,
            continuity_risk=self._label_continuity(continuity_score),
            focus_agent_ids=focus_agent_ids,
            notes=notes,
            subject_isolation_ticks=isolation_ticks,
            recent_rejections=rejected_count,
            active_support_count=support_count,
        )

    def _compute_suspicion_trend(
        self,
        current_score: float,
        previous_score: float,
    ) -> SuspicionTrend:
        """计算主体告警度变化趋势"""
        delta = current_score - previous_score

        if delta >= 0.2:
            trend_type = "rapid_rise"
        elif delta >= 0.05:
            trend_type = "gradual_rise"
        elif delta <= -0.1:
            trend_type = "declining"
        else:
            trend_type = "stable"

        return SuspicionTrend(
            current_score=current_score,
            previous_score=previous_score,
            delta=delta,
            trend_type=trend_type,
        )

    def _label_suspicion(self, score: float) -> str:
        if score >= 0.8:
            return "high"
        if score >= 0.6:
            return "alerted"
        if score >= 0.3:
            return "guarded"
        return "low"

    def _label_continuity(self, score: float) -> str:
        if score >= 0.75:
            return "critical"
        if score >= 0.45:
            return "elevated"
        if score >= 0.15:
            return "watch"
        return "stable"
