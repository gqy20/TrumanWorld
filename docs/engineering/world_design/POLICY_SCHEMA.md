# Policy Schema

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 目标

`policies/*.yml` 不负责重新定义世界事实，也不负责完整法条本体。

它负责：

- 提供当前生效的治理参数
- 覆盖规则求值所需的动态值
- 承载临时事件、治理强度和区域性例外

一句话：

**rules 定义制度边界，policy 定义当前执行环境。**

## 2. 第一版设计原则

第一版 `policy` 应尽量参数化，而不是脚本化。

优先支持：

- 参数覆盖
- 列表型限制
- 区域型配置
- 时段型配置
- 治理强度配置

第一版不建议支持：

- 自定义脚本
- 任意规则重写
- 深层继承链
- 多层 patch 语言

## 3. 文件组织建议

建议 bundle 目录结构：

```text
scenarios/<scenario_id>/
  policies/
    default.yml
    <policy_id>.yml
```

其中：

- `default.yml`：默认政策基线
- 其他文件：临时政策、专题政策、事件政策

## 4. 第一版顶层结构

建议：

```yaml
version: 1

policy_id: default
name: Default Governance Policy
description: 默认治理与环境参数

values:
  closed_locations: []
  power_outage_locations: []
  sensitive_locations: []
  inspection_level: low
  talk_risk_after_hour: 23
  subject_protection_bias: medium
```

第一版先统一采用 `values`，避免过早引入复杂结构。

## 5. 第一版建议支持的 policy values

### 5.1 地点限制类

- `closed_locations`
- `restricted_locations`
- `power_outage_locations`

这些字段应使用 location id 列表。

### 5.2 敏感区类

- `sensitive_locations`
- `high_attention_locations`

这些字段用于告诉规则和治理执行层，哪些地点更容易被观察和触发干预。

### 5.3 执法强度类

- `inspection_level`
- `subject_protection_bias`
- `continuity_protection_level`

建议第一版使用枚举值，而不是自由数字。

候选枚举：

- `low`
- `medium`
- `high`

### 5.4 时段参数类

- `talk_risk_after_hour`
- `night_restriction_start_hour`
- `night_restriction_end_hour`

这些字段用于支撑时间敏感规则。

### 5.5 活动增益类

- `social_boost_locations`
- `activity_boost_locations`

建议形式：

```yaml
values:
  social_boost_locations:
    plaza: 0.3
    cafe: 0.2
```

第一版允许简单 map，但不建议引入复杂嵌套对象。

## 6. 与 `rules.yml` 的关系

policy 不直接替代 rule。

推荐关系是：

- `rules.yml` 写稳定制度逻辑
- `policy values` 作为规则求值输入

例如：

- `target_location.id in policy.closed_locations`
- `world.hour >= policy.talk_risk_after_hour`
- `target_location.id in policy.sensitive_locations`

也就是说，policy 主要通过 facts 影响规则，而不是重写规则条目。

## 7. 第一版是否允许覆盖规则条目

当前建议：

- 第一版不允许 policy 直接改写 rule 结构
- 第一版只允许覆盖规则输入参数

原因：

- 更容易校验
- 更容易调试
- 更容易解释
- 避免 policy 变成第二套 rule 语言

后续如果确有必要，可再考虑有限的 rule enable/disable 机制。

## 8. 与治理执行层的关系

policy 是治理执行层最重要的动态输入。

它会影响：

- 观察概率
- 介入力度
- 是否立刻拦截
- 是否优先保护主体

例如：

- `inspection_level = high`
  表示更高的观察和介入强度
- `subject_protection_bias = high`
  表示靠近主体的异常行为更容易被处理

## 9. 空值和默认值

建议：

- policy 文件缺失时，回退到 bundle 默认 policy
- `values` 中缺失字段时，按 schema 默认值补齐
- 第一版不建议把未定义 policy value 视为 `null`

这样可以减少运行时分支。

## 10. 第一版 schema 草案

```yaml
version: 1

policy_id: default
name: Default Governance Policy
description: 默认治理参数

values:
  closed_locations: []
  restricted_locations: []
  power_outage_locations: []
  sensitive_locations: []
  high_attention_locations: []
  inspection_level: low
  subject_protection_bias: medium
  continuity_protection_level: high
  talk_risk_after_hour: 23
  night_restriction_start_hour: 23
  night_restriction_end_hour: 6
  social_boost_locations: {}
```

## 11. 对当前仓库的映射建议

当前代码里的 `world_effects` 可以逐步收口到 policy values：

- `power_outages` -> `power_outage_locations`
- 未来的关闭区域 -> `closed_locations`
- 未来的敏感区域 -> `sensitive_locations`

这意味着：

- 短期可以继续保留 `world_effects`
- 中期应让 runtime 统一把动态效果投影为 `policy.*`

## 12. 第一版默认结论

建议默认采用：

- `policies/default.yml` 为必备资产
- 顶层统一使用 `values`
- policy 只覆盖参数，不直接覆盖规则条目
- 治理执行层主要消费 policy
- 动态 world effect 逐步并入 policy 语义

## 13. 后续待展开问题

后续可继续细化：

- 是否支持 rule enable/disable
- 是否支持 policy 继承或叠加
- director 注入的 policy 生命周期如何建模
