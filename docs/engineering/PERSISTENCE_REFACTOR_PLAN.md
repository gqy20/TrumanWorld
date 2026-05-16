# Persistence Refactor Plan

本文档记录当前 persistence / simulation tick 相关重构的整体思路、已完成拆分、后续拆解方向和验证标准。

## 1. 背景

当前项目的 simulation tick 写入链路已经具备可运行闭环，但存在几个工程上不够优雅的点：

- 事务边界分散：service、persistence manager、repository、scenario state updater 中都可能触发写入或提交。
- repository 责任混合：部分方法既负责 add / flush，又负责 commit，导致上层难以组合成原子操作。
- tick 流程过长：`SimulationService.run_tick` 同时承担读取 run、加载 world、调度 planner、执行 tick、写入结果、触发 day boundary 等职责。
- persistence 关注点交织：事件、记忆、关系、治理记录、经济状态、场景状态更新混在同一类或同一调用链中。
- 测试能覆盖业务结果，但过去对失败回滚、半写入、防重复提交等边界保护不足。

本轮重构目标不是一次性重写架构，而是通过 TDD 小步拆分，把核心写入路径逐步变成可组合、可回滚、可验证的结构。

## 2. 重构原则

- TDD 优先：每个风险点先补失败测试，再改实现。
- 小步提交：每次只收敛一个事务边界或一个模块职责。
- Repository 分层：保留 `create*` 这类自提交方法给简单调用场景，同时提供 `add*` / `set*` / `*_no_commit` 给上层事务组合。
- 上层拥有事务：跨多个 repository / service / scenario updater 的写入由上层统一控制事务。
- 不做无关重写：避免在事务重构中混入命名、目录、风格等大规模清理。
- 每步可回滚：每次变更都要有明确测试证明行为。
- 提交信息遵循 Conventional Commits，例如 `refactor(persistence): ...`、`test(sim): ...`、`docs(engineering): ...`。

## 3. 已完成拆分

### 3.1 API helper 与 repository 模块拆分

已将部分过大的 API helper / repository 文件拆出模块，降低单文件复杂度。

收益：

- 查找具体 repository 行为更直接。
- 后续可以在单个 repository 上补事务友好方法。
- 减少 persistence manager 对庞大 repository 文件的隐式依赖。

### 3.2 `PersistenceManager.persist_tick_results` 原子化

已将 tick result 写入放进事务边界。

覆盖范围：

- agent location / goal 同步
- run tick 更新
- event 写入
- governance record 写入
- governance case 写入
- economic state 写入
- memory 写入
- relationship 写入

关键变化：

- 新增 repository 的 no-commit / add / set 方法。
- `persist_tick_results` 在无外部事务时创建事务；已有事务时复用当前事务。
- 失败时 event 和 run tick 不再半写入。

验证：

- 新增失败回滚测试。
- 后端全量测试通过。

### 3.3 `TickEventWriter.persist` 原子化

已将 tick event writer 的事件、记忆、关系、场景状态更新纳入同一事务。

覆盖范围：

- event 写入
- memory 写入
- relationship 写入
- `scenario.update_state_from_events`

关键变化：

- event 写入从 `create_many()` 改为事务内 `add_many()`。
- writer 复用当前 session 事务，无事务时创建事务。
- `BundleWorldScenario.update_state_from_events()` 调用 no-commit 的 state updater 入口，由调用方控制 commit / rollback。

验证：

- 新增 `backend/tests/sim/test_tick_event_writer.py`。
- 测试证明 memory 写入失败时不会残留 event，也不会继续调用 scenario state update。
- 测试证明 scenario state update 失败时，event / memory / relationship 一起回滚。
- 后端全量测试通过。

### 3.4 `SimulationService.run_tick` 写入阶段拆分

已抽出 `TickPersistenceCoordinator`，让 `SimulationService` 不再直接串联 agent location、run tick 和 event writer 的写入细节。

覆盖范围：

