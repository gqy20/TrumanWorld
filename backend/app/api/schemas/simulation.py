from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.protocol.simulation import EventType

# ============================================================================
# Common Responses
# ============================================================================


class ErrorResponse(BaseModel):
    """通用错误响应"""

    detail: str = Field(..., description="错误描述", examples=["Run not found"])
    code: str | None = Field(None, description="错误代码", examples=["RUN_NOT_FOUND"])
    context: dict[str, Any] = Field(default_factory=dict, description="额外上下文信息")


class ValidationErrorDetail(BaseModel):
    """验证错误详情"""

    loc: list[str] = Field(..., description="错误位置", examples=[["body", "name"]])
    msg: str = Field(..., description="错误消息", examples=["Field required"])
    type: str = Field(..., description="错误类型", examples=["missing"])


class ValidationErrorResponse(BaseModel):
    """验证错误响应（FastAPI 默认格式）"""

    detail: list[ValidationErrorDetail]


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="服务状态", examples=["ok"])


class SystemOverviewComponentResponse(BaseModel):
    """单个系统组件资源概览"""

    status: str = Field(..., description="组件状态", examples=["available", "unavailable"])
    rss_bytes: int = Field(..., description="常驻内存字节数", ge=0)
    unique_bytes: int | None = Field(
        None,
        description="更接近独占内存的估算字节数（优先 USS，回退 PSS；不可用时为空）",
        ge=0,
    )
    vms_bytes: int = Field(..., description="虚拟内存字节数", ge=0)
    cpu_seconds: float = Field(..., description="累计 CPU 秒数", ge=0)
    cpu_percent: float = Field(..., description="CPU 占用百分比", ge=0)
    process_count: int = Field(..., description="进程数", ge=0)


class SystemOverviewComponentsResponse(BaseModel):
    """系统组件聚合视图"""

    backend: SystemOverviewComponentResponse
    frontend: SystemOverviewComponentResponse
    postgres: SystemOverviewComponentResponse
    total: SystemOverviewComponentResponse


class SystemOverviewResponse(BaseModel):
    """系统运行总览响应"""

    collected_at: int = Field(..., description="采集时间戳（毫秒）", ge=0)
    components: SystemOverviewComponentsResponse


# Common response definitions for reuse in route decorators
COMMON_RESPONSES = {
    400: {
        "description": "请求参数错误",
        "model": ErrorResponse,
    },
    401: {
        "description": "未授权",
        "model": ErrorResponse,
    },
    404: {
        "description": "资源不存在",
        "model": ErrorResponse,
    },
    422: {
        "description": "验证错误",
        "model": ValidationErrorResponse,
    },
    500: {
        "description": "服务器内部错误",
        "model": ErrorResponse,
    },
}


# ============================================================================
# Status & Run Responses
# ============================================================================


