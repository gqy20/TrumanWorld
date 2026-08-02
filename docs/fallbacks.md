# TrumanWorld 兼容与降级机制盘点

> 代码审计基线：当前工作树（2026-08-03）。本文以当前实现为准，区分“运行时降级”、
> “历史协议兼容”和“普通默认值”，避免把所有 `default` 都误认为 fallback。

## 1. 结论摘要

当前项目的兼容与降级设计覆盖了认知后端、场景配置、持久化、API/CLI、实时数据和前端渲染。
整体策略可以概括为：

- **Actor LLM fail-closed**：LangGraph 或 Claude SDK 的居民决策失败时，不自动伪造规则行为；
  上游不可用会继续抛出，避免把“模型离线”伪装成“居民自主决策”。
- **Heuristic Actor 可降级**：只有显式选择 heuristic backend 时，单个居民决策异常、日计划或反思异常
  才允许使用场景规则或跳过失败项。
- **Director fail-open**：自动导演规划异常时，协调器会退回 `director.yml` 的规则策略；
  LangGraph 导演还会修复不可用的目标角色。
- **配置和数据向后兼容有明确边界**：保留提示词、LLM 计量字段、导演历史关联和 repository
  导入路径；仓库内已完成迁移的场景字段和 CLI 命令别名已移除。
- **前端以“保留可用画面”为目标**：SSE 与轮询/快照合并，旧世界快照可重建 Agent，
  GLB、头像、导航和布局缺失时都有视觉替代。
- **数据库兼容主要服务测试与本地运行**：PostgreSQL 使用跨进程 advisory lock；非 PostgreSQL
  仅使用进程内锁。SQLite 是测试兼容层，不具备生产等价语义。

当前最需要治理的不是增加更多 fallback，而是让已有 fallback **可见、可控、可测试、可退场**。
优先问题包括：导演捕获范围过宽、前端 SSE 断线没有显式状态、部分视觉降级缺少遥测、
仍在使用的兼容机制需要继续补齐退场条件。

## 2. 分类标准

| 类型 | 定义 | 本文标记 |
|---|---|---|
| 运行时降级 | 主路径失败后切换到能力更弱但可继续工作的路径 | `fallback` |
| 能力协商 | 根据 provider、数据库或浏览器能力预先选择实现 | `capability` |
| 历史兼容 | 继续接受旧字段、旧格式、旧导入路径或旧命令 | `compat` |
| 安全默认 | 输入缺失时使用确定值，但没有发生主路径失败 | `default` |
| 最佳努力 | 辅助功能失败不阻断核心事务 | `best-effort` |

本文不会把 `energy=0.75`、`tick_minutes=5` 等普通业务默认值逐一列为 fallback。

## 3. 认知系统与 LangGraph

### 3.1 Actor：结构化输出退回文本 JSON

**类型：** `fallback` + `capability`

入口位于 `backend/app/cognition/langgraph/agent_backend.py`：

1. `langgraph_reactor_structured_enabled=true` 时优先调用模型原生 `with_structured_output()`。
2. provider 不接受 `method="json_schema"` / `include_raw=True` 时，捕获 `TypeError`，改用较旧的
   `with_structured_output(schema)` 签名。
3. 原生结构化路径返回解析失败、字段不完整、动作不在允许集合中，或 `talk` 缺少目标/消息时，
   退回“仅返回一个 JSON 对象”的文本提示路径。
4. 文本路径仍不可解析时抛出异常，不再生成 `rest` 等伪造结果。

可观测性已经覆盖该路径：

- 日志事件：`langgraph_model_fallback`、`langgraph_reactor_path_completed`；
- 指标：`trumanworld_langgraph_fallback_total`；
- LLM 调用记录：`status`、`failure_reason`、`fallback_from=structured`、`attempt_no`。

边界与风险：

- 结构化路径的普通非 `RuntimeError` 异常会落入文本路径；上游不可用异常会先转换为
  `UpstreamApiUnavailableError`，不会被吞掉。
- LangGraph 节点最多尝试 2 次；Actor 的 retry predicate 只重试 `RuntimeError`，属于对无效输出的有限恢复，
  不是无限重试。