- agent location 更新
- run tick 更新
- tick event writer

关键变化：

- `PersistenceManager.set_agent_locations()` 提供 no-commit 入口。
- `TickPersistenceCoordinator` 统一处理 tick 写入事务。
- coordinator 复用已有事务，不会提前 commit 外部 pending change。

验证：

- event writer 失败时，run tick 和 agent location 一起回滚。
- agent location 写入失败时，不调用 event writer。
- 已有外部事务时，coordinator 不会预提交外部变更。

### 3.5 Day boundary 写入语义收敛

已将 day boundary 内部主业务写入调整为原子写入，并明确 telemetry 不参与主业务事务。

覆盖范围：

- morning planner 的 `Agent.current_plan`
- morning planner 的 `daily_plan` memory
- evening reflector 的 `daily_reflection` memory
- evening reflector 的 memory promotion
- planner / reflector 的 `LlmCall` telemetry

关键变化：

- daily plan / reflection memory 写入使用 `add_many()`，由 day boundary 写入阶段统一 commit。
- reflection memory 与 memory promotion 合并到同一事务。
- `LlmCallWriter` 明确为 best-effort：持久化失败只记录 warning，不回滚主业务写入。

验证：

- plan memory 写入失败时，`Agent.current_plan` 不会半更新。
- memory promotion 失败时，daily reflection memory 不会半写入。
- LLM telemetry 持久化失败不抛出异常。

### 3.6 Scenario updater 与 seed 语义收敛

已拆分 scenario updater 的 no-commit 入口和独立提交入口，并为 seed 入口补充失败回滚测试。

关键变化：

- `BundleWorldStateUpdater.apply_subject_alert()` 只 flush，不 commit。
- `BundleWorldStateUpdater.persist_subject_alert()` 作为独立提交入口保留。
- `BundleWorldScenario.update_state_from_events()` 使用 no-commit 入口。

验证：

- scenario state update 复用外部事务，不提交外部 pending change。
- bundle seed / open world seed 在最终 commit 失败时不留下半初始化数据。

### 3.7 测试质量清理

已清理 store 层测试中未 await `db_session.commit()` 的 RuntimeWarning。

覆盖文件：

- `tests/store/test_agent_economic_state.py`
- `tests/store/test_economic_effect_log.py`
- `tests/store/test_governance_case.py`

验证：

- 后端全量测试已无 coroutine RuntimeWarning summary。

## 4. 收口状态

### 4.1 `SimulationService.run_tick` 已收敛到协调角色

当前 `run_tick` 仍然负责整体 orchestration：

- 获取 run
- 配置 scenario
- 加载 world
- day boundary planner
- 准备 intents
- 执行 tick
- 调用 `TickPersistenceCoordinator` 写入 tick 结果
- 执行 day boundary coordinator

tick 写入细节已经从 service 中拆出。后续如果继续拆分，应聚焦读取阶段、day boundary 调度阶段或 isolated runner 对齐，而不是再扩大本轮 persistence 重构。

### 4.2 day boundary 写入边界已明确

day boundary 和 tick event 写入不强行放进同一个事务。当前决策：

- tick event 成功后，day boundary 失败不回滚 tick event。
- day boundary 自己内部的主业务写入保持原子性。
- telemetry 是 best-effort。
- daily plan / reflection 使用 metadata `day` 字段做当天幂等判断。

### 4.3 scenario updater 事务规范已落地

state updater 默认不拥有 commit。调用方负责事务边界；独立入口保留显式提交方法。

### 4.4 测试 warning 已清理

后端全量测试不再输出未 await commit 的 RuntimeWarning summary。

## 5. 下一步 TDD 拆解

### Step 1: 明确 `SimulationService.run_tick` 失败语义

状态：已完成。

建议测试：

- event writer 失败时，run tick 不应提前变更。
- agent location 更新失败时，不应写入 event。
- day boundary coordinator 失败时，明确当前期望：回滚 tick 写入，或保留 tick 写入并允许重试。

