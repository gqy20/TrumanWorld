# Narrative World Design

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 目标

这份文档把平台级 world design 抽象压到当前默认场景 `narrative_world` 上。

目的不是一次性写完整法典，而是回答：

- 当前默认世界最值得先资产化什么
- 哪些规则应先进入 `rules.yml`
- 哪些动态值应先进入 `policies/default.yml`

## 2. 当前场景特征

`narrative_world` 不是一个完整经济模拟世界，而是一个强调连续性、自然日常感和主体异常控制的叙事型社会模拟。

当前 world 设计重点应围绕：

- 公共空间与日常活动节律
- 主体附近的异常风险
- 临时关闭、停电、活动等环境变化
- cast/support 角色的自然行为约束

这意味着第一阶段不需要优先建模：

- 商品交易
- 许可制度
- 复杂组织治理

## 3. 第一阶段最值得资产化的内容

### 3.1 地点可达性与关闭状态

最适合先进入：

- `rules.yml`
- `policies/default.yml`

原因：

- 当前项目已有 location、capacity、world_effects 基础
- director 已经有关闭、停电、活动等干预方向
- 这部分最容易解释到 timeline

### 3.2 时间段风险

例如：

- 深夜社交风险更高
- 特定时段公共空间更容易出现观察与介入
- 工作时段和休息时段的行为预期不同

这部分适合：

- 基础时间事实放在 `world.yml`
- 风险阈值放在 `policies/default.yml`
- 判断规则放在 `rules.yml`

### 3.3 主体保护偏置

`narrative_world` 的核心不是普遍法律，而是围绕主体连续性展开的治理逻辑。

因此第一阶段建议显式引入：

- `policy.subject_protection_bias`
- `policy.continuity_protection_level`

这样后续就能解释：

- 为什么靠近主体的异常行为更容易被注意
- 为什么某些违规在一般区域无事发生，但在主体附近会被处理

### 3.4 cast 的异常行为约束

当前系统里 support/cast 行为更多靠 prompt 和软 guidance。

第一阶段更适合做的不是全规则化，而是先引入少量制度约束，例如：

- cast 不应主动制造高异常事件
- cast 深夜聚集或异常对话属于风险行为
- cast 对主体的引导优先通过自然方式完成

这类规则更适合作为：

- `soft_risk`
- `violates_rule`

而不是全都物理拦截。

### 3.5 关系网络的叙事化演化

`narrative_world` 不是纯制度世界，它本质上还是一个持续运转的人际场。

因此第一阶段关系设计不应只回答“谁认识谁”，还应回答：

- 哪些日常接触会自然升温
- 哪些互动会造成疏离或不信任
- 哪些地点和时段会放大社交效果
- 主体附近的异常互动为什么会带来负面后果

这部分适合：

- 关系状态本身存入 relationship 数据
- 变化条件由 `rules.yml` 与 `policies/default.yml` 共同约束
- 变化原因通过 event payload / memory / timeline 解释

## 4. Narrative World 第一阶段建议 facts

在平台 facts 基础上，这个场景最常用的应该是：

- `actor.role`
- `actor.location_id`
- `actor.workplace_id`
- `target_agent.role`
- `target_agent.relationship_level`
- `target_agent.familiarity`
- `target_location.id`
- `target_location.type`
- `target_location.capacity_remaining`
- `world.time_period`
- `policy.closed_locations`
- `policy.power_outage_locations`
- `policy.sensitive_locations`
- `policy.subject_protection_bias`
- `policy.social_boost_locations`
- `policy.talk_risk_after_hour`

## 5. Narrative World 第一阶段建议规则

### 5.1 物理不可执行类

- 地点不存在
- 地点满员
- 会话冲突

这些仍应走 `impossible`。

### 5.2 制度违规类

- 关闭地点上的行动
- 停电影响区域中的不当行动
- 特定高保护场景中的明显异常行为

这些更适合走 `violates_rule`。

### 5.3 软风险类

- 深夜社交
- 主体附近的异常互动
- 敏感区域的非日常行为

这些更适合走 `soft_risk`。

### 5.4 关系演化类

`narrative_world` 中的关系变化应被视为“行为后果”的一部分，而不是和世界规则完全脱钩。

第一阶段建议至少支持以下倾向：

- 白天、公共、自然的日常对话，通常小幅提升 `familiarity`
- 在 `cafe`、`plaza` 等社交增强地点的自然互动，可额外提升 `affinity`
- 持续可靠、照料式或帮助式互动，可提升 `trust`
- 深夜、敏感区域、主体附近的异常互动，不一定提升关系，必要时应转为 `soft_risk`
- 明显冲突、操控、失信、强行引导，应允许降低 `trust` 或 `affinity`