- `langgraph_reactor_structured_enabled` 当前默认关闭，因此生产是否实际使用该 fallback 取决于部署配置。

### 3.2 LangChain/provider API 兼容

**类型：** `compat` + `capability`

`backend/app/cognition/langgraph/agent_backend.py` 兼容了多种模型包装形态：

- LangGraph `Runtime.execution_info` 通过 `getattr` 读取；缺失时按第 1 次尝试处理；
- LangChain `Runnable` 支持传入 tracing config，最小协议实现只调用 `ainvoke`；
- 模型响应既可为字符串，也可为 message、文本 block 列表或结构化 wrapper；
- Anthropic 与 OpenAI 的 usage/cache/reasoning token 字段由
  `backend/app/sim/llm_call_collector.py` 归一化；
- `notify_llm_call()` 会检查 callback 签名，只把旧五参数 hook 能接受的字段传入，
  同时允许新 callback 接收完整 trace 字段。

`backend/app/cognition/langgraph/model_factory.py` 对可选 provider 包提供延迟失败：缺少
`langchain_anthropic` 或 `langchain_openai` 时模块仍可导入，实际构建模型时记录
`langgraph_model_construction_failed` 并返回 `None`。真正调用时会抛出
`UpstreamApiUnavailableError`，而不是切到另一 provider。

### 3.3 提示词格式兼容

**类型：** `compat`

Actor prompt 优先识别当前的 `# 动态决策上下文` 分隔符；若不存在，则识别旧格式
`# 运行上下文` + JSON code fence；两者都没有时使用 invocation 中的结构化 context。
这保证旧 Agent prompt 不必与 LangGraph 接入同步迁移。

风险是旧 marker 依赖精确文本匹配。长期应给 prompt 模板增加显式版本，而不是继续扩展字符串探测。

### 3.4 Actor 后端选择与失败语义

**类型：** `capability`，不是自动 failover

`backend/app/cognition/registry.py` 根据 `TRUMANWORLD_AGENT_BACKEND` 构建
`heuristic`、`claude_sdk` 或 `langgraph` 后端。三者是部署时选择，不形成运行时链式切换。

`backend/app/sim/tick_orchestrator.py` 的规则恢复只在 backend 是 `HeuristicAgentBackend` 时开启：

- 场景 fallback 优先尝试与附近居民交谈；
- 有导演位置提示时移动到目标地点；
- 否则回家；
- 最终执行 `rest`。

LangGraph/Claude SDK 的普通决策异常会终止该次 tick；`UpstreamApiUnavailableError` 始终直接上抛，
scheduler 收到后会立即暂停 run。该行为是固定语义，不再暴露无消费者的配置开关。

这项不对称是合理的：heuristic 本身就是确定性模拟模式，而 LLM backend 代表居民自主性，
静默切换会污染实验结果。

### 3.5 日计划与反思

**类型：** 条件式 `best-effort`

`backend/app/sim/day_boundary.py` 对 heuristic backend 使用 `asyncio.gather(...,
return_exceptions=True)`，单个 Agent 的 planner/reflector 失败会记录 warning 并跳过该 Agent；
LLM backend 遇到任一异常则继续抛出。

因此“某个居民缺少当天计划/反思但世界继续运行”只属于 heuristic 模式，不是 LangGraph 生产降级。

### 3.6 Claude SDK 连接模式

**类型：** `capability`

Claude SDK reactor pool 已预热时复用连接，否则使用 query 模式启动新进程。
这是连接能力路由，不是“池调用失败后自动转 query”；不要在运维上把它当作故障切换保证。

## 4. 导演系统

### 4.1 导演规划异常退回规则策略

**类型：** `fallback`

`backend/app/scenario/bundle_world/coordinator.py` 在自动导演构建计划时捕获 planner 的所有
`Exception`，记录 `director_planner_fallback`，随后调用 `DirectorPlanner._build_config_based_plan()`，
使用 `director.yml` 的条件与动作生成计划。已经采集到的 LLM 调用记录仍在 `finally` 中持久化。

这与 `DirectorPlanner` 自身的策略不同：planner 只会在 backend 本来就是
`HeuristicDirectorBackend` 时正常使用规则策略；LLM backend 的异常降级由外层 coordinator 统一执行。

