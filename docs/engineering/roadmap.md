# Engineering Roadmap

本文档记录近期工程重构路线，重点围绕 persistence、simulation tick、事务边界和测试质量。

## 1. 当前阶段

当前阶段目标：把 simulation tick 的核心写入链路整理成可测试、可组合、可回滚的结构。

已完成：

- repository 拆分，降低单文件复杂度。
- 为 repository 增加事务友好的 `add*` / `set*` / `*_no_commit` 方法。
- `PersistenceManager.persist_tick_results` 事务化。
- `TickEventWriter.persist` 事务化。
- `TickPersistenceCoordinator` 抽出并覆盖失败回滚语义。
- day boundary 主业务写入事务语义已明确。
- scenario updater no-commit 入口已拆分。
- store 测试 warning 已清理。
- 前端测试修复，恢复 frontend suite 稳定性。
- 提交信息规范写入 `AGENTS.md`。

当前状态：

- 后端全量测试通过：`637 passed, 8 skipped`。
- 前端全量测试最近通过：`19 suites / 99 tests passed`。
- 后端全量测试无 coroutine `RuntimeWarning` summary。

## 2. Roadmap

### Phase 1: Tick persistence 原子性

状态：已完成。

目标：

- tick result 写入失败时不留下半写入数据。
- event writer 写入失败时不留下半写入 event。
- repository 支持上层事务组合。

已完成事项：

- `persist_tick_results` 原子化。
- `TickEventWriter.persist` 原子化。
- 相关失败回滚测试补齐。

后续补强：按新增场景持续补充对应 rollback 测试。

### Phase 2: `SimulationService.run_tick` 拆分

状态：已完成。

目标：

- 让 `SimulationService` 回到 orchestration 角色。
- 将 tick 写入细节抽到独立 coordinator。
- 明确 run tick、agent location、event、memory、relationship、scenario state 的统一提交边界。

建议 TDD 起点：

- event writer 失败时，run tick 不应提前变更。（已覆盖）
- agent location 写入失败时，不应写入 event。（已覆盖）
- scenario state update 失败时，event / memory / relationship 应一起回滚。（已覆盖）

候选产物：

- `backend/app/sim/tick_persistence_coordinator.py`（已创建）
- `backend/tests/sim/test_tick_persistence_coordinator.py`（已创建）

已完成事项：

- 抽出 `TickPersistenceCoordinator` 承接 tick 写入阶段。
- 将 agent location、run tick、event writer 放进同一写入事务。
- 补充 coordinator 独立测试，覆盖 location 写入失败短路和外部已有事务复用。
- 移除 coordinator 内部预提交，避免提前提交外部 pending change。
- 补充 writer 集成回归测试，覆盖 scenario state update 失败时 event / memory / relationship 一起回滚。
- 保留 day boundary 作为后续独立语义分析对象，暂不强行并入 tick 写入事务。

### Phase 3: Day boundary 写入语义

状态：已完成。

目标：

- 明确 day boundary 与 tick persistence 的失败恢复关系。
- 防止 daily memory / plan / economic effect 重复写入。
- 为可重试任务建立幂等基础。

关键问题：

- day boundary 失败是否回滚当前 tick？
- day boundary 是否应该成为独立可重试任务？
- 哪些写入需要幂等 key？

建议先做：

- 列出 day boundary 写入清单。（已完成）
- 补失败测试，锁定当前期望。（已完成）
- 再决定事务边界。（已完成）

已完成事项：

- evening reflection 的 daily reflection memory 写入与 memory promotion 合并到同一事务。
- 补充 promotion 失败回滚测试，确保 promotion 失败时 reflection memory 不会半写入。
- 补充 morning planning 回归测试，确保 plan memory 写入失败时 `agent.current_plan` 不会半更新。
- 在重构计划中整理 day boundary 写入清单，明确 LLM call telemetry 为 best-effort。
- 补充 `LlmCallWriter` 测试，锁定 telemetry 持久化失败不抛出异常的契约。

### Phase 4: Scenario updater 事务规范

状态：已完成。

目标：

