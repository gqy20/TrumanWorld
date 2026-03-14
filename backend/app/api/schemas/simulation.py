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
    scenario_type: Literal["truman_world", "open_world"] = Field(
        default="truman_world",
        description="运行场景类型",
        examples=["truman_world", "open_world"],
    )
    seed_demo: bool = Field(
        default=True,
        description="是否自动填充演示数据（agent、地点等）",
        examples=[True],
    )
    tick_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="每个 tick 代表的分钟数",
        examples=[5],
    )


class RunBaseResponse(BaseModel):
    id: str = Field(..., description="运行 ID", examples=["550e8400-e29b-41d4-a716-446655440000"])
    name: str = Field(..., description="运行名称", examples=["Truman Town"])
    status: str = Field(..., description="运行状态", examples=["running", "paused", "stopped"])
    scenario_type: str = Field(..., description="场景类型", examples=["truman_world", "open_world"])
    current_tick: int = Field(..., description="当前 tick", examples=[42])
    tick_minutes: int = Field(..., description="每 tick 分钟数", examples=[5])
    was_running_before_restart: bool = Field(False, description="服务重启前是否在运行中")
    started_at: datetime | None = Field(None, description="最近一次启动时间（UTC ISO8601）")
    elapsed_seconds: int = Field(0, description="累计运行秒数", ge=0)


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
    total: int = Field(0, description="总事件数", ge=0)
    filtered: int = Field(0, description="过滤后事件数", ge=0)
    run_info: TimelineRunInfo | None = Field(None, description="运行信息")


class DirectorObservationResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    current_tick: int = Field(..., description="当前 tick")
    truman_agent_id: str | None = Field(None, description="Truman agent ID")
    truman_suspicion_score: float = Field(
        ..., description="怀疑度分数", ge=0, le=1, examples=[0.35]
    )
    suspicion_level: str = Field(..., description="怀疑级别", examples=["low", "medium", "high"])
    continuity_risk: str = Field(
        ..., description="连续性风险", examples=["stable", "warning", "critical"]
    )
    focus_agent_ids: list[str] = Field(default_factory=list, description="关注 agent IDs")
    notes: list[str] = Field(default_factory=list, description="观察笔记")


class AgentSummaryResponse(BaseModel):
    id: str = Field(..., description="Agent ID", examples=["agent_alice"])
    name: str = Field(..., description="Agent 名称", examples=["Alice"])
    occupation: str | None = Field(None, description="职业", examples=["咖啡师"])
    current_goal: str | None = Field(None, description="当前目标", examples=["完成早班工作"])
    current_location_id: str | None = Field(None, description="当前位置 ID", examples=["loc_cafe"])
    config_id: str | None = Field(None, description="配置 ID", examples=["alice"])


class AgentsListResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    agents: list[AgentSummaryResponse] = Field(default_factory=list, description="Agent 列表")


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
    total_cache_read_tokens: int = Field(0, description="缓存读取 token 数", ge=0)
    total_cache_creation_tokens: int = Field(0, description="缓存创建 token 数", ge=0)


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
    target_cast_ids: list[str] = Field(default_factory=list, description="目标 cast IDs")
    target_cast_names: list[str] = Field(default_factory=list, description="目标 cast 名称")
    location_hint: str | None = Field(None, description="地点提示")
    location_name: str | None = Field(None, description="地点名称")
    reason: str | None = Field(None, description="原因说明")
    was_executed: bool = Field(..., description="是否已被本轮 tick 消费")
    delivery_status: str = Field(
        ..., description="投递状态", examples=["queued", "consumed", "expired"]
    )
    effectiveness_score: float | None = Field(None, description="效果分数", ge=0, le=1)
    trigger_suspicion_score: float = Field(0.0, description="触发怀疑度", ge=0, le=1)
    trigger_continuity_risk: str = Field("stable", description="触发连续性风险")
    cooldown_ticks: int = Field(0, description="冷却 tick 数", ge=0)
    cooldown_until_tick: int | None = Field(None, description="冷却结束 tick")
    created_at: datetime = Field(..., description="创建时间")


class DirectorMemoriesResponse(BaseModel):
    run_id: str = Field(..., description="运行 ID")
    memories: list[DirectorMemoryResponse] = Field(default_factory=list, description="记忆列表")
    total: int = Field(0, description="总数", ge=0)


class WorldSnapshotResponse(BaseModel):
    run: WorldSnapshotRunResponse = Field(..., description="运行信息")
    world_clock: WorldClockResponse = Field(..., description="世界时钟")
    locations: list[WorldLocationResponse] = Field(default_factory=list, description="地点列表")
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


class WorldPulseResponse(BaseModel):
    run: WorldSnapshotRunResponse = Field(..., description="运行信息")
    world_clock: WorldClockResponse = Field(..., description="世界时钟")
    daily_stats: WorldDailyStatsResponse = Field(
        default_factory=WorldDailyStatsResponse, description="每日统计"
    )