风险：

- 捕获范围包含代码缺陷、数据错误和上游不可用，可能把真实 bug 隐藏成一次合法导演干预；
- 日志有 fallback 事件，但目前没有独立的 director-fallback Prometheus counter；
- 规则计划可能与失败前的 LLM 意图完全不同，回放时必须结合日志与 LLM call 状态解释。

建议只降级已分类的上游/输出错误；编程错误应 fail-closed。至少新增
`trumanworld_director_fallback_total{backend,reason}` 和规则计划的 `fallback_reason` 持久化字段。

### 4.2 LangGraph 导演目标修复

**类型：** `fallback`

`backend/app/cognition/langgraph/director_backend.py` 的图为：候选筛选 → 模型提案 → 校验 → 目标修复。
模型返回不存在或不可用的 target 时，`repair_target` 会将目标替换为当前候选列表的第一个角色，
并以 `outcome=repaired` 记录导演决策指标。

这能维持控制闭环，但属于语义改变。更稳妥的后续方案是让修复节点基于 scene goal、位置和可用性打分，
并在 directive 中保存原目标与修复原因。

### 4.3 导演配置与 prompt 多级回退

**类型：** `fallback` + `compat`

`backend/app/scenario/runtime/director_config.py` 的配置解析顺序是：

1. 当前场景 bundle 的 `director.yml`；
2. manifest 标记的默认场景的 `director.yml`；
3. 旧内置路径 `backend/app/scenario/bundle_world/director.yml`；
4. 文件缺失或 YAML 解析失败时使用 `DirectorConfig` 数据类默认值。

prompt 缺失时另有内置英文 prompt。该路径有 warning/error 日志，但默认配置仍可能使导演保持 enabled，
因此配置缺失不等于功能关闭。生产环境建议对“当前场景缺少导演配置”提供 strict 模式。

### 4.4 历史导演记忆与新 directive 关联

**类型：** `compat`

新 directive 使用 `source_memory_id` 关联导演记忆。旧数据没有该字段时，
`backend/app/api/routes/run_director.py` 会按 scene goal、目标 Agent 和相差不超过 1 tick 进行近似匹配，
从而继续展示执行状态。

该兼容是启发式的：同一 tick 对同一 Agent 发出多个同目标计划时可能误关联。它应只作为迁移窗口，
待历史数据回填后删除。

## 5. 场景与 Agent 配置兼容

### 5.1 场景 manifest 严格字段

**类型：** 当前契约

manifest 只读取 `adapter`，能力开关只读取 `subject_alert_tracking`。旧字段
`runtime_adapter`、`alert_tracking` 已在仓库场景和测试中迁移后删除。Pydantic 模型仍对额外字段使用
`extra="ignore"`，所以未知扩展不会阻断当前版本加载；代价是拼写错误也可能被静默忽略。

### 5.2 场景 adapter 与默认场景

**类型：** `compat` + `default`

- bundle 场景统一使用 `bundle_world` adapter，`narrative_world` 只保留为默认场景 ID；
- 默认场景优先取 manifest 的 `default: true`，其次取旧 ID `narrative_world`，最后取按目录排序的第一个；
- 完全没有 bundle 时仍返回旧默认 ID `narrative_world`；
- 场景专属 `agents/` 不存在时退回仓库根目录的 `agents/`。

注意：manifest 无效会直接抛错，registry 不会跳过坏 bundle；“取第一个 bundle”也可能让部署结果受目录命名影响。

### 5.3 Agent 初始配置

**类型：** 当前契约

`backend/app/agent/config_loader.py` 统一读取 `status.alert_score`、`spawn.goal` 和
`spawn.location`。旧的顶层初始位置/目标与 `status.suspicion_score` 输入别名已删除。状态与初始计划
仍允许额外字段，便于场景扩展，同样存在错别字被保留却不生效的风险。

### 5.4 Settings 环境变量迁移

**类型：** `compat` + `default`

`backend/app/infra/settings.py` 会把空字符串标准化为 `None`，并支持 Anthropic 旧配置向通用 LLM 配置迁移：

