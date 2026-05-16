# Engineering Roadmap

本文档记录近期工程重构路线，重点围绕 persistence、simulation tick、事务边界和测试质量。

## 1. 当前阶段

当前阶段目标：把 simulation tick 的核心写入链路整理成可测试、可组合、可回滚的结构。

已完成：

- repository 拆分，降低单文件复杂度。
- 为 repository 增加事务友好的 `add*` / `set*` / `*_no_commit` 方法。
- `PersistenceManager.persist_tick_results` 事务化。
- `TickEventWriter.persist` 事务化。
- 前端测试修复，恢复 frontend suite 稳定性。
- 提交信息规范写入 `AGENTS.md`。

当前状态：

- 后端全量测试通过：`627 passed, 8 skipped`。
- 前端全量测试最近通过：`19 suites / 99 tests passed`。
- 后端仍有遗留 store 测试 warning，来自未 await 的 `db_session.commit()`。

## 2. Roadmap

### Phase 1: Tick persistence 原子性

状态：基本完成。

目标：

- tick result 写入失败时不留下半写入数据。
- event writer 写入失败时不留下半写入 event。
- repository 支持上层事务组合。

已完成事项：

- `persist_tick_results` 原子化。
- `TickEventWriter.persist` 原子化。
- 相关失败回滚测试补齐。

后续补强：

- 增加更多 scenario state updater 的 rollback 测试。
- 清理仍可能自提交的写入组件。

### Phase 2: `SimulationService.run_tick` 拆分

状态：进行中。

目标：

- 让 `SimulationService` 回到 orchestration 角色。
- 将 tick 写入细节抽到独立 coordinator。
- 明确 run tick、agent location、event、memory、relationship、scenario state 的统一提交边界。

建议 TDD 起点：

- event writer 失败时，run tick 不应提前变更。（已覆盖）
- agent location 写入失败时，不应写入 event。（已覆盖）
- scenario state update 失败时，event / memory / relationship 应一起回滚。

候选产物：

- `backend/app/sim/tick_persistence_coordinator.py`（已创建）
- `backend/tests/sim/test_tick_persistence_coordinator.py`（已创建）

已完成事项：

- 抽出 `TickPersistenceCoordinator` 承接 tick 写入阶段。
- 将 agent location、run tick、event writer 放进同一写入事务。
- 补充 coordinator 独立测试，覆盖 location 写入失败短路和外部已有事务复用。
- 移除 coordinator 内部预提交，避免提前提交外部 pending change。
- 保留 day boundary 作为后续独立语义分析对象，暂不强行并入 tick 写入事务。

### Phase 3: Day boundary 写入语义

状态：待分析。

目标：

- 明确 day boundary 与 tick persistence 的失败恢复关系。
- 防止 daily memory / plan / economic effect 重复写入。
- 为可重试任务建立幂等基础。

关键问题：

- day boundary 失败是否回滚当前 tick？
- day boundary 是否应该成为独立可重试任务？
- 哪些写入需要幂等 key？

建议先做：

- 列出 day boundary 写入清单。
- 补失败测试，锁定当前期望。
- 再决定事务边界。

### Phase 4: Scenario updater 事务规范

状态：部分完成。

目标：

- scenario updater 默认不拥有 commit。
- 调用方负责事务边界。
- 独立调用入口可以保留，但需要显式命名或包装。

已处理：

- `BundleWorldStateUpdater.persist_subject_alert` 已适配 `TickEventWriter` 受管事务。

待处理：

- 检查所有 scenario updater / seed / state 写入路径。
- 将隐式 commit 改为受控 commit。
- 补 rollback 测试。

### Phase 5: 测试质量清理

状态：待处理。

目标：

- 清理后端全量测试 warning。
- 将 store 层测试 setup 改成 async 风格。
- 提升事务测试的失败信号质量。

优先项：

- `tests/store/test_agent_economic_state.py`
- `tests/store/test_economic_effect_log.py`
- `tests/store/test_governance_case.py`

## 3. 执行节奏

每个阶段按这个节奏推进：

1. 先写失败测试。
2. 最小实现让测试通过。
3. 跑相关测试。
4. 跑格式与静态检查。
5. 对核心事务边界变更跑后端全量。
6. 用 Conventional Commits 提交。

推荐提交粒度：

- `test(sim): cover run tick rollback behavior`
- `refactor(sim): extract tick persistence coordinator`
- `refactor(scenario): make state updater transaction aware`
- `test(store): await async session commits`
- `docs(engineering): update persistence refactor roadmap`

## 4. 近期优先级

P0:

- 为 `SimulationService.run_tick` 补失败语义测试。
- 抽出 tick persistence coordinator。

P1:

- 梳理 day boundary 写入与幂等性。
- 清理 scenario updater 内部 commit。

P2:

- 清理 store 测试 warning。
- 更新 `CURRENT_ARCHITECTURE.md` 中 persistence 相关说明。

## 5. Done 定义

本轮 persistence 重构完成的判断标准：

- tick 核心写入路径有明确单一事务边界。
- repository 不再强迫复杂调用方接受内部 commit。
- scenario updater 不再意外破坏外层 rollback。
- day boundary 失败语义被测试锁定。
- 后端全量测试无事务相关 warning 或 flaky 行为。
- 文档能说明下一位维护者应该在哪里继续拆分。