第一阶段默认不追求复杂社会学模型，但应避免：

- 任何 `talk` 一律加分
- 所有地点和时段的社交效果完全相同
- 主体附近的异常行为既提高风险又提高亲密度

## 6. Narrative World 第一阶段建议 policy values

建议 `policies/default.yml` 最小包含：

```yaml
version: 1

policy_id: default
name: Narrative World Default Policy
description: Narrative World 默认治理参数

values:
  closed_locations: []
  power_outage_locations: []
  sensitive_locations: []
  high_attention_locations: []
  inspection_level: medium
  subject_protection_bias: high
  continuity_protection_level: high
  talk_risk_after_hour: 23
  relationship_decay_per_day:
    affinity: 0.02
    trust: 0.0
  social_boost_locations:
    plaza: 0.2
    cafe: 0.3
```

## 7. Narrative World 第一阶段建议规则示例

当前代码中已经落地的最小规则包括：

- `location_closed_access`
- `power_outage_work_restriction`
- `late_night_stranger_talk_risk`
- `subject_stranger_talk_risk`
- `sensitive_location_stranger_talk_risk`

其中前两条主要承接动态 world effects，后三条主要承接叙事连续性与社交风险。

### 7.1 关闭地点限制

```yaml
- rule_id: location_closed_access
  name: 关闭地点限制
  description: 进入已关闭地点属于制度违规
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

### 7.2 深夜社交风险

```yaml
- rule_id: late_night_talk_risk
  name: 深夜社交风险
  description: 深夜社交会提高异常风险
  trigger:
    action_types: [talk]
  conditions:
    - fact: world.time_period
      op: eq
      value: night
  outcome:
    decision: soft_risk
    reason: late_night_talk_risk
    risk_level: low
    tags: [night, social]
  priority: 300
```

## 8. 第一阶段 agent 可见摘要建议

对 `narrative_world`，agent 更适合看到：

- 当前地点与附近地点的日常性提示
- 当前是否存在关闭、停电、活动等政策通知
- 当前是否处于高风险时段
- 最近哪些行为触发了风险或警告

当前代码中已经最小落地的可见摘要包括：

- `available_actions`
- `policy_notices`
- `blocked_constraints`
- `current_risks`
- `recent_rule_feedback`

并且会把关闭地点、停电、最近治理反馈、最近规则风险，以及高 attention 风险一起压缩到这层。

不建议直接看到：

- 全部规则原文
- 平台裁决优先级细节
- 所有治理参数全集

## 9. 当前已落地但文档需明确的实现细节

### 9.1 动态 world effects 已接入 rule facts

当前 `shutdown` 和 `power_outage` 已持久化为 run 级 `world_effects`，并在 runtime facts 中映射为：

- `policy.closed_locations`
- `policy.power_outage_locations`

这意味着 Narrative World 已经具备最小动态 policy overlay，而不是只依赖静态 `policies/default.yml`。

### 9.2 对话连续性已进入 runtime context

当前活跃对话状态已经进入 agent runtime context，包含：

- `last_message_summary`
- `last_proposal`
- `open_question`
- `repeat_count`

当前还额外有一层最小保护：

- 当同一 agent 在连续对话里重复相同提议达到阈值时，orchestrator 会把该次 `talk` 降级为 `rest`

这属于 Narrative World 下“自然行为约束”的最小执行版。

### 9.3 规则反馈已进入长期记忆

当前不仅治理警告/拦截会进入长期记忆，纯规则反馈也已经进入长期记忆：

- `soft_risk -> Rule risk`
- `violates_rule / impossible -> Rule block`

这使得 Narrative World 中的“被提醒过什么、被拦过什么”开始形成跨 tick 学习闭环。

补充建议：

- agent 看到的是派生后的 `relationship_level`
- 只有熟人以上关系才稳定暴露职业等信息
- 密友或家人可获得更高置信度的背景信息
- 原始 `trust` / `affinity` 数值不应直接作为 agent-facing 接口

## 9. 当前最适合的实现路径

对 `narrative_world`，最值得先做的是：

1. 补 `constitution.md`
2. 补 `rules.yml`
3. 补 `policies/default.yml`
4. 把 relationship 变化从持久化硬编码迁到“规则/治理/后果”链路
5. 先让 timeline/event payload 能解释规则和治理结果

这样能最快把抽象设计落到当前默认场景上。

## 10. 第一阶段默认结论

`narrative_world` 的第一阶段重点不是完整社会制度模拟，而是：

- 地点关闭与区域变化
- 时间段风险
- 主体保护偏置
- 异常行为的治理处理
- 叙事化关系演化

这几块最符合当前项目形态，也最容易验证价值。