- `TRUMANWORLD_ANTHROPIC_MODEL` 可补全 `TRUMANWORLD_LLM_MODEL`；
- Anthropic provider 下，`TRUMANWORLD_LLM_API_KEY` / `TRUMANWORLD_LLM_BASE_URL`
  与 Anthropic 专用字段相互补全。

它不会在 Anthropic 与 OpenAI 之间自动切换。开发环境缺少数据库 URL 时使用本地 PostgreSQL；
非开发环境缺少数据库或 demo 管理密码会启动失败，这是安全边界，不应改成降级。

## 6. 数据库、事务与可观测性

### 6.1 PostgreSQL 与 SQLite/其他方言

**类型：** `capability`

| 能力 | PostgreSQL | 非 PostgreSQL（主要为测试 SQLite） |
|---|---|---|
| 同一 run 的 tick 锁 | transaction-scoped advisory lock，可跨进程 | 进程内 `asyncio.Lock` |
| 世界快照读取 | 多个隔离 session 并行查询 | 同一 session 顺序查询 |

实现分别位于 `backend/app/sim/tick_lock.py` 和
`backend/app/api/services/world_snapshot_loader.py`。

非 PostgreSQL 锁只保证单进程安全，多 worker/多实例会失效；因此 SQLite 支持应明确视作测试兼容，
而不是可替代的生产数据库。PostgreSQL engine 还启用了 `pool_pre_ping` 与 300 秒 recycle，
用于降低托管数据库空闲 TLS 连接失效造成的首次请求错误；这是连接韧性，不是数据库 failover。

### 6.2 LLM 调用记录最佳努力持久化

**类型：** `best-effort`

`backend/app/sim/llm_call_writer.py` 使用独立 session 写入 LLM telemetry。写入失败时记录
`llm_calls_persist_failed`，不回滚已经完成的模拟或导演决策。

这个事务边界正确保护了核心世界状态，但意味着成本、fallback 和失败分析可能缺记录。
应为该日志配置告警，并增加 dropped-record counter；如果审计完整性是硬要求，则需要 outbox/队列而非继续吞错。

### 6.3 LLM token 字段兼容

**类型：** `compat`

计量采集兼容 Anthropic/OpenAI/LangChain 的多套字段：

- reasoning：`output_token_details.reasoning`、
  `completion_tokens_details.reasoning_tokens`、`reasoning_tokens`；
- cache read：`input_token_details.cache_read`、
  `prompt_tokens_details.cached_tokens`、`cache_read_input_tokens`；
- cache creation：`input_token_details.cache_creation`、
  `cache_creation_input_tokens`、`cache_creation`。

这部分有单元测试，但 provider SDK 仍可能新增字段。未知格式目前会记为 0，而不是标记“无法解析”。

### 6.4 生命周期最佳努力清理

**类型：** `best-effort`

`backend/app/main.py` 在启动时尝试把遗留的 running run 重置为 paused；失败只记录 `startup_error`，
服务仍会启动。关闭时停止 scheduler、清理 cognition pool 也分别捕获异常并记录 `shutdown_error`。

这提高了服务可用性，但数据库不可用时仍启动可能让 readiness 与真实业务可用性不一致，
应由健康检查明确区分“进程存活”和“数据库可服务”。

## 7. API、CLI 与模块导入兼容

### 7.1 API 查询参数与响应演进

**类型：** `compat`

- Director directives 的 Python 参数 `directive_status` 对外仍使用查询参数 `status`；
- 当前 OpenAPI 已移除旧 director schema 字段，说明这里不是无限兼容所有旧客户端；
- 未知前端事件类型会使用通用图标与事件类型文本展示，不会让时间线崩溃；
- speaker 名称缺失时依次尝试 name、ID 映射、非 UUID ID、调用方 fallback，最后显示“某人”。

### 7.2 CLI 命令与配置优先级

**类型：** `compat` + `default`

- 确定性推进统一使用 `truman run step`；旧的 `truman run tick` 别名已删除；
- CLI 配置优先级为命令行参数 → 环境变量 → TOML profile → 内置默认值；
- 缺少配置文件会使用默认 profile 与 `http://127.0.0.1:18080/api`，配置文件损坏则明确报错，
  不静默忽略。

