# Governance And Economic MVP

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 目标

这一版不是做完整社会治理。

这一版要做的是：

- 让治理从“单条记录”升级为“最小案件流程”
- 让治理后果先体现为“限制与生计压力”
- 让经济先是“生活状态”，而不是完整市场或银行系统

一句话：

**先做粗糙治理与最小生计闭环，不直接做执法机构和复杂货币社会。**

## 2. 设计原则

### 2.1 执法先粗糙

第一阶段不引入执法 agent。

先只保留平台级后果：

- `record`
- `warn`
- `restrict`

其中：

- `record`：留痕，不立刻产生硬后果
- `warn`：写记忆、提高 attention、进入案件流程
- `restrict`：限制地点、工作或后续行动能力

### 2.2 经济先是生计状态

当前世界还没有完整工资、商品、产权、债务、交易网络。

因此第一阶段不应把经济收缩成“余额 + 罚款”，也不应假装已经有完整市场。

更合理的最小经济是：

- `cash`
- `employment_status`
- `food_security`
- `housing_security`

它表达的是：

- 是否还能稳定工作
- 是否还能维持日常生活
- 治理后果是否开始影响生计

### 2.3 治理先影响机会，不先影响金钱

第一阶段最重要的治理后果不是罚款，而是：

- 更容易被持续关注
- 更难进入某些地点
- 更难执行某些动作
- 更容易失去工作稳定性

这比直接扣钱更接近当前世界阶段。

## 3. MVP 范围

### 3.1 `governance_cases`

把 `governance_records` 聚合成案件。

最小状态：

- `open`
- `warned`
- `restricted`
- `closed`

用途：

- 表达“这不是一次孤立事件，而是一个治理对象”
- 支撑后续升级、结案、director 查询

### 3.2 `governance_restrictions`

表达治理后果。

第一阶段只做最小限制类型：

- `work_ban`
- `location_ban`
- `heightened_watch`

用途：

- `work_ban`：不能执行 `work`
- `location_ban`：不能进入某地点
- `heightened_watch`：提高后续 observation / intervention 强度

### 3.3 `agent_economic_state`

表达最小生计状态。

建议字段：

- `cash`
- `employment_status`
- `food_security`
- `housing_security`
- `work_restriction_until_tick`

第一阶段不做：

- 市场价格
- 商品交易
- 房产系统
- 债务系统

### 3.4 `economic_effect_logs`

只记录“生计为什么变化”，不做通用交易流水。

最小类型：

- `daily_work_income`
- `governance_work_loss`
- `manual_support`

## 4. 最小数据模型

### 4.1 `governance_cases`

建议字段：

- `id`
- `run_id`
- `agent_id`
- `status`
- `opened_tick`
- `last_updated_tick`
- `primary_reason`
- `severity`
- `record_count`
- `active_restriction_count`
- `metadata`

### 4.2 `governance_restrictions`

建议字段：

- `id`
- `run_id`
- `agent_id`
- `case_id`
- `restriction_type`
- `status`
- `scope_type`
- `scope_value`
- `reason`
- `start_tick`
- `end_tick`
- `severity`
- `metadata`

说明：

- `scope_type` 例如 `location`、`action`、`world`
- `scope_value` 例如 `loc_cafe`、`work`

### 4.3 `agent_economic_state`

建议字段：

- `agent_id`
- `run_id`
- `cash`
- `employment_status`
- `food_security`
- `housing_security`
- `work_restriction_until_tick`
- `last_income_tick`
- `metadata`

建议的最小状态值：

- `employment_status`: `stable / unstable / suspended`

### 4.4 `economic_effect_logs`

建议字段：

- `id`
- `run_id`
- `agent_id`
- `case_id` nullable
- `tick_no`
- `effect_type`
- `cash_delta`
- `food_security_delta`
- `housing_security_delta`
- `employment_status_before`
- `employment_status_after`
- `reason`
- `metadata`

## 5. 最小流程

### 5.1 治理流程

1. tick 产生 `governance_record`
2. 若结果是 `warn / block`，尝试归并进已有 case
3. 没有合适 case 就创建新 case
4. case 根据阈值生成 restriction
5. restriction 影响后续 action
6. case 进入 `warned` 或 `restricted`

### 5.2 经济流程

1. agent 正常工作时获得最小收入
2. 若存在 `work_ban`，则本 tick 无法工作
3. 无法工作会触发 `governance_work_loss`
4. 若持续失去工作机会，`food_security` 下降
5. 必要时把 `employment_status` 从 `stable` 降到 `unstable / suspended`

## 6. 最小归并与升级规则

### 6.1 case 归并

先用简单规则：

- 同 `run_id`
- 同 `agent_id`
- 同 `primary_reason`
- 最近 `N` tick 内
- status 不是 `closed`

### 6.2 restriction 触发

第一阶段建议非常粗：

- 单次 `block` 可直接触发 `work_ban` 或 `location_ban`
- 连续两次 `warn` 可触发 `heightened_watch`
- 连续 `warn + block` 可把 case 升到 `restricted`

### 6.3 经济影响

第一阶段也保持粗粒度：

- 正常 `work` 给少量 `cash`
- `work_ban` 存在时不给收入
- 多个 tick 无收入时，`food_security` 缓慢下降

## 7. 与现有系统的集成点

后端主要落点：

- `backend/app/store/models.py`
- `backend/app/store/repositories.py`
- `backend/alembic/versions/...`
- `backend/app/sim/persistence.py`
- `backend/app/scenario/runtime/governance_executor.py`

建议新增 service：

- `backend/app/sim/governance_case_service.py`
- `backend/app/sim/economic_state_service.py`

API 主要落点：

- `backend/app/api/routes/run_director.py`
- `backend/app/api/routes/agents.py`
- `backend/app/api/schemas/simulation.py`

前端主要落点：

- `frontend/components/world-health-director.tsx`
- `frontend/app/runs/[runId]/agents/[agentId]/page.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/types.ts`

## 8. 明确不做

这一期明确不做：

- 执法 agent
- 法院/申诉/复核系统
- 多机构治理
- 完整交易流水
- 商品市场
- 房产与许可证系统
- 债务与税收

## 9. 代码量评估

按这个 MVP 范围，比较现实的量级是：

### 9.1 后端数据层

- migration + models + repositories
- 约 `1200-1800` 行

### 9.2 治理流程层

- case 聚合
- restriction 生成
- restriction 对 action 的影响
- 约 `1200-2200` 行

### 9.3 经济状态层

- 生计状态更新
- work loss / basic income
- 约 `800-1500` 行

### 9.4 API 层

- director cases / restrictions
- agent economic summary
- 约 `700-1300` 行

### 9.5 前端

- director 最小案件/限制视图
- agent 生计摘要
- 约 `800-1500` 行

### 9.6 测试

- repository
- service
- API
- 前端数据层
- 约 `2200-3800` 行

### 9.7 总量

- 较紧凑的 MVP：`5k-8k` 行
- 更稳妥的完整 MVP：`7k-12k` 行

## 10. 推荐实施顺序

1. 先补 migration 与 model
2. 先补 repository
3. 先写 case / restriction 的后端测试
4. 再接 economic state
5. 再接 API
6. 最后接 director 和 agent 最小 UI

当前推荐：

- 先做 `governance_cases`
- 再做 `work_ban`
- 再做 `agent_economic_state`
- 最后再把更细的 `location_ban` 和更多经济效果补上
