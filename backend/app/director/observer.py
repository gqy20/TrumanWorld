from __future__ import annotations

from dataclasses import dataclass, field

from app.protocol.simulation import DIRECTOR_EVENT_PREFIX
from app.scenario.types import get_world_role
from app.store.models import Agent, Event


@dataclass
class SuspicionTrend:
    """怀疑度变化趋势"""

    current_score: float
    previous_score: float
    delta: float  # 变化量
    trend_type: str  # "rapid_rise" | "gradual_rise" | "stable" | "declining"


@dataclass
class DirectorAssessment:
    run_id: str
    current_tick: int
    truman_agent_id: str | None
    truman_suspicion_score: float
    suspicion_level: str
    continuity_risk: str
    suspicion_trend: SuspicionTrend | None = None
    focus_agent_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # 新增场景感知字段
    truman_isolation_ticks: int = 0  # Truman 独处时长
    recent_rejections: int = 0  # 最近被拒绝的次数
    active_cast_count: int = 0  # 当前可用的 cast 数量


class DirectorObserver:
    """Read-only observer for world stability and Truman suspicion."""

    def assess(
        self,
        *,
        run_id: str,
        current_tick: int,
        agents: list[Agent],
        events: list[Event],
        previous_suspicion_score: float = 0.0,
        truman_isolation_ticks: int = 0,
    ) -> DirectorAssessment:
        truman = next(
            (agent for agent in agents if get_world_role(agent.profile) == "truman"),
            None,
        )
        suspicion_score = (
            float((truman.status or {}).get("suspicion_score", 0.0) or 0.0) if truman else 0.0
        )

        rejected_count = sum(1 for event in events if event.event_type.endswith("_rejected"))
        director_count = sum(
            1 for event in events if event.event_type.startswith(DIRECTOR_EVENT_PREFIX)
        )
        continuity_score = min(1.0, (rejected_count * 0.18) + (director_count * 0.22))

        # 计算怀疑度趋势
        suspicion_trend = self._compute_suspicion_trend(
            current_score=suspicion_score,
            previous_score=previous_suspicion_score,
        )

        focus_agent_ids = [truman.id] if truman else []
        for event in events:
            for agent_id in (event.actor_agent_id, event.target_agent_id):
                if not agent_id or agent_id in focus_agent_ids:
                    continue
                focus_agent_ids.append(agent_id)
                if len(focus_agent_ids) >= 3:
                    break
            if len(focus_agent_ids) >= 3:
                break

        # 计算 cast 数量
        cast_count = sum(1 for agent in agents if get_world_role(agent.profile) == "cast")

        notes: list[str] = []
        if suspicion_score >= 0.6:
            notes.append("Truman 的怀疑度已进入需要重点观察的区间。")
        if suspicion_trend and suspicion_trend.trend_type == "rapid_rise":
            notes.append(f"警告：怀疑度正在快速上升（+{suspicion_trend.delta:.2f}）。")
        if rejected_count > 0:
            notes.append("最近存在被拒绝或受阻的动作，可能削弱世界的自然感。")
        if director_count > 0:
            notes.append("最近出现了导演级事件，需要关注连续性修补效果。")
        if truman_isolation_ticks >= 3:
            notes.append(f"Truman 已经连续 {truman_isolation_ticks} 个 tick 独处，可能感到孤独。")
        if not notes:
            notes.append("世界整体保持平稳，暂无明显异常信号。")

        return DirectorAssessment(
            run_id=run_id,
            current_tick=current_tick,
            truman_agent_id=truman.id if truman else None,
            truman_suspicion_score=suspicion_score,
            suspicion_level=self._label_suspicion(suspicion_score),
            suspicion_trend=suspicion_trend,
            continuity_risk=self._label_continuity(continuity_score),
            focus_agent_ids=focus_agent_ids,
            notes=notes,
            truman_isolation_ticks=truman_isolation_ticks,
            recent_rejections=rejected_count,
            active_cast_count=cast_count,
        )

    def _compute_suspicion_trend(
        self,
        current_score: float,
        previous_score: float,
    ) -> SuspicionTrend:
        """计算怀疑度变化趋势"""
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