### 7.3 Repository 导入门面

**类型：** `compat`

`backend/app/store/repositories.py` 继续从拆分后的 `repository_modules/` 重导出全部 repository，
旧的 `from app.store.repositories import ...` 无需修改。这是稳定公共导入面，已有导出完整性测试。

## 8. 前端实时数据与渲染降级

### 8.1 SSR/SWR 快照保留

**类型：** `fallback` + `best-effort`

`frontend/components/world-context.tsx` 与 `runs-provider.tsx` 把服务端初始数据作为 SWR
`fallbackData`，revalidate 时保留上一份数据；瞬时请求错误期间根据最后一次正常的 run 状态继续轮询，
避免页面闪空或停止刷新。

### 8.2 SSE、轮询与快照事件合并

**类型：** `capability` + `fallback`

- 浏览器支持 `EventSource` 时订阅增量 world event；不支持时跳过 SSE，世界快照仍按 15 秒、pulse 按 5 秒轮询；
- streamed events 与 snapshot `recent_events` 按 ID 去重合并；
- 情报流独立增量 API 失败时保留已有事件；首次加载失败则使用 world snapshot 中的 recent events。

当前缺口是 EventSource 没有 `onerror` 状态、退避策略或“实时连接已降级”提示。虽然 SWR 轮询能最终更新快照，
用户无法知道实时性已经降低，且 SSE 恢复后的缺口完全依赖快照/event API 补齐。

### 8.3 旧世界快照

**类型：** `compat`

`frontend/lib/world-scene-adapter.ts` 优先使用顶层 `world.agents`；旧快照没有该字段时，从每个 location 的
`occupants` 聚合并按 Agent ID 去重。对应行为有单元测试。

### 8.4 3D/WebGL 与资产替代

**类型：** `fallback`

- React Three Fiber Canvas 无法创建时显示“切换到导演地图”的静态提示；
- ready GLB 加载失败、没有 mesh 或仍在加载时，使用预先生成的 voxel blocks；
- 资产 promise 失败后从缓存移除，后续允许重试；
- 缺少 navigation entrance 时根据 location 坐标寻找不冲突的网格中心；
- 未知 location type 使用确定性的 fallback plot；重复类型位置会错位展开；
- 缺少事件路线时使用预计算 anchor；
- 2D sprite manifest 缺少 tile/prop/status 映射时使用内置 frame；
- 自定义 Agent SVG 加载失败时使用以 Agent ID 为 seed 的 DiceBear 头像；
- `VOXEL_MATERIAL_COLORS` 保留为旧 instance/planning 代码的兼容视图。

这些视觉降级大多没有统一遥测。当前只有头像用 `console.log`，GLB 加载失败被静默处理。
建议统一上报 `frontend_fallback`，至少包含 `kind`、asset URI、run ID 和浏览器能力；同一 URI 要限频。

### 8.5 分析指标的数据缺失兼容

**类型：** `fallback`

`frontend/lib/world-insights.ts` 在缺少 daily stats 时用 recent talk/speech events 估算社交活跃度；
告警值依次读取 `alert_score`、`anomaly_score`、`suspicion_score`。这种展示兼容保证旧数据可看，
但估算窗口与完整日统计不等价，UI 应标识“估算”以免用户做错误比较。

## 9. 明确不存在的 fallback

以下边界容易被误解，当前代码**不会**自动处理：

- LangGraph/Claude Actor 失败不会切换到 heuristic，也不会自动生成 `rest`；
- Anthropic 失败不会自动切到 OpenAI，反之亦然；
- PostgreSQL 不可用不会切到 SQLite，Redis 配置存在也不是数据库替代；
- 非开发环境缺少数据库 URL 或 demo 管理密码不会使用不安全默认值；
- 无效场景 manifest、未知 scenario adapter 不会被跳过或替换；
- CLI 配置 TOML 损坏不会静默使用默认配置；
- GLB 降级只保证视觉继续显示，不保证高保真模型材质、碰撞或尺寸完全一致；
- SSE 无法使用时没有独立的完整事件流协议，主要依靠周期性 world snapshot/event query 补偿。