产出：

- `SimulationService` 的失败行为被测试锁定。
- 为后续抽 `TickPersistenceCoordinator` 提供边界。

### Step 2: 抽出 tick 写入协调器

状态：已完成。

候选名称：

- `TickPersistenceCoordinator`
- `TickWriteCoordinator`
- `TickCommitter`

职责：

- 接收 run、world、tick result、scenario。
- 统一写入 agent locations、run tick、events、memories、relationships、scenario state。
- 暴露一个事务化入口。

不负责：

- 准备 intents。
- 执行 agent runtime。
- 执行 day boundary planner。
- 处理 HTTP / API schema。

### Step 3: 清理 scenario updater 内部 commit

状态：已完成。

目标：

- 将 updater 变成事务友好的纯写入组件。
- 独立调用场景通过外层方法提交。

建议先覆盖：

- subject alert 更新成功时可以被外部事务 commit。
- subject alert 更新失败时外部事务 rollback 能撤销状态变化。

### Step 4: 梳理 day boundary 写入

状态：已完成。

先画出写入清单，再补 TDD。

关注点：

- daily plan 写入
- daily memory 写入
- economic / governance 后续影响
- 是否有幂等标识
- 失败重试是否会重复写入

当前写入清单：

| 阶段 | 写入内容 | 事务语义 | 当前状态 |
|------|----------|----------|----------|
| Morning planner | `Agent.current_plan` | 必须和 daily plan memory 同事务 | 已覆盖 |
| Morning planner | `Memory(memory_type=daily_plan)` | 必须和 `Agent.current_plan` 同事务 | 已覆盖 |
| Morning planner | `LlmCall` telemetry | best-effort，不回滚主写入 | 已确认 |
| Evening reflector | `Memory(memory_type=daily_reflection)` | 必须和 memory promotion 同事务 | 已覆盖 |
| Evening reflector | short / medium memory promotion | 必须和 daily reflection memory 同事务 | 已覆盖 |
| Evening reflector | `LlmCall` telemetry | best-effort，不回滚主写入 | 已确认 |

day boundary 当前决策：

- Planner / reflector 属于 tick 外围任务，失败不回滚已经完成的 tick event 写入。
- day boundary 自己内部的主业务写入必须保持原子性。
- LLM call telemetry 是观测数据，不参与主业务事务；写入失败只记录 warning。
- daily plan / daily reflection 通过 memory metadata 的 `day` 字段做当天存在性判断，短期可以继续作为幂等判断基础。

### Step 5: 清理遗留测试 warning

状态：已完成。

将同步风格的 `db_session.commit()` 改为 `await db_session.commit()`，或按 fixture 约定重写 setup。

目标：

- 全量测试不再产生 coroutine warning。
- 后续事务相关失败更容易定位。

## 6. 验证标准

每个重构提交至少满足：

- 新增或更新能证明行为的测试。
- 相关测试先跑通过。
- 后端全量测试在关键事务边界变更后跑通过。
- `ruff check` 覆盖变更文件。
- `git diff --check` 无空白问题。

推荐命令：

```bash
uv run ruff check backend/app backend/tests
uv run pytest backend/tests/sim/test_tick_event_writer.py -q
uv run pytest backend/tests/sim/test_service_runtime.py -q
uv run pytest
```

当前收口基线：

- 后端全量：`637 passed, 8 skipped`
- warning summary：无 coroutine `RuntimeWarning`

## 7. 风险清单

- SQLAlchemy `session.in_transaction()` 不能简单等价为“当前由业务外层事务托管”，普通查询也可能开启自动事务。
- 内部 `commit()` 会破坏外层 rollback 能力。
- 直接把 day boundary 并入 tick transaction 可能改变失败恢复语义。
- 大范围移动 service 逻辑容易引入行为回归，必须先用测试锁定。
- 事务改造过程中不要删除现有自提交 repository 方法，除非所有调用点都已经迁移。
