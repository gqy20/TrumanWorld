# Truman World 当前架构设计

- 类型：`engineering`
- 状态：`active`
- 负责人：`repo`
- 基线日期：`2026-05-16`

## 1. 系统定位

当前系统是一个面向实验与观测的 AI 社会模拟系统：

- 可持续运行的 AI 小镇仿真器
- 带导演层观察、干预和统计面板的控制台
- 带 scenario 抽象的多题材雏形
- 带运行恢复、timeline、世界健康度、治理留痕、LLM 调用统计的实验系统

> 历史设计文档见 [../references/](../references/)

## 2. 当前后端结构

当前后端模块：

```text
backend/app/
├── api/           # HTTP 路由、查询、控制接口
├── sim/           # tick 编排、world state、调度与持久化主流程
├── agent/         # Agent runtime、prompt、provider、连接池
├── store/         # SQLAlchemy models、repository、持久化
├── scenario/      # 题材抽象层（bundle_world / open_world）
├── director/      # 观察、策略、计划、干预记忆
├── infra/         # settings、logging、db
└── protocol/      # 协议定义
```

核心关系：

- `sim` 负责仿真主流程与 tick 编排
- `agent` 负责认知调用与 prompt/runtime 拼装
- `director` 负责观察、计划、干预策略
- `scenario` 负责题材特定规则和上下文注入
- `store` 负责状态持久化

## 3. 当前前端定位

当前前端已经不只是简单的 run 控制页，而是一个导演控制台：

- run 列表与控制
- 世界地图 / 世界快照
- 时间线与故事流查看
- agent 详情、关系、记忆查看
- director interventions 查看与注入
- 世界健康度、活动分布、统计信息面板
- 已具备部分治理运营入口，但 cases / restrictions / economic summary 的前端整合仍未完成

## 4. 当前已落地的关键能力

- Run 创建、启动、暂停、恢复
- 自动 tick 调度
- timeline / world snapshot / agent detail 查询
- director manual injection
- director automatic planning
- subject alert / continuity risk 观测
- director memories 持久化
- world rules summary / rule feedback / governance feedback 暴露
- governance records / cases / restrictions API
- agent economic summary API
- LLM token 与成本统计
- scenario_type 持久化与按题材运行
- 事件增量查询（since_tick 参数，节省 99% 带宽）

## 5. 后端运行与持久化边界

当前后端 tick 主路径已经拆成三个层次：

```text
SimulationService.run_tick
├── 读取 run / world
├── day boundary planner（tick 决策前，独立外围任务）
├── TickOrchestrator.execute_tick
├── TickPersistenceCoordinator.persist
│   ├── PersistenceManager.set_agent_locations
│   ├── RunRepository.set_tick
│   └── TickEventWriter.persist
│       ├── EventRepository.add_many
│       ├── PersistenceManager.persist_tick_memories
│       ├── PersistenceManager.persist_tick_relationships
│       └── Scenario.update_state_from_events
└── day boundary reflector（tick 写入后，独立外围任务）
```

### 5.1 Tick 写入事务

tick 核心写入由 `TickPersistenceCoordinator` 持有事务边界。

同一事务内完成：

- agent location 更新
- run current_tick 更新
- event 写入
- event-derived memory 写入
- relationship 写入
- scenario state update

失败语义：

- event writer 失败时，run tick 和 agent location 一起回滚。
- agent location 写入失败时，不会继续写 event。
- scenario state update 失败时，event / memory / relationship 一起回滚。
- coordinator 复用已有事务，不会提前 commit 外部 pending change。

### 5.2 Repository 分层约定

repository 方法按提交语义分层：

- `create*` / `update*`：面向简单调用场景，可以自行 commit。
- `add*` / `set*` / `*_no_commit`：面向上层组合事务，只 flush，不 commit。

跨多个 repository 或跨 scenario updater 的写入，必须由上层 coordinator / service / use-case 明确持有事务。

### 5.3 Day Boundary 写入语义

day boundary 不并入 tick event 主事务。当前约定：

- planner / reflector 是 tick 外围任务，失败不回滚已经完成的 tick event。
- day boundary 自身的主业务写入必须保持原子性。
- morning planner 的 `Agent.current_plan` 与 `daily_plan` memory 同事务。
- evening reflector 的 `daily_reflection` memory 与 memory promotion 同事务。
- `LlmCall` telemetry 是 best-effort，写入失败只记录 warning，不回滚主业务。

### 5.4 Scenario State 与 Seed

scenario state updater 默认不拥有 commit。

当前 `bundle_world` 约定：

- `BundleWorldStateUpdater.apply_subject_alert()` 只 flush，不 commit。
- `BundleWorldStateUpdater.persist_subject_alert()` 是独立提交入口。
- `BundleWorldScenario.update_state_from_events()` 使用 no-commit 入口，由 tick writer / coordinator 控制事务。

seed 是独立入口，可以在成功结束时 commit；当前已有测试覆盖 bundle seed / open world seed 在最终 commit 失败时不会留下半初始化数据。

## 6. 当前已知设计张力

当前实现大体可用，但仍存在一些需要后续收敛的点：

- `scenario` 抽象已基本收口，但仍保留少量兼容层与历史命名
- 文档里宣称的 `Redis` / `pgvector` 能力目前更多是预留而非主链路依赖
- API 和前端暴露了不少内部运行与观测细节
- 测试主链路仍以 SQLite 为主，和生产 PostgreSQL 有差距
- 心智模型仍停留在 `mood` / `emotional_valence` / attention 等铺垫信号，尚未形成结构化 `mental_state`
- 后端治理/经济能力比前端运营视图走得更快，产品闭环仍需补齐
- day boundary 当前仍是 inline 外围任务；如果后续需要更强可恢复性，可以演进为独立可重试任务

这部分不影响把系统描述为“当前实现”，但说明它仍处于快速演进阶段。

补充说明：

- `bundle_world` 是当前默认的 bundle-driven 运行时实现
- `narrative_world` 现在只表示默认场景 bundle id，不再是后端实现目录
- 仓库中仍可见的 `TrumanWorld` 文案，当前主要属于品牌层、默认场景内容层或历史文档层，而不再是运行时主路径耦合

## 7. 阅读顺序建议

如果你是第一次进入项目，建议按这个顺序看：

1. [../engineering/DEVELOPMENT.md](../engineering/DEVELOPMENT.md)
2. [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md)
3. [PERSISTENCE_REFACTOR_PLAN.md](PERSISTENCE_REFACTOR_PLAN.md)
4. [roadmap.md](roadmap.md)
5. [../engineering/world_design/IMPLEMENTATION_ROADMAP.md](../engineering/world_design/IMPLEMENTATION_ROADMAP.md)
6. [../product/BACKLOG.md](../product/BACKLOG.md)
7. [../references/SCENARIOS.md](../references/SCENARIOS.md)
