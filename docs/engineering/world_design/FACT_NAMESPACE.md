# Fact Namespace

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 目标

规则资产不应直接引用 Python 实现字段，而应引用平台统一 facts。

这层命名空间的作用是：

- 让 `rules.yml` 对运行时实现保持稳定
- 让不同 scenario 共享同一套求值语言
- 限制第一版规则系统的复杂度

一句话：

**规则引用 facts，不直接引用代码对象。**

## 2. 第一版命名空间范围

第一版建议只开放五个顶层命名空间：

- `actor.*`
- `target_agent.*`
- `target_location.*`
- `world.*`
- `policy.*`

第一阶段不开放：

- 任意自定义顶层命名空间
- 任意脚本表达式
- 直接透出数据库模型字段全集

## 3. `actor.*`

表示当前动作发起者相关事实。

建议开放：

- `actor.id`
- `actor.name`
- `actor.role`
- `actor.occupation`
- `actor.location_id`
- `actor.home_location_id`
- `actor.workplace_id`
- `actor.status.<key>`

谨慎开放：

- `actor.profile.<key>`

建议第一版默认不开放整个 `profile`，原因是：

- `profile` 更偏 bundle 内容和认知资料
- 字段形态不稳定
- 很容易把规则系统耦合到场景私有数据

如果后续确实需要，可改为白名单方式开放。

## 4. `target_agent.*`

表示动作目标 agent 相关事实。

建议开放：

- `target_agent.id`
- `target_agent.role`
- `target_agent.occupation`
- `target_agent.location_id`
- `target_agent.status.<key>`

适用动作：

- `talk`
- 后续可能的 `trade`
- 后续可能的 `assist`

如果当前动作没有目标 agent，则相关 facts 为 `null`。

## 5. `target_location.*`

表示动作目标地点相关事实。

建议开放：

- `target_location.id`
- `target_location.name`
- `target_location.exists`
- `target_location.type`
- `target_location.capacity`
- `target_location.occupancy`
- `target_location.capacity_remaining`
- `target_location.attributes.<key>`

说明：

- `exists` 主要用于区分“目标不存在”和“目标存在但制度不允许”
- `capacity_remaining = capacity - occupancy`

第一版不建议直接开放完整地点对象。

## 6. `world.*`

表示全局世界态和时间态。

建议开放：

- `world.current_tick`
- `world.current_time`
- `world.time_period`
- `world.weekday`
- `world.weekday_name`
- `world.is_weekend`

后续可增补：

- `world.active_effects`
- `world.day_index`

其中时间态应尽量基于当前 `WorldState.time_context()` 统一生成。

## 7. `policy.*`

表示当前生效的政策与治理参数。

这层应逐步吸收当前 `world_effects` 的运行时语义。

建议第一版开放：

- `policy.closed_locations`
- `policy.power_outage_locations`
- `policy.sensitive_locations`
- `policy.inspection_level`
- `policy.talk_risk_after_hour`
- `policy.subject_protection_bias`

说明：

- `policy.*` 是规则层最重要的动态输入
- 动态世界变化尽量通过 policy 表达，而不是散落在代码判断中

## 8. 空值与缺失处理

必须先定义 facts 读取失败时的行为。

建议：

- 路径存在但值为空：返回 `null`
- 路径不存在：视为 schema 错误，而不是运行时自动吞掉
- 第一版规则求值不支持“静默忽略未知 facts”

这样能避免 bundle 写错字段后悄悄失效。

## 9. 允许的比较方式

facts 本身不是 schema 的全部，还要约束可用操作符。

第一版建议支持：

- `eq`
- `neq`
- `in`
- `not_in`
- `gt`
- `gte`
- `lt`
- `lte`
- `contains`

第一版不建议支持：

- 任意表达式拼接
- 自定义函数
- 动态脚本求值

## 10. 与当前仓库的映射建议

当前实现可映射到 facts 的主要来源：

- `actor.*` / `target_agent.*`
  来自 `backend/app/sim/world.py` 中的 `AgentState`
- `target_location.*`
  来自 `backend/app/sim/world.py` 中的 `LocationState`
- `world.*`
  来自 `WorldState.time_context()`
- `policy.*`
  初期可来自 scenario bundle policy 文件与现有 `world_effects`

## 11. 第一版默认结论

建议默认采用：

- facts 只开放五个命名空间
- `actor.profile.*` 暂不直接开放
- `world_effects` 逐步收口到 `policy.*`
- 未知 fact 路径视为 schema 错误
- 不支持脚本表达式

## 12. 后续待展开问题

后续可继续细化：

- `actor.role` 如何从 scenario semantics 统一映射
- 是否引入 `location.*` 与 `target_location.*` 的区分
- 是否允许 scenario 通过注册方式扩展 facts
