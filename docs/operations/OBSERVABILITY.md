# 可观测性与日志规范

本文定义 TrumanWorld 的日志契约、数据边界和基础排障流程。业务事实以数据库为准；日志用于诊断，指标用于告警，不用日志替代世界事件或 LLM 调用审计。

## 运行配置

开发环境默认使用便于阅读的文本日志：

```bash
TRUMANWORLD_LOG_LEVEL=DEBUG
TRUMANWORLD_LOG_FORMAT=text
```

生产环境必须使用单行 JSON，并保持 `INFO` 或更高等级：

```bash
TRUMANWORLD_LOG_LEVEL=INFO
TRUMANWORLD_LOG_FORMAT=json
```

本地 `make backend-dev` 和 `make frontend-dev` 会将输出写入 `logs/dev_*.log`。需要回收旧文件时显式执行：

```bash
make logs-prune                       # 默认删除 7 天前的开发日志
make logs-prune LOG_RETENTION_DAYS=14
```

Docker Compose 对每个容器限制为 5 个、每个 20MB 的日志文件。生产部署保持 stdout/stderr 输出，由部署平台负责保留和集中检索。

## 后端日志契约

JSON 公共字段：

| 字段 | 含义 |
|------|------|
| `schema_version` | 日志契约版本，当前为 `1` |
| `service` | 服务名，后端为 `trumanworld-backend` |
| `environment` | `development`、`production` 等运行环境 |
| `timestamp` | UTC ISO 8601 时间 |
| `level` | `DEBUG`、`INFO`、`WARNING`、`ERROR` |
| `logger` | 代码模块 |
| `message` | 面向人的简短说明 |
| `event` | 稳定、机器可检索的事件名 |
| `request_id` | 单次 HTTP 请求关联标识 |

按执行场景增加以下字段：

- HTTP：`method`、`route`、`status_code`、`duration_ms`、`db_query_count`、`db_duration_ms`。
- 模拟：`simulation_run_id`（日志上下文仍兼容 `run_id`）、`scenario_id`、`tick_no`、`agent_id`。
- 调度：`component=scheduler`、`run_id`；后台任务不得继承启动它的 HTTP `request_id`。
- 异常：`exception_type` 和受控堆栈。不要把异常对象塞入任意嵌套结构。

`route` 必须使用 `/api/runs/{run_id}` 形式的路由模板，Prometheus label 禁止使用包含实际 ID 的 URL。

## 隐私与安全边界

日志过滤器会递归遮盖 password、secret、token、API key、Authorization、Cookie、Redis URL 和数据库 URL 凭据，但调用方仍需遵守最小记录原则：

- 不记录请求/响应 headers。
- 不记录 LLM prompt、完整 response、居民记忆、人格配置或导演私密内容。
- 不记录 `.env`、数据库连接串和第三方 SDK 配置对象。
- LLM 格式错误只记录任务、agent、响应长度和失败原因。
- 新增敏感字段时同时扩展脱敏单测。

## 前端错误关联

API 客户端读取后端响应的 `x-request-id` 并放入 `ApiResult.requestId`。错误界面将其显示为“问题编号”，排障时使用该编号检索后端日志。请求超时返回 `timeout_error`，连接失败返回 `network_error`。

路由级和全局 React error boundary 会通过统一前端错误记录器输出结构化对象。当前记录器写入浏览器或 Next.js 控制台；接入 Sentry/OpenTelemetry 时应在该入口扩展，不能在各组件散落 SDK 调用。

## 指标

`/api/metrics` 包含以下关键系列：

- `trumanworld_http_request_total`
- `trumanworld_http_request_duration_seconds`
- `trumanworld_tick_total`
- `trumanworld_tick_duration_seconds`
- `trumanworld_database_queries_per_operation`
- `trumanworld_database_duration_seconds`
- `trumanworld_llm_call_total`
- `trumanworld_llm_tokens_total`
- `trumanworld_llm_cost_usd_total`
- `trumanworld_llm_call_duration_seconds`
- `trumanworld_langgraph_run_total`
- `trumanworld_langgraph_node_duration_seconds`
- `trumanworld_langgraph_retry_total`
- `trumanworld_langgraph_fallback_total`

LLM 指标只使用 `backend`、`provider`、`task_type`、`status` 等有限枚举作为 label；
`run_id`、`trace_id`、`agent_id` 等高基数字段只能进入日志和数据库，不能成为 Prometheus label。

## LangGraph 可观测性

Agent reactor 使用 LangGraph 原生 `RunnableConfig` 和 lifecycle callback 记录 graph/node
开始、完成与失败。一次 graph invocation 使用独立的 `graph_run_id`，业务模拟使用
`simulation_run_id`，两者不得混用。`trace_id` 将 graph 生命周期日志与 `llm_calls` 记录关联。

稳定事件包括：

- `langgraph_run_started`、`langgraph_run_completed`、`langgraph_run_failed`
- `langgraph_node_started`、`langgraph_node_completed`、`langgraph_node_failed`
- `langgraph_node_retry_scheduled`、`langgraph_model_fallback`
- `llm_call_observed`、`langgraph_director_started`、`langgraph_director_completed`

`llm_calls` 对成功、失败和无有效输出的模型请求都落审计记录，关键字段包括 `status`、
`trace_id`、`node_name`、`attempt_no`、`exception_type`、`failure_reason` 和
`fallback_from`。失败记录 token 可以为 0；这表示供应商未返回 usage，而不是调用没有发生。
inline 与 isolated tick 都会为 actor reactor 注入同一套采集回调并持久化 `llm_calls`，因此 CLI
成本/Token 保护和 Prometheus 计数不依赖 tick 执行模式。

正常运行不启用 LangGraph `debug` stream，因为完整 state 快照可能包含 prompt、上下文和模型
输出。需要临时诊断时，应在隔离环境中显式启用并遵守上述隐私边界。

推荐告警起点：5 分钟 5xx 比例超过 5%、tick 连续失败、P95 请求或 tick 耗时异常、数据库错误，以及 LLM 错误率或费用突增。阈值应根据稳定运行基线再收紧。

## 基础排障流程

1. 记录界面上的问题编号、run ID、世界 tick 和发生时间。
2. 先按 `request_id` 查 HTTP 请求，再按 `simulation_run_id` 与 `tick_no` 查后台执行。
3. LangGraph 问题再按 `trace_id` 聚合 graph、node 与模型调用，按 `attempt_no` 检查重试顺序。
4. 对照 `/api/metrics` 判断是单请求问题还是系统性延迟/错误。
5. 世界事实、导演干预和 LLM 用量以数据库审计记录为准，不从日志反推业务状态。
6. 若出现未脱敏内容，立即限制日志访问、缩短保留期并补充过滤器回归测试。