class RunCreateRequest(BaseModel):
    """创建新的模拟运行请求"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="运行名称",
        examples=["My First World", "Alice Town"],
    )
    scenario_type: str | None = Field(
        default=None,
        description="运行场景类型；未提供时使用系统默认场景",
        examples=["hero_world", "open_world"],
    )
    seed_demo: bool = Field(
        default=True,
        description="是否自动填充演示数据（agent、地点等）",
        examples=[True],
    )
    auto_start: bool = Field(
        default=True,
        description="初始化完成后是否立即启动自动 tick 调度",
        examples=[False],
    )
    tick_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="每个 tick 代表的分钟数",
        examples=[5],
    )


class SimulationSpeedRequest(BaseModel):
    multiplier: float = Field(
        ...,
        ge=0.25,
        le=8.0,
        description="模拟速度倍率；只改变世界时间映射，不改变事件顺序",
    )


class ManualActionRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, description="执行动作的运行时 Agent ID")
    action_type: Literal["move", "talk", "work", "rest", "start_activity", "interrupt_activity"]
    target_location_id: str | None = None
    target_agent_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ManualActionResultResponse(BaseModel):
    accepted: bool
    action_type: str
    reason: str
    event_payload: dict[str, Any] = Field(default_factory=dict)


class ManualTickResponse(BaseModel):
    run_id: str
    tick_no: int = Field(ge=0)
    world_time: str
    accepted: list[ManualActionResultResponse] = Field(default_factory=list)
    rejected: list[ManualActionResultResponse] = Field(default_factory=list)


class RunBaseResponse(BaseModel):
    id: str = Field(..., description="运行 ID", examples=["550e8400-e29b-41d4-a716-446655440000"])
    name: str = Field(..., description="运行名称", examples=["Truman Town"])
    status: str = Field(..., description="运行状态", examples=["running", "paused", "stopped"])
    scenario_type: str = Field(..., description="场景类型", examples=["hero_world", "open_world"])
    current_tick: int = Field(..., description="当前 tick", examples=[42])
    tick_minutes: int = Field(..., description="每 tick 分钟数", examples=[5])
    simulation_speed: float = Field(1.0, description="当前模拟速度倍率", ge=0.25, le=8.0)
    was_running_before_restart: bool = Field(False, description="服务重启前是否在运行中")
    started_at: datetime | None = Field(None, description="最近一次启动时间（UTC ISO8601）")
    elapsed_seconds: int = Field(0, description="累计运行秒数", ge=0)
    created_at: datetime | None = Field(None, description="运行创建时间（UTC ISO8601）")


class RunResponse(RunBaseResponse):
    agent_count: int = Field(0, description="本次运行的 agent 数量", ge=0)
    location_count: int = Field(0, description="本次运行的地点数量", ge=0)
    event_count: int = Field(0, description="本次运行产生的事件总数", ge=0)


class StatusResponse(BaseModel):
    run_id: str = Field(
        ..., description="运行 ID", examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    status: str = Field(..., description="操作状态", examples=["success", "error"])


class RunDetailResponse(RunBaseResponse):
    pass


class ScenarioSummaryResponse(BaseModel):
    id: str = Field(..., description="场景 ID", examples=["hero_world"])
    name: str = Field(..., description="场景名称", examples=["Hero World"])
    version: int = Field(..., description="场景版本", ge=1, examples=[1])


class DirectorEventRequest(BaseModel):
    """导演事件注入请求"""

    event_type: Literal["activity", "shutdown", "broadcast", "weather_change", "power_outage"] = (
        Field(
            ...,
            description="事件类型",
            examples=["activity", "shutdown", "broadcast", "weather_change", "power_outage"],
        )
    )
    payload: dict = Field(
        default_factory=dict,
        description="事件负载数据",
        examples=[{"message": "咖啡馆举办周末派对", "duration_hours": 2}],
    )
    location_id: str | None = Field(
        None,
        description="事件发生地点 ID",
        examples=["downtown_cafe"],
    )
    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="事件重要性（0-1）",
        examples=[0.8],
    )


class TickResponse(BaseModel):
    """Tick 推进响应"""

    run_id: str = Field(..., description="运行 ID")
    tick_no: int = Field(..., description="tick 编号")
    accepted_count: int = Field(..., description="接受的动作数量")
    rejected_count: int = Field(..., description="拒绝的动作数量")


class RuleEvaluationResponse(BaseModel):
    decision: Literal["allowed", "violates_rule", "impossible", "soft_risk"] = Field(
        ...,
        description="规则裁决结果",
    )
    primary_rule_id: str | None = Field(None, description="主裁决规则 ID")
    reason: str | None = Field(None, description="规则裁决原因")
    matched_rule_ids: list[str] = Field(default_factory=list, description="命中的规则 ID 列表")


class TimelineEventResponse(BaseModel):
    id: str = Field(..., description="事件 ID", examples=["evt_001"])
    tick_no: int = Field(..., description="Tick 编号", examples=[42])
    event_type: EventType = Field(
        ..., description="事件类型", examples=["speech", "listen", "move"]
    )
    importance: float | None = Field(None, description="重要性", ge=0, le=1, examples=[0.8])
    payload: dict = Field(default_factory=dict, description="事件负载数据")
    world_time: str | None = Field(None, description="模拟世界时间", examples=["09:30"])
    world_date: str | None = Field(None, description="模拟世界日期", examples=["2024-03-15"])


class WorldEventsResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    events: list[WorldEventResponse] = Field(default_factory=list, description="事件列表")
    total: int = Field(0, description="事件总数", ge=0)
    latest_tick: int = Field(0, description="返回事件中最大 tick，用于增量查询", ge=0)


class TimelineRunInfo(BaseModel):
    current_tick: int = Field(..., description="当前 tick", examples=[100])
    tick_minutes: int = Field(..., description="每 tick 分钟数", examples=[5])
    world_start_iso: str = Field(
        ..., description="世界开始时间 ISO", examples=["2024-03-15T06:00:00"]
    )
    current_world_time_iso: str = Field(
        ..., description="当前世界时间 ISO", examples=["2024-03-15T14:30:00"]
    )


class TimelineResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    events: list[TimelineEventResponse] = Field(default_factory=list, description="事件列表")
    total: int = Field(0, description="当前运行的未过滤事件总数", ge=0)
    filtered: int = Field(0, description="应用查询条件后的事件总数", ge=0)
    run_info: TimelineRunInfo | None = Field(None, description="运行信息")


class DirectorObservationResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    current_tick: int = Field(..., description="当前 tick")
    subject_agent_id: str | None = Field(None, description="主要观察对象 agent ID")
    subject_alert_tracking_enabled: bool = Field(
        True,
        description="当前场景是否启用了主体告警跟踪能力",
    )
    subject_alert_score: float | None = Field(
        None,
        description="主要观察对象警觉/异常分数；未启用主体告警跟踪时为空",
        ge=0,
        le=1,
        examples=[0.35],
    )
    suspicion_level: str = Field(..., description="怀疑级别", examples=["low", "medium", "high"])
    continuity_risk: str = Field(
        ..., description="连续性风险", examples=["stable", "warning", "critical"]
    )
    focus_agent_ids: list[str] = Field(default_factory=list, description="关注 agent IDs")
    notes: list[str] = Field(default_factory=list, description="观察笔记")


class AgentMovementResponse(BaseModel):
    id: str = Field(..., description="移动 ID")
    state: Literal["in_transit"] = Field("in_transit", description="移动状态")
    from_location_id: str = Field(..., description="出发地点 ID")
    to_location_id: str = Field(..., description="目标地点 ID")
    started_tick: int = Field(..., description="开始 Tick", ge=0)
    arrival_tick: int = Field(..., description="预计到达 Tick", ge=1)
    route_node_ids: list[str] = Field(default_factory=list, description="服务端规划的道路节点")
    distance: float = Field(0.0, description="路线距离", ge=0)
    speed: float = Field(1.5, description="兼容字段：移动速度（米/秒）", gt=0)
    speed_mps: float = Field(1.5, description="移动速度（米/秒）", gt=0)
    started_at_world_time: datetime | None = Field(None, description="移动开始世界时间")
    expected_arrival_world_time: datetime | None = Field(None, description="预计到达世界时间")
    duration_seconds: float | None = Field(None, description="预计移动秒数", gt=0)
    progress: float | None = Field(None, description="当前路线进度", ge=0, le=1)
    activity_id: str | None = Field(None, description="所属活动 ID")


class AgentActivityStepResponse(BaseModel):
    id: str
    action: str
    status: Literal["pending", "waiting_for_resource", "performing", "completed"]
    duration_seconds: float = Field(..., ge=0)
    visual_state: str | None = None
    resource_required: bool = False
    candidate_resource_ids: list[str] = Field(default_factory=list)
    claimed_resource_id: str | None = None
    release_after: bool = True
    started_at_world_time: datetime | None = None
    expected_end_world_time: datetime | None = None
    progress: float | None = Field(None, ge=0, le=1)


class AgentActivityResponse(BaseModel):
    id: str = Field(..., description="活动实例 ID")
    agent_id: str = Field(..., description="Agent ID")
    activity_type: str = Field(..., description="活动类型")
    status: Literal[
        "planned",
        "navigating",
        "waiting_for_resource",
        "performing",
        "completed",
        "interrupted",
        "failed",
        "cancelled",
    ]
    step_index: int = Field(..., ge=0)
    started_at_world_time: datetime
    expected_end_world_time: datetime | None = None
    duration_seconds: float = Field(..., ge=0)
    target_entity_id: str | None = None
    claimed_resource_ids: list[str] = Field(default_factory=list)
    parent_intent_id: str | None = None
    interruption_reason: str | None = None
    interruptible: bool = True
    steps: list[AgentActivityStepResponse] = Field(default_factory=list)
    current_step_id: str | None = None
    current_action: str | None = None
    visual_state: str | None = None
    zone_id: str | None = None
    queue_position: int | None = Field(None, ge=1)
    progress: float | None = Field(None, ge=0, le=1)


class AgentSummaryResponse(BaseModel):
    id: str = Field(..., description="Agent ID", examples=["agent_alice"])
    name: str = Field(..., description="Agent 名称", examples=["Alice"])
    occupation: str | None = Field(None, description="职业", examples=["咖啡师"])
    current_goal: str | None = Field(None, description="当前目标", examples=["完成早班工作"])
    current_location_id: str | None = Field(None, description="当前位置 ID", examples=["loc_cafe"])
    movement: AgentMovementResponse | None = Field(None, description="当前在途状态")
    activity: AgentActivityResponse | None = Field(None, description="当前或最近完成的持续活动")
    position_meters: tuple[float, float, float] | None = Field(None, description="权威世界坐标")
    facing_radians: float = Field(0.0, description="权威朝向")
    zone_id: str | None = Field(None, description="当前地图 Zone")
    status: dict = Field(default_factory=dict, description="状态信息")
    profile: dict = Field(default_factory=dict, description="档案信息")
    config_id: str | None = Field(None, description="配置 ID", examples=["alice"])


class AgentsListResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    agents: list[AgentSummaryResponse] = Field(default_factory=list, description="Agent 列表")


class AgentMemoryCountsResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    tick_no: int = Field(..., description="采样时的 Tick 编号", ge=0)
    memory_limit: int = Field(..., description="每个 Agent 的观测上限", ge=1, le=100)
    observed_counts: dict[str, int] = Field(
        default_factory=dict,
        description="每个 Agent 在观测上限内的记忆数量",
    )
    capped_agent_ids: list[str] = Field(
        default_factory=list,
        description="记忆数量达到或超过观测上限的 Agent ID",
    )


class AgentEventResponse(BaseModel):
    id: str = Field(..., description="事件 ID")
    tick_no: int = Field(..., description="Tick 编号")
    event_type: EventType = Field(..., description="事件类型")
    actor_agent_id: str | None = Field(None, description="发起者 ID")
    actor_name: str | None = Field(None, description="发起者名称", examples=["Alice"])
    target_agent_id: str | None = Field(None, description="目标 ID")
    target_name: str | None = Field(None, description="目标名称", examples=["Bob"])
    location_id: str | None = Field(None, description="地点 ID")
    location_name: str | None = Field(None, description="地点名称", examples=["咖啡店"])
    payload: dict = Field(default_factory=dict, description="事件负载数据")


class AgentMemoryResponse(BaseModel):
    id: str = Field(..., description="记忆 ID")
    memory_type: str = Field(
        ..., description="记忆类型", examples=["recent", "episodic", "reflection"]
    )
    memory_category: str = Field(
        ..., description="记忆层级", examples=["short_term", "medium_term", "long_term"]
    )
    summary: str | None = Field(None, description="记忆摘要")
    content: str = Field(..., description="记忆内容")
    importance: float | None = Field(None, description="重要性", ge=0, le=1)
    event_importance: float | None = Field(None, description="事件客观显著性", ge=0, le=1)
    self_relevance: float | None = Field(None, description="主体相关性", ge=0, le=1)
    streak_count: int = Field(1, description="连续重复次数", ge=1)
    related_agent_id: str | None = Field(None, description="关联 agent ID")
    related_agent_name: str | None = Field(None, description="关联 agent 名称")


class AgentRelationshipResponse(BaseModel):
    other_agent_id: str = Field(..., description="对方 agent ID")
    other_agent_name: str | None = Field(None, description="对方 agent 名称", examples=["Bob"])
    familiarity: float = Field(..., description="熟悉度", ge=0, le=1, examples=[0.75])
    trust: float = Field(..., description="信任度", ge=-1, le=1, examples=[0.6])
    affinity: float = Field(..., description="亲和力", ge=-1, le=1, examples=[0.5])
    relation_type: str = Field(
        ..., description="关系类型", examples=["friend", "colleague", "stranger"]
    )


class WorldRulesSummaryResponse(BaseModel):
    available_actions: list[str] = Field(default_factory=list, description="当前推荐可行动作")
    policy_notices: list[str] = Field(default_factory=list, description="当前政策或环境通知")
    blocked_constraints: list[str] = Field(default_factory=list, description="当前明确约束")
    current_risks: list[str] = Field(default_factory=list, description="当前风险提示")
    recent_rule_feedback: list[str] = Field(default_factory=list, description="最近制度反馈")


class GovernanceRecordResponse(BaseModel):
    id: str = Field(..., description="治理记录 ID")
    tick_no: int = Field(..., description="触发 tick")
    source_event_id: str | None = Field(None, description="来源事件 ID")
    location_id: str | None = Field(None, description="地点 ID")
    location_name: str | None = Field(None, description="地点名称")
    action_type: str = Field(..., description="被治理动作类型")
    decision: str = Field(..., description="治理决策")
    reason: str | None = Field(None, description="治理原因")
    observed: bool = Field(..., description="是否被观察到")
    observation_score: float = Field(..., description="观察分", ge=0, le=1)
    intervention_score: float = Field(..., description="干预分", ge=0, le=1)
    metadata: dict = Field(default_factory=dict, description="附加治理元数据")


class AgentGovernanceRecordsResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    agent_id: str = Field(..., description="Agent ID")
    records: list[GovernanceRecordResponse] = Field(default_factory=list, description="治理记录")
    total: int = Field(0, description="返回记录数", ge=0)


class DirectorGovernanceRecordResponse(BaseModel):
    id: str = Field(..., description="治理记录 ID")
    tick_no: int = Field(..., description="触发 tick")
    source_event_id: str | None = Field(None, description="来源事件 ID")
    agent_id: str = Field(..., description="Agent ID")
    agent_name: str | None = Field(None, description="Agent 名称")
    location_id: str | None = Field(None, description="地点 ID")
    location_name: str | None = Field(None, description="地点名称")
    action_type: str = Field(..., description="被治理动作类型")
    decision: str = Field(..., description="治理决策")
    reason: str | None = Field(None, description="治理原因")
    observed: bool = Field(..., description="是否被观察到")
    observation_score: float = Field(..., description="观察分", ge=0, le=1)
    intervention_score: float = Field(..., description="干预分", ge=0, le=1)
    metadata: dict = Field(default_factory=dict, description="附加治理元数据")


class DirectorGovernanceRecordsResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    records: list[DirectorGovernanceRecordResponse] = Field(
        default_factory=list, description="治理记录"
    )
    total: int = Field(0, description="返回记录数", ge=0)


# ============================================================================
# Governance Cases & Restrictions
# ============================================================================


class GovernanceCaseResponse(BaseModel):
    id: str = Field(..., description="案件 ID")
    run_id: str = Field(..., description="运行 ID")
    agent_id: str = Field(..., description="Agent ID")
    agent_name: str | None = Field(None, description="Agent 名称")
    status: str = Field(..., description="案件状态")
    opened_tick: int = Field(..., description="开案 tick")
    last_updated_tick: int = Field(..., description="最后更新 tick")
    primary_reason: str = Field(..., description="主要原因")
    severity: str = Field(..., description="严重程度")
    record_count: int = Field(..., description="关联记录数")
    active_restriction_count: int = Field(..., description="活跃限制数")
    metadata: dict = Field(default_factory=dict, description="附加元数据")
    created_at: datetime = Field(..., description="创建时间")


class GovernanceCasesResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    cases: list[GovernanceCaseResponse] = Field(default_factory=list, description="治理案件列表")
    total: int = Field(0, description="返回案件数", ge=0)


class GovernanceRestrictionResponse(BaseModel):
    id: str = Field(..., description="限制 ID")
    run_id: str = Field(..., description="运行 ID")
    agent_id: str = Field(..., description="Agent ID")
    agent_name: str | None = Field(None, description="Agent 名称")
    case_id: str | None = Field(None, description="关联案件 ID")
    restriction_type: str = Field(..., description="限制类型")
    status: str = Field(..., description="限制状态")
    scope_type: str = Field(..., description="范围类型")
    scope_value: str | None = Field(None, description="范围值")
    reason: str | None = Field(None, description="限制原因")
    start_tick: int = Field(..., description="开始 tick")
    end_tick: int | None = Field(None, description="结束 tick")
    severity: str = Field(..., description="严重程度")
    metadata: dict = Field(default_factory=dict, description="附加元数据")
    created_at: datetime = Field(..., description="创建时间")


class GovernanceRestrictionsResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    restrictions: list[GovernanceRestrictionResponse] = Field(
        default_factory=list, description="治理限制列表"
    )
    total: int = Field(0, description="返回限制数", ge=0)


# ============================================================================
# Agent Economic State
# ============================================================================


class AgentEconomicStateResponse(BaseModel):
    agent_id: str = Field(..., description="Agent ID")
    agent_name: str | None = Field(None, description="Agent 名称")
    cash: float = Field(..., description="现金余额")
    employment_status: str = Field(..., description="就业状态")
    food_security: float = Field(..., description="食品安全 (0-1)")
    housing_security: float = Field(..., description="住房安全 (0-1)")
    work_restriction_until_tick: int | None = Field(None, description="工作限制截止 tick")
    last_income_tick: int | None = Field(None, description="最后收入 tick")
    metadata: dict = Field(default_factory=dict, description="附加元数据")


class AgentEconomicSummaryResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    agent_id: str = Field(..., description="Agent ID")
    economic_state: AgentEconomicStateResponse | None = Field(None, description="经济状态")
    recent_effects: list[EconomicEffectLogResponse] = Field(
        default_factory=list, description="最近经济效果"
    )


class EconomicEffectLogResponse(BaseModel):
    id: str = Field(..., description="日志 ID")
    run_id: str = Field(..., description="运行 ID")
    agent_id: str = Field(..., description="Agent ID")
    case_id: str | None = Field(None, description="关联案件 ID")
    tick_no: int = Field(..., description="触发 tick")
    effect_type: str = Field(..., description="效果类型")
    cash_delta: float = Field(..., description="现金变化")
    food_security_delta: float = Field(..., description="食品安全变化")
    housing_security_delta: float = Field(..., description="住房安全变化")
    employment_status_before: str | None = Field(None, description="变化前就业状态")
    employment_status_after: str | None = Field(None, description="变化后就业状态")
    reason: str | None = Field(None, description="原因")
    metadata: dict = Field(default_factory=dict, description="附加元数据")
    created_at: datetime = Field(..., description="创建时间")


class EconomicEffectLogsResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    agent_id: str | None = Field(None, description="Agent ID (可选)")
    logs: list[EconomicEffectLogResponse] = Field(default_factory=list, description="经济效果日志")
    total: int = Field(0, description="返回日志数", ge=0)


class AgentDetailResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    agent_id: str = Field(..., description="Agent ID")
    name: str = Field(..., description="名称", examples=["Alice"])
    occupation: str | None = Field(None, description="职业", examples=["咖啡师"])
    status: dict = Field(default_factory=dict, description="状态信息")
    current_goal: str | None = Field(None, description="当前目标")
    config_id: str | None = Field(None, description="配置 ID")
    personality: dict = Field(default_factory=dict, description="人格特质")
    profile: dict = Field(default_factory=dict, description="档案信息")
    recent_events: list[AgentEventResponse] = Field(default_factory=list, description="最近事件")
    memories: list[AgentMemoryResponse] = Field(default_factory=list, description="记忆列表")
    relationships: list[AgentRelationshipResponse] = Field(
        default_factory=list, description="关系网络"
    )
    world_rules_summary: WorldRulesSummaryResponse = Field(
        default_factory=WorldRulesSummaryResponse,
        description="面向 agent 的制度摘要",
    )


class WorldClockResponse(BaseModel):
    iso: str = Field(..., description="ISO 时间", examples=["2024-03-15T14:30:00"])
    date: str = Field(..., description="日期", examples=["2024-03-15"])
    time: str = Field(..., description="时间", examples=["14:30"])
    year: int = Field(..., description="年", examples=[2024])
    month: int = Field(..., description="月", ge=1, le=12, examples=[3])
    day: int = Field(..., description="日", ge=1, le=31, examples=[15])
    hour: int = Field(..., description="时", ge=0, le=23, examples=[14])
    minute: int = Field(..., description="分", ge=0, le=59, examples=[30])
    weekday: int = Field(..., description="星期几 (0=周一)", ge=0, le=6, examples=[4])
    weekday_name: str = Field(..., description="星期名", examples=["Friday"])
    weekday_name_cn: str = Field(..., description="星期名中文", examples=["周五"])
    is_weekend: bool = Field(..., description="是否周末")
    time_period: str = Field(..., description="时段", examples=["afternoon"])
    time_period_cn: str = Field(..., description="时段中文", examples=["下午"])


class WorldLocationResponse(BaseModel):
    id: str = Field(..., description="地点 ID", examples=["loc_cafe"])
    name: str = Field(..., description="地点名称", examples=["咖啡店"])
    location_type: str = Field(..., description="地点类型", examples=["commercial"])
    x: int = Field(..., description="X 坐标", examples=[120])
    y: int = Field(..., description="Y 坐标", examples=[80])
    capacity: int = Field(..., description="容量", ge=0, examples=[20])
    occupants: list[AgentSummaryResponse] = Field(default_factory=list, description="在场 agent")


class WorldMapNodeResponse(BaseModel):
    id: str = Field(..., description="道路节点 ID")
    x: float = Field(..., description="地图 X 坐标（米）")
    y: float = Field(..., description="地图 Z 坐标（米）")


class WorldMapEdgeResponse(BaseModel):
    from_node_id: str = Field(..., description="起始道路节点")
    to_node_id: str = Field(..., description="结束道路节点")
    distance: float = Field(..., description="边长度", gt=0)
    bidirectional: bool = Field(True, description="是否双向通行")


class WorldMapTopologyResponse(BaseModel):
    version: int = Field(1, description="地图协议版本")
    nodes: list[WorldMapNodeResponse] = Field(default_factory=list)
    edges: list[WorldMapEdgeResponse] = Field(default_factory=list)
    location_entrances: dict[str, str] = Field(default_factory=dict)


class WorldObjectStateResponse(BaseModel):
    resource_id: str
    object_id: str
    object_type: str
    slot_kind: str
    location_id: str
    zone_id: str
    capacity: int = Field(..., ge=1)
    occupant_agent_ids: list[str] = Field(default_factory=list)
    queue_agent_ids: list[str] = Field(default_factory=list)


class WorldEventResponse(BaseModel):
    id: str = Field(..., description="事件 ID")
    tick_no: int = Field(..., description="Tick 编号")
    event_type: EventType = Field(..., description="事件类型")
    location_id: str | None = Field(None, description="地点 ID")
    actor_agent_id: str | None = Field(None, description="发起者 ID")
    target_agent_id: str | None = Field(None, description="目标 ID")
    actor_name: str | None = Field(None, description="发起者名称")
    target_name: str | None = Field(None, description="目标名称")
    location_name: str | None = Field(None, description="地点名称")
    payload: dict = Field(default_factory=dict, description="事件负载数据")


class WorldSnapshotRunResponse(RunBaseResponse):
    pass


class WorldStageLocationVisualResponse(BaseModel):
    visual_preset: str | None = Field(None, description="地点视觉预设", examples=["house"])
    glyph: str | None = Field(None, description="地点字形标记", examples=["H"])


class WorldStagePaletteResponse(BaseModel):
    background_color: str | None = Field(None, description="背景色", examples=["#112317"])
    header_color: str | None = Field(None, description="顶部氛围层颜色", examples=["#1d4d2b"])
    header_alpha: float | None = Field(None, description="顶部氛围层透明度", examples=[0.34])
    vignette_color: str | None = Field(None, description="舞台暗角颜色", examples=["#08140d"])
    vignette_alpha: float | None = Field(None, description="舞台暗角透明度", examples=[0.18])
    label_color: str | None = Field(None, description="标签文字颜色", examples=["#dcfce7"])


class WorldStageAgentStatusVisualResponse(BaseModel):
    visual_preset: str | None = Field(None, description="角色视觉预设", examples=["student"])
    marker: str | None = Field(None, description="角色状态标记", examples=["!"])


class WorldStageAgentUiResponse(BaseModel):
    statuses: dict[str, WorldStageAgentStatusVisualResponse] = Field(
        default_factory=dict,
        description="按角色状态定义的视觉预设",
    )


class WorldStageUiResponse(BaseModel):
    renderer: str | None = Field(None, description="舞台渲染器", examples=["voxel"])
    theme: str | None = Field(None, description="舞台主题", examples=["campus_night"])
    ground_preset: str | None = Field(None, description="地面预设", examples=["boardwalk"])
    palette: WorldStagePaletteResponse = Field(
        default_factory=WorldStagePaletteResponse,
        description="舞台调色板",
    )
    agents: WorldStageAgentUiResponse = Field(
        default_factory=WorldStageAgentUiResponse,
        description="角色 UI 配置",
    )
    location_types: dict[str, WorldStageLocationVisualResponse] = Field(
        default_factory=dict,
        description="按地点类型定义的视觉预设",
    )


class WorldUiConfigResponse(BaseModel):
    stage: WorldStageUiResponse = Field(
        default_factory=WorldStageUiResponse, description="舞台 UI 配置"
    )


class WorldDirectorStatsResponse(BaseModel):
    total: int = Field(0, description="总干预数", ge=0)
    executed: int = Field(0, description="已消费数", ge=0)
    execution_rate: int = Field(0, description="消费率 (%)", ge=0, le=100)


class WorldDailyStatsResponse(BaseModel):
    talk_count: int = Field(0, description="社交发言数", ge=0)
    move_count: int = Field(0, description="移动数", ge=0)
    rejection_count: int = Field(0, description="拒绝数", ge=0)
    total_input_tokens: int = Field(0, description="输入 token 数", ge=0)
    total_output_tokens: int = Field(0, description="输出 token 数", ge=0)
    total_reasoning_tokens: int = Field(0, description="推理 token 数", ge=0)
    total_cache_read_tokens: int = Field(0, description="缓存读取 token 数", ge=0)
    total_cache_creation_tokens: int = Field(0, description="缓存创建 token 数", ge=0)
    total_cost_usd: float = Field(0.0, description="累计 LLM 成本（美元）", ge=0)
    llm_provider: str | None = Field(None, description="最近一次 LLM 调用的 provider")
    llm_model: str | None = Field(None, description="最近一次 LLM 调用的模型名")


class WorldHealthMetricsConfig(BaseModel):
    """健康度评估配置参数"""

    continuity_penalty_factor: float = Field(200.0, description="连续性惩罚因子")
    continuity_warning_threshold: float = Field(0.2, description="连续性警告阈值")
    continuity_trend_down_threshold: float = Field(0.15, description="连续性下降趋势阈值")
    continuity_trend_stable_threshold: float = Field(0.05, description="连续性稳定趋势阈值")
    social_baseline_talks_per_person_per_day: float = Field(20.0, description="社交基线")
    social_trend_up_threshold: float = Field(10.0, description="社交上升阈值")
    social_trend_stable_threshold: float = Field(3.0, description="社交稳定阈值")
    heat_normalization_baseline: float = Field(30.0, description="热度归一化基线")
    heat_threshold_very_active: float = Field(0.7, description="非常活跃阈值")
    heat_threshold_active: float = Field(0.4, description="活跃阈值")
    heat_threshold_mild: float = Field(0.15, description="轻度活跃阈值")
    heat_glow_threshold: float = Field(0.1, description="发光阈值")
    ui_location_detail_max_events: int = Field(50, description="地点详情最大事件数")
    ui_intelligence_stream_max_events: int = Field(500, description="情报流最大事件数")
    ui_intelligence_stream_poll_interval: int = Field(5000, description="情报流轮询间隔 (ms)")
    ui_director_panel_max_memories: int = Field(100, description="导演面板最大记忆数")


class DirectorMemoryResponse(BaseModel):
    id: str = Field(..., description="记忆 ID")
    tick_no: int = Field(..., description="创建 tick")
    scene_goal: str = Field(..., description="场景目标", examples=["增加社交活动"])
    priority: str = Field(..., description="优先级", examples=["high", "medium", "low"])
    urgency: str = Field(..., description="紧急度", examples=["immediate", "normal", "scheduled"])
    message_hint: str | None = Field(None, description="消息提示")
    target_agent_id: str | None = Field(None, description="目标 agent ID")
    target_agent_name: str | None = Field(None, description="目标 agent 名称")
    target_agent_ids: list[str] = Field(default_factory=list, description="目标 agent IDs")
    target_agent_names: list[str] = Field(default_factory=list, description="目标 agent 名称列表")
    location_hint: str | None = Field(None, description="地点提示")
    location_name: str | None = Field(None, description="地点名称")
    reason: str | None = Field(None, description="原因说明")
    was_executed: bool = Field(..., description="是否已被本轮 tick 消费")
    delivery_status: str = Field(
        ...,
        description="聚合投递与效果状态",
        examples=["queued", "active", "evaluating", "succeeded", "failed", "expired"],
    )
    effectiveness_score: float | None = Field(None, description="效果分数", ge=0, le=1)
    trigger_subject_alert_score: float = Field(0.0, description="触发主体告警度", ge=0, le=1)
    trigger_continuity_risk: str = Field("stable", description="触发连续性风险")
    cooldown_ticks: int = Field(0, description="冷却 tick 数", ge=0)
    cooldown_until_tick: int | None = Field(None, description="冷却结束 tick")
    created_at: datetime = Field(..., description="创建时间")


class DirectorMemoriesResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    memories: list[DirectorMemoryResponse] = Field(default_factory=list, description="记忆列表")
    total: int = Field(0, description="总数", ge=0)


class DirectorDirectiveResponse(BaseModel):
    id: str = Field(..., description="指令 ID")
    target_agent_id: str = Field(..., description="执行角色 ID")
    target_agent_name: str | None = Field(None, description="执行角色名称")
    subject_agent_id: str | None = Field(None, description="交互目标角色 ID")
    subject_agent_name: str | None = Field(None, description="交互目标角色名称")
    objective: str = Field(..., description="导演目标")
    mode: str = Field(..., description="控制模式")
    priority: str = Field(..., description="优先级")
    status: str = Field(..., description="生命周期状态")
    issued_tick: int = Field(..., description="下发 tick")
    expires_at_tick: int = Field(..., description="过期 tick")
    completed_tick: int | None = Field(None, description="完成 tick")
    location_id: str | None = Field(None, description="目标地点 ID")
    location_name: str | None = Field(None, description="目标地点名称")
    message_hint: str | None = Field(None, description="导演提示")
    constraints: dict = Field(default_factory=dict, description="执行约束")
    completion_criteria: dict = Field(default_factory=dict, description="完成条件")
    source: str = Field(..., description="指令来源")
    source_memory_id: str | None = Field(None, description="关联导演记忆 ID")
    disposition: str | None = Field(None, description="Actor 回执")
    failure_reason: str | None = Field(None, description="失败或取消原因")
    attempt_count: int = Field(0, description="执行尝试次数", ge=0)
    last_attempt_tick: int | None = Field(None, description="最后尝试 tick")
    last_progress_tick: int | None = Field(None, description="最后有效进展 tick")
    last_result_action_type: str | None = Field(None, description="最后动作类型")
    last_result_target_agent_id: str | None = Field(None, description="最后动作目标")
    replaced_by_directive_id: str | None = Field(None, description="替代指令 ID")
    effect_status: str = Field("pending", description="效果评估状态")
    effectiveness_score: float | None = Field(None, description="延迟效果分数", ge=0, le=1)
    evaluated_tick: int | None = Field(None, description="效果评估 tick")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class DirectorDirectivesResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    directives: list[DirectorDirectiveResponse] = Field(default_factory=list)
    total: int = Field(0, ge=0)


class WorldSnapshotResponse(BaseModel):
    run: WorldSnapshotRunResponse = Field(..., description="运行信息")
    world_clock: WorldClockResponse = Field(..., description="世界时钟")
    tick: int = Field(..., description="Godot 客户端使用的当前权威 tick", ge=0)
    world_time: str = Field(..., description="Godot 客户端使用的权威 ISO 世界时间")
    run_status: str = Field(..., description="Godot 客户端使用的运行状态")
    simulation_speed: float = Field(
        1.0,
        description="Godot 客户端使用的世界时间倍率",
        ge=0.25,
        le=8.0,
    )
    map_id: str | None = Field(None, description="Godot 地图稳定 ID")
    map_content_hash: str | None = Field(None, description="地图内容哈希")
    subject_agent_id: str | None = Field(None, description="当前场景主体 agent ID")
    agents: list[AgentSummaryResponse] = Field(default_factory=list, description="完整 Agent 列表")
    locations: list[WorldLocationResponse] = Field(default_factory=list, description="地点列表")
    navigation: WorldMapTopologyResponse = Field(
        default_factory=WorldMapTopologyResponse,
        description="后端权威道路拓扑",
    )
    object_states: list[WorldObjectStateResponse] = Field(
        default_factory=list,
        description="交互资源的权威占用与队列状态",
    )
    conversations: list[dict] = Field(default_factory=list, description="Godot 对话表现状态")
    recent_events: list[WorldEventResponse] = Field(default_factory=list, description="最近事件")
    director_stats: WorldDirectorStatsResponse = Field(
        default_factory=WorldDirectorStatsResponse, description="导演统计"
    )
    daily_stats: WorldDailyStatsResponse = Field(
        default_factory=WorldDailyStatsResponse, description="每日统计"
    )
    health_metrics_config: WorldHealthMetricsConfig = Field(
        default_factory=WorldHealthMetricsConfig, description="健康度配置"
    )
    ui_config: WorldUiConfigResponse = Field(
        default_factory=WorldUiConfigResponse,
        description="世界 UI 配置",
    )


class WorldPulseResponse(BaseModel):
    run: WorldSnapshotRunResponse = Field(..., description="运行信息")
    world_clock: WorldClockResponse = Field(..., description="世界时钟")
    daily_stats: WorldDailyStatsResponse = Field(
        default_factory=WorldDailyStatsResponse, description="每日统计"
    )
