# 事件增量查询技术设计

> **状态**: ✅ 已实现 (2026-03-11)
>
> 基于 TDD 流程实现，所有测试通过。

## 背景

当前"情报流弹窗" (`IntelligenceStreamModal`) 每次轮询都会请求全量 500 条事件，即使大部分数据没有变化。这导致：

1. **数据库压力**：每次都执行完整查询
2. **网络带宽**：传输大量重复数据
3. **前端处理**：需要过滤重复事件

## 目标

实现增量查询机制：只获取自上次查询后新增的事件。

## API 设计

### 请求参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `since_tick` | `int` | `null` | 只返回 tick_no > since_tick 的事件 |

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `latest_tick` | `int` | 当前返回事件中的最大 tick，供下次增量查询使用 |

### 使用示例

```bash
# 首次请求（全量）
GET /runs/{id}/events?limit=500
# 响应: { events: [...], total: 500, latest_tick: 100 }

# 增量请求（只获取 tick > 100 的事件）
GET /runs/{id}/events?limit=500&since_tick=100
# 响应: { events: [...], total: 50, latest_tick: 150 }
```

## 实现细节

### 后端修改

#### 1. Repository 层

**文件**: `backend/app/store/repositories.py`

```python
async def list_for_run(
    self, run_id: str, limit: int = 50, since_tick: int | None = None
) -> Sequence[Event]:
    # ... 省略排序逻辑 ...
    stmt = (
        select(Event)
        .where(Event.run_id == run_id)
        .order_by(event_priority, Event.tick_no.desc(), Event.created_at.desc())
        .limit(limit)
    )
    # 增量查询：只获取指定 tick 之后的事件
    if since_tick is not None:
        stmt = stmt.where(Event.tick_no > since_tick)
    result = await self.session.execute(stmt)
    return result.scalars().all()
```

#### 2. Schema 层

**文件**: `backend/app/api/schemas/simulation.py`

```python
class WorldEventsResponse(BaseModel):
    run_id: str
    events: list[WorldEventResponse]
    total: int
    latest_tick: int = 0  # 当前返回事件中的最大 tick，供增量查询使用
```

#### 3. API 层

**文件**: `backend/app/api/routes/runs.py`

```python
@router.get("/{run_id}/events")
async def get_run_events(
    run_id: UUID,
    event_type: str | None = None,
    limit: int = 500,
    since_tick: int | None = None,  # 新增
    session: AsyncSession = Depends(get_db_session),
) -> WorldEventsResponse:
    # ...
    events = await event_repo.list_for_run(str(run_id), limit=limit, since_tick=since_tick)
    # 计算返回事件中的最大 tick
    latest_tick = max((e.tick_no for e in events), default=0)
    return WorldEventsResponse(
        run_id=str(run_id),
        events=result_events,
        total=len(result_events),
        latest_tick=latest_tick,
    )
```

### 前端修改

#### 1. API 层

**文件**: `frontend/lib/api.ts`

```typescript
export async function getRunEventsResult(
  runId: string,
  eventType?: string,
  limit = 500,
  sinceTick?: number,  // 新增
): Promise<ApiResult<{ run_id: string; events: WorldEvent[]; total: number; latest_tick: number }>> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (eventType) params.set("event_type", eventType);
  if (sinceTick != null) params.set("since_tick", String(sinceTick));
  return fetchResult(`/runs/${runId}/events?${params.toString()}`);
}
```

#### 2. 组件层

**文件**: `frontend/components/intelligence-stream-modal.tsx`

```typescript
// Track latest tick for incremental queries
const latestTickRef = useRef<number>(0);

const loadAllEvents = useCallback(async (force = false) => {
  // ...
  const isFirstLoad = knownIdsRef.current.size === 0;
  // Incremental query: pass since_tick for non-first loads
  const sinceTick = force ? undefined : (isFirstLoad ? undefined : latestTickRef.current);
  const result = await getRunEventsResult(runId, undefined, maxEvents ?? 500, sinceTick);

  if (result.data) {
    // Update latest tick from response for next incremental query
    if (result.data.latest_tick != null) {
      latestTickRef.current = result.data.latest_tick;
    }
    // ...
  }
}, [runId, maxEvents, world.recent_events]);

// Reset on fresh open
useEffect(() => {
  if (isOpen && !prevIsOpenRef.current) {
    knownIdsRef.current = new Set();
    latestTickRef.current = 0;  // Reset for full reload
    setAllEvents(world.recent_events);
  }
  prevIsOpenRef.current = isOpen;
}, [isOpen, world.recent_events]);
```

## 测试覆盖

### Repository 层测试

- `test_event_repository_list_for_run_with_since_tick` - 基本增量过滤
- `test_event_repository_list_for_run_since_tick_excludes_equal` - 排他边界
- `test_event_repository_list_for_run_since_tick_none_returns_all` - 向后兼容
- `test_event_repository_list_for_run_since_tick_respects_limit` - limit 与 since_tick 同时生效

### API 层测试

- `test_events_incremental_query_with_since_tick` - API 增量查询
- `test_events_incremental_query_returns_latest_tick` - 响应包含 latest_tick
- `test_events_incremental_query_empty_since_tick` - since_tick 超过最大 tick 时返回空

## 资源消耗对比

| 场景 | 之前（全量） | 现在（增量） | 节省 |
|------|-------------|-------------|------|
| 首次加载 | 500 条 | 500 条 | 0% |
| 后续轮询（无新事件） | 500 条 | **0 条** | **100%** |
| 后续轮询（1 tick/5 事件） | 500 条 | **5 条** | **99%** |

## 配置

轮询间隔在 `world_config.yml` 中配置：

```yaml
health_metrics_config:
  intelligence_stream:
    poll_interval_ms: 3000  # 轮询间隔（毫秒）
```

## 回滚方案

增量查询是**可选参数**，不传时行为与之前完全一致：

- 前端：不传 `since_tick` 即回退到全量查询
- 后端：参数为可选，默认 `None`

## 相关文件

| 层级 | 文件 | 改动 |
|------|------|------|
| Repository | `backend/app/store/repositories.py` | `list_for_run` 添加 `since_tick` 参数 |
| Schema | `backend/app/api/schemas/simulation.py` | `WorldEventsResponse` 添加 `latest_tick` 字段 |
| API | `backend/app/api/routes/runs.py` | 端点添加 `since_tick` 查询参数 |
| Frontend API | `frontend/lib/api.ts` | `getRunEventsResult` 传递 `sinceTick` |
| Frontend Component | `frontend/components/intelligence-stream-modal.tsx` | 追踪 `latestTickRef` |
| Config | `backend/app/scenario/truman_world/world_config.yml` | `poll_interval_ms` 配置 |
