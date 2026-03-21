# Rules Schema

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 目标

第一版 `rules.yml` 不追求万能表达，而追求：

- 稳定
- 可解释
- 易校验
- 易迁移

一句话：

**先做有限模板，不做通用 DSL。**

## 2. 第一版规则结构

建议每条规则至少包含：

- `rule_id`
- `name`
- `description`
- `trigger`
- `conditions`
- `outcome`
- `priority`

可选：

- `scope`
- `tags`
- `explanation_key`

## 3. 顶层结构建议

```yaml
version: 1

rules:
  - rule_id: target_location_must_exist
    name: 目标地点必须存在
    description: move 行为只能前往存在的地点
    trigger:
      action_types: [move]
    conditions:
      - fact: target_location.exists
        op: eq
        value: false
    outcome:
      decision: impossible
      reason: location_not_found
    priority: 1000
```

## 4. `trigger`

`trigger` 决定规则在什么动作上参与求值。

第一版建议只支持：

- `action_types`

示例：

```yaml
trigger:
  action_types: [move, work]
```

第一版不建议支持：

- 复杂事件组合触发
- 多阶段状态机触发
- 任意表达式触发

## 5. `conditions`

`conditions` 是规则匹配条件列表。

第一版建议采用“全部满足即命中”的简单语义。

单个 condition 建议结构：

- `fact`
- `op`
- `value` 或 `value_from`

示例：

```yaml
conditions:
  - fact: target_location.capacity_remaining
    op: lte
    value: 0
```

说明：

- `value` 用于字面量比较
- `value_from` 用于 fact 与 fact 对比

示例：

```yaml
conditions:
  - fact: actor.workplace_id
    op: eq
    value_from: actor.location_id
```

第一版建议暂不支持：

- `and` / `or` 嵌套树
- 否定块
- 自定义函数
- 脚本表达式

## 6. `outcome`

`outcome` 定义规则命中后的裁决结果。

第一版建议至少支持：

- `decision`
- `reason`
- `risk_level`
- `tags`

其中 `decision` 建议限定为：

- `allowed`
- `violates_rule`
- `impossible`
- `soft_risk`

说明：

- `allowed`：规则明确允许
- `violates_rule`：制度违规，后续进入治理执行层
- `impossible`：物理或系统不可执行
- `soft_risk`：允许动作继续，但附带风险信号

示例：

```yaml
outcome:
  decision: violates_rule
  reason: closed_location_access
  risk_level: medium
  tags: [closure, restricted_access]
```

## 7. `priority`

必须支持优先级，因为规则之间可能冲突。

建议：

- 数值越大优先级越高
- 第一版采用“最高优先级命中规则决定主裁决”
- 同优先级冲突时走固定顺序：
  `impossible > violates_rule > soft_risk > allowed`

这样能避免第一版引入复杂冲突求解器。

## 8. `scope`

第一版可以保留可选 `scope`，但不做复杂语义。

候选值：

- `global`
- `role_based`
- `location_based`

这主要用于文档化和调试，不建议第一版承载复杂执行逻辑。

## 9. `explanation_key`

建议为每条规则预留 `explanation_key`。

作用：

- timeline 展示更友好的解释
- 后续可关联 `constitution.md` 或前端文案

示例：

```yaml
explanation_key: location.closed.access_denied
```

## 10. 第一版推荐规则模板

第一版最适合支持的规则模板类型：

- 存在性检查
- 容量检查
- 时间段限制
- 地点关闭限制
- 工作地点匹配
- 风险提升规则

不建议第一版支持：

- 跨多步骤推理规则
- 复杂经济结算规则
- 自定义 effect 脚本
- 任意嵌套布尔树

## 11. 示例

### 11.1 容量限制

```yaml
- rule_id: target_location_capacity_limit
  name: 地点容量限制
  description: 目标地点满员时 move 不可执行
  trigger:
    action_types: [move]
  conditions:
    - fact: target_location.capacity_remaining
      op: lte
      value: 0
  outcome:
    decision: impossible
    reason: location_full
  priority: 900
```

### 11.2 地点关闭

```yaml
- rule_id: closed_location_requires_enforcement
  name: 关闭地点限制进入
  description: 已关闭地点上的行动属于制度违规
  trigger:
    action_types: [move, work, talk, rest]
  conditions:
    - fact: target_location.id
      op: in
      value_from: policy.closed_locations
  outcome:
    decision: violates_rule
    reason: location_closed
    risk_level: medium
    tags: [closure]
  priority: 800
```

### 11.3 夜间社交风险

```yaml
- rule_id: late_night_social_risk
  name: 夜间社交风险提升
  description: 深夜社交会提高异常风险
  trigger:
    action_types: [talk]
  conditions:
    - fact: world.time_period
      op: eq
      value: night
  outcome:
    decision: soft_risk
    reason: late_night_social_risk
    risk_level: low
    tags: [night, social]
  priority: 300
```

## 12. 与治理执行层的边界

`rules.yml` 只负责定性，不直接负责完整处置。

也就是说：

- 规则决定“这是违规还是风险”
- 治理执行层决定“这次是否被发现、是否被拦截、是否处罚”

第一版不建议把复杂处罚逻辑直接塞进 `outcome`。

## 13. 第一版默认结论

建议默认采用：

- 顶层 `version + rules`
- 简单 `trigger`
- 扁平 `conditions`
- 有限 `decision` 集合
- 数值 `priority`
- 预留 `explanation_key`

## 14. 后续待展开问题

后续可继续细化：

- `POLICY_SCHEMA.md`
- 条件组合规则是否需要第二版引入
- `soft_risk` 与 `violates_rule` 是否需要合并或拆分