- scenario updater 默认不拥有 commit。
- 调用方负责事务边界。
- 独立调用入口可以保留，但需要显式命名或包装。

已处理：

- `BundleWorldStateUpdater.persist_subject_alert` 已适配 `TickEventWriter` 受管事务。
- `BundleWorldStateUpdater` 已拆分 `apply_subject_alert()` no-commit 入口和 `persist_subject_alert()` 独立提交入口。
- `BundleWorldScenario.update_state_from_events()` 已改用 no-commit 入口，避免提交外部 pending change。
- 已补充场景更新复用外部事务的回归测试。
- 已补充 bundle seed / open world seed 的失败回滚测试，锁定最终 commit 失败时不留下半初始化数据。

待处理：

- 新增 scenario updater 时继续遵守 no-commit / persist 独立入口拆分。
- 新增 seed 策略时补失败回滚测试。

### Phase 5: 测试质量清理

状态：已完成。

目标：

- 清理后端全量测试 warning。
- 将 store 层测试 setup 改成 async 风格。
- 提升事务测试的失败信号质量。

优先项：

- `tests/store/test_agent_economic_state.py`（已清理）
- `tests/store/test_economic_effect_log.py`（已清理）
- `tests/store/test_governance_case.py`（已清理）

已完成事项：

- 将上述 store 测试中的 async session fixture 改为 `pytest_asyncio.fixture`。
- 将模型创建测试改为 async 测试并 `await db_session.commit()`。
- 后端全量测试已无 coroutine `RuntimeWarning` summary。

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

- 保持事务回归测试作为新增写入路径的准入条件。
- 将过长核心文件纳入重构队列，优先处理 `backend/app/sim/persistence.py` 和大型 sim 测试文件。

P1:

- 更新 `CURRENT_ARCHITECTURE.md` 中 persistence / tick 写入边界说明。
- 继续观察 day boundary 是否需要独立重试任务。
- 建立测试数据 factory / builder，减少各测试文件重复手写 run、location、agent、event。
- 默认后端测试命令已调整为排除 `integration`，真实 SDK / PostgreSQL 测试使用 `make backend-integration-test`。

P2:

- 将本轮重构经验沉淀到贡献指南或开发文档。
- 前端补充关键页面级用户流测试，并增强 Phaser scene 的行为断言。

## 5. 维护性审计补充

本轮审计关注两个问题：是否存在过长脚本或文件影响维护，以及当前测试体系是否规范、优雅并贴合项目。

### 5.1 长文件与脚本

结论：

- Shell 脚本本身不是当前主要风险。`scripts/railway-bootstrap.sh` 约 164 行，`Makefile` 约 261 行，仍在可维护范围内。
- 真正的风险来自过长业务文件和过长测试文件，尤其是 simulation persistence、scenario、service runtime、前端地图和 Phaser scene。

重点文件：

- `backend/app/sim/persistence.py`：集中处理 tick 事件、记忆、关系、治理记录、治理 case、经济状态等写入，职责过密。
- `backend/tests/sim/test_service_runtime.py`、`backend/tests/sim/test_scenarios.py`、`backend/tests/sim/test_service_isolated.py`：测试文件过长，重复造数较多，定位失败成本偏高。
- `frontend/components/town-map.tsx`：同时承担布局计算、小地图、缩放拖拽、节点渲染和交互。
- `frontend/components/phaser/world-scene.ts`：同时承担 Phaser scene、纹理、节点同步、动画、tooltip 和视觉规则。

建议拆分顺序：

1. 先拆测试辅助，将常见 run / location / agent / event 创建逻辑沉淀为 factory。
   - `make_run_with_location_agents` 已加入 `backend/tests/factories.py`，用于收敛 service runtime 测试里重复的 run/location/agent 组合造数。
   - `create_isolated_sqlite_engine` 与 `build_scheduler_service` 已加入 `backend/tests/sim/helpers.py`，用于收敛 isolated service 测试里的内存 DB 与 scheduler runtime 初始化。
