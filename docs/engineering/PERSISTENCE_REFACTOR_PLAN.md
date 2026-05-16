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
- writer 在事务期间通过 session info 标记受管事务上下文。
- `BundleWorldStateUpdater.persist_subject_alert` 在 writer 受管事务内使用 `flush()`，独立调用时仍保持 `commit()` 语义。

验证：

- 新增 `backend/tests/sim/test_tick_event_writer.py`。
- 测试证明 memory 写入失败时不会残留 event，也不会继续调用 scenario state update。
- 后端全量测试通过。

## 4. 当前核心问题

### 4.1 `SimulationService.run_tick` 仍是最大协调点

当前 `run_tick` 仍然串联了多个阶段：

- 获取 run
- 配置 scenario
- 加载 world
- day boundary planner
- 准备 intents
- 执行 tick
- 写 agent locations
- 更新 run tick
- 写 events / memories / relationships / scenario state
- 执行 day boundary coordinator

问题不在于它“长”，而在于它同时承担 orchestration 和 persistence boundary 的判断。下一步应该把 tick 写入阶段进一步抽出，让 service 更像协调器，而不是写入细节拥有者。

### 4.2 day boundary 写入边界仍需梳理

day boundary 里仍存在直接 repository 写入和自提交行为。它和 tick event 写入在业务上属于同一次 tick 的后续阶段，但是否要放进同一个数据库事务，需要按失败语义拆分：

- 如果 day boundary 失败，是否应该回滚本 tick events？
- 如果 tick events 成功但 day boundary 失败，是否允许稍后重试？
- day boundary planner 和 daily memory 写入是否需要幂等键？

这部分不应直接强行并入同一个事务，需要先补失败语义测试。

### 4.3 scenario updater 的提交语义需要统一

目前 `BundleWorldStateUpdater` 已适配 writer 受管事务，但长期看更理想的形态是：

- scenario updater 只负责修改 session 中的模型。
- 是否 commit / rollback 由调用方控制。
- 必要时保留独立调用入口，例如 `persist_*` 包一层 transaction。

这能避免未来新增 scenario updater 时重新引入内部 commit。

### 4.4 遗留测试 warning 需要清理

当前后端全量通过，但 store 层部分测试存在未 await 的 `db_session.commit()` warning。

这不是本轮事务改动引入的问题，但会降低测试信号质量。建议在事务重构稳定后单独清理。

## 5. 下一步 TDD 拆解

### Step 1: 明确 `SimulationService.run_tick` 失败语义

先补测试，不急着改实现。

建议测试：

- event writer 失败时，run tick 不应提前变更。
- agent location 更新失败时，不应写入 event。
- day boundary coordinator 失败时，明确当前期望：回滚 tick 写入，或保留 tick 写入并允许重试。

产出：

- `SimulationService` 的失败行为被测试锁定。
- 为后续抽 `TickPersistenceCoordinator` 提供边界。

### Step 2: 抽出 tick 写入协调器

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

目标：

- 将 updater 变成事务友好的纯写入组件。
- 独立调用场景通过外层方法提交。

建议先覆盖：

- subject alert 更新成功时可以被外部事务 commit。
- subject alert 更新失败时外部事务 rollback 能撤销状态变化。

### Step 4: 梳理 day boundary 写入

先画出写入清单，再补 TDD。

关注点：

- daily plan 写入
- daily memory 写入
- economic / governance 后续影响
- 是否有幂等标识
- 失败重试是否会重复写入

### Step 5: 清理遗留测试 warning

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

## 7. 风险清单

- SQLAlchemy `session.in_transaction()` 不能简单等价为“当前由业务外层事务托管”，普通查询也可能开启自动事务。
- 内部 `commit()` 会破坏外层 rollback 能力。
- 直接把 day boundary 并入 tick transaction 可能改变失败恢复语义。
- 大范围移动 service 逻辑容易引入行为回归，必须先用测试锁定。
- 事务改造过程中不要删除现有自提交 repository 方法，除非所有调用点都已经迁移。