## 10. 风险与优化优先级

| 优先级 | 改进项 | 原因 | 建议验收 |
|---|---|---|---|
| P0 | 收窄导演 fallback 异常范围 | 当前可能掩盖代码/数据缺陷 | 只对上游不可用、超时、无效输出降级；其他异常使 tick 可诊断失败 |
| P0 | 为所有降级建立统一事件模型 | 当前日志、指标、DB 字段和前端 console 分散 | 每次 fallback 有 `from`、`to`、`reason`、run/tick/trace、结果 |
| P1 | SSE 显式状态与 gap recovery | 当前用户不知道已退回轮询 | UI 显示连接状态；重连携带 last event/tick；测试丢包与恢复 |
| P1 | LLM telemetry 丢失告警 | best-effort 写失败会造成审计盲区 | dropped counter、告警、可选 outbox 重放 |
| P1 | strict scenario/director config | 多级默认可能掩盖部署漏文件 | production strict 模式启动或创建 run 时校验完整 bundle |
| P1 | 区分真实值与估算值 | world insights fallback 可能误导 | API/UI 增加 `data_quality=exact|estimated|stale` |
| P2 | 兼容项登记退场版本 | 剩余兼容仍可能永久积累 | 每项增加 introduced/deprecate/remove 版本和使用计数 |
| P2 | 前端资源 fallback 遥测 | GLB/头像/布局问题当前不可量化 | 限频上报并按资源、浏览器、版本聚合 |
| P2 | SQLite 能力边界固化 | 进程锁容易被误当生产安全 | 文档、启动检查及多 worker 测试明确仅限开发/测试 |
| P3 | prompt 显式 schema version | marker 探测脆弱 | prompt metadata 声明版本，集中迁移器负责升级 |

## 11. 建议的统一 fallback 契约

后续新增降级机制时，建议统一记录以下字段：

```text
fallback_id       唯一 ID
timestamp         UTC 时间
simulation_run_id 可空
tick_no           可空
trace_id          可空
component         actor | director | persistence | api | frontend
operation         例如 reactor_decide / load_world_asset
from_path         原主路径
to_path           替代路径
reason_code       稳定、低基数枚举
exception_type    可空，不写敏感异常正文
result            recovered | degraded | failed
semantic_change   是否改变业务语义
```

规则：

1. 安全、权限、数据一致性错误不得 fail-open。
2. fallback 必须有界：限制重试次数、持续时间或影响范围。
3. 降级路径必须能单独测试，也要测试恢复回主路径。
4. 用户可感知的质量下降必须在 UI/CLI 明示。
5. 历史兼容必须声明移除条件；没有消费量证据时不删除。
6. “返回默认值”不能掩盖 unknown，应同时携带数据质量或原因。

## 12. 现有测试证据

当前关键兼容行为已有以下测试覆盖：

- `backend/tests/cognition/test_langgraph_agent_backend.py`：structured → text JSON、重试、
  不暴露 heuristic hook；
- `backend/tests/cognition/test_langgraph_observability.py`：两条模型路径及 `fallback_from`；
- `backend/tests/sim/test_service_isolated_prepare_intents.py`：按 backend 控制单 Agent fallback；
- `backend/tests/sim/test_scenarios.py`：场景 fallback policy 与可替换模块；
- `backend/tests/sim/test_llm_call_collector.py`：旧 cache token 字段；
- `backend/tests/sim/test_llm_call_writer.py`：telemetry best-effort；
- `backend/tests/scenario/test_bundle_registry.py`、`test_factory_registry.py`：默认场景与当前 adapter/capability；
- `backend/tests/store/test_repository_module_exports.py`：repository 兼容门面；
- `frontend/lib/__tests__/world-scene-adapter.test.ts`：旧 snapshot occupant 聚合；
- `frontend/components/__tests__/use-world-event-stream.test.ts`：SSE 事件解析与合并；
- `frontend/components/voxel/__tests__/scene-plan.test.ts`：GLB placement 保留 voxel fallback。

仍建议补充：导演异常分类、SSE 断线补洞、GLB 加载失败遥测、strict config、SQLite 多进程边界
以及剩余兼容机制的弃用统计测试。