2. 再拆 `PersistenceManager`，让当前类只保留事务编排，具体写入逻辑下沉到 memory、relationship、governance、economic 等小模块。
   - `governance_persistence.py` 已抽出，承接 governance records / cases 写入。
   - `relationship_persistence.py` 已抽出，承接 relationship upsert / impact annotation。
   - `memory_persistence.py` 已抽出，承接 memory record 构建、routine memory 合并与 relationship strength 预加载。
   - `economic_persistence.py` 已抽出，承接 tick economic state、free action consequence 与 state delta 应用。
3. 最后拆前端地图组件，把纯计算、交互 hook、子视图组件和 Phaser 渲染辅助分离。
   - `world-scene-style.ts` 已抽出，承接 Phaser 场景的尺寸常量、颜色/纹理 key、glyph/marker、palette 合并与箭头角度计算。
   - `town-map-utils.ts` 已抽出，承接 SVG 地图常量、地点样式、坐标缩放、viewBox clamp、地图节点/连线/移动路径构建。
   - `town-mini-map.tsx` 已抽出，承接小地图渲染、点击导航与视口框拖拽。
   - `use-speech-bubbles.ts` 已抽出，承接 talk/speech 事件气泡、去重、自动过期与数量上限。
   - `use-night-skip-banner.ts` 已抽出，承接夜晚跨天提示的检测、显示状态与自动隐藏。
   - `use-town-map-viewport.ts` 已抽出，承接 SVG viewBox、缩放、重置、地图聚焦、拖拽平移与滚轮缩放。
   - `town-location-node.tsx` 已抽出，承接地点节点、热力层、居民头像与对话气泡渲染。
   - `world-scene-geometry.ts` 已抽出，承接 Phaser 场景的世界坐标映射与 agent slot 坐标计算。
   - `world-scene-textures.ts` 已抽出，承接 Phaser ground、building、agent pixel texture 的生成与 ensure 逻辑。
   - `world-scene-sync.ts` 已抽出，承接 Phaser location、agent、move trail、speech bubble 节点同步与 stale node 清理。
   - `world-scene-interactions.ts` 已抽出，承接 Phaser 高亮刷新、相机聚焦、tooltip 与点击反馈动画。
   - `world-scene-stage.ts` 已抽出，承接 Phaser 舞台外壳创建、ambience 同步与 stage theme 应用。

### 5.2 测试体系

结论：

- 后端测试体系整体规范，覆盖面和项目适配度较高，已覆盖 api、sim、store、scenario、agent、director、integration 等边界。
- 前端测试体系基础可用，覆盖了 lib 和部分组件，但更偏单元层，关键页面流和复杂可视化交互保护不足。
- 当前问题不是“没有测试”，而是测试可维护性和质量门禁还需要提升。

已具备的优点：

- `backend/tests/conftest.py` 提供了 async DB session、ASGI client、默认 heuristic backend 和 scheduler cleanup。
- `backend/pyproject.toml` 已声明 `integration` marker，并配置了 coverage。
- `frontend/jest.config.ts` 使用 Next.js Jest 配置，覆盖 `__tests__` 和 `*.test.*` 文件。
- 后端测试与业务模块基本同构，能反映项目真实边界。

主要改进点：

- 大型测试文件需要按行为主题拆分，减少单文件上下文负担。
- 测试数据创建应统一封装，避免每个测试重复构造 SQLAlchemy model。
- 避免在普通行为测试中过多调用私有方法；私有方法测试应优先转成 public behavior 测试。
- 默认测试命令应区分 fast unit/integration/live SDK，避免日常测试受外部环境影响。
- 前端应补充页面级用户流测试，并让 Phaser 测试验证关键对象数量、坐标同步、事件回调等行为。

## 6. Done 定义

本轮 persistence 重构完成的判断标准：

- tick 核心写入路径有明确单一事务边界。
- repository 不再强迫复杂调用方接受内部 commit。
- scenario updater 不再意外破坏外层 rollback。
- day boundary 失败语义被测试锁定。
- 后端全量测试无事务相关 warning 或 flaky 行为。
- 文档能说明下一位维护者应该在哪里继续拆分。
