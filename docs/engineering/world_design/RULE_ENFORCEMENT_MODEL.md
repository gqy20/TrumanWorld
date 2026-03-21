# Rule And Enforcement Model

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 核心判断

world 里的“审核”不应直接等于硬性规则命中。

更合理的结构是三层：

1. 规则层：定义制度边界
2. 治理执行层：决定是否发现、是否介入、如何处置
3. 后果层：把处置结果写入长期状态

当前实现状态：

- 目前已实现第 1 层、第 2 层和第 3 层的最小版
- `soft_risk` 当前会继续执行，并进入 `warn`
- `impossible` 当前直接映射为 `block`
- `violates_rule` 当前会根据 policy 与治理信号决定 `warn` 或 `block`
- `warn / block` 当前已可写入最小长期状态
- 治理状态已经开始影响 relationship 后果
- `governance_execution.reason` 与纯 `rule_evaluation.reason` 当前都已进入最小长期记忆闭环

## 2. 三层职责

### 2.1 规则层

负责定性：

- 行为是否合法
- 是否违规
- 是否属于高风险行为
- 命中了哪条规则

规则层输出不应只有简单 `accepted/rejected`。

第一版建议至少区分：

- `allowed`
- `violates_rule`
- `impossible`

说明：

- `allowed`：制度允许
- `violates_rule`：制度不允许，但不等于物理上不能发生
- `impossible`：系统或物理条件下无法执行

### 2.2 治理执行层

负责把制度边界变成现实世界中的执行。

例如：

- 有没有被观察到
- 当前巡查强度高不高
- 是否要立即拦截
- 是否只做警告或记录
- 是否触发更高层次干预

这层更接近“政府/治理机制”，但第一阶段不必做成独立政府 agent。

更适合先做成一个平台级执行器。

### 2.3 后果层

负责把执行结果写入长期状态。

例如：

- 违规记录
- 声誉变化
- alert score 上升
- location 或 policy 状态变化
- timeline 审计信息

当前最小实现已经覆盖：

- `warning_count`
- `governance_attention_score`
- `current_risks`
- agent memories 中的治理反馈与规则反馈
- relationship 侧的最小后果扩散

## 3. 为什么不能只做硬规则

如果所有不合法行为都直接 `blocked`：

- 世界会过硬
- agent 无法试探边界
- 没有规避、侥幸、选择性执法空间
- 社会模拟会退化成流程校验器

更合理的做法是：

- 物理不可执行：直接阻止
- 制度违规：允许进入治理执行层
- 高风险行为：允许发生，但带风险和后果

当前代码与上面的目标仍有差距：

- `物理不可执行 -> 直接阻止` 已实现
- `高风险行为 -> 允许发生并附带反馈` 已实现
- `制度违规 -> 进入治理执行层` 已实现
- `制度违规 -> 最小长期后果写入` 已实现
- `制度违规 -> relationship 后果扩散` 已实现（最小版）
- `制度违规 -> 规则反馈写入长期记忆` 已实现（最小版）
- `制度违规 -> 更完整长期后果扩散` 尚未实现

## 4. 资产化建议

### 4.1 `rules.yml`

主要负责：

- 行为触发条件
- 制度判断
- 风险标记
- 规则解释 key

### 4.2 `policies/*.yml`

主要负责：

- 巡查强度
- 敏感区域
- 特定时段风险参数
- 例外政策
- 对主体的保护偏置

也就是说：

- `rules` 负责定性
- `policies` 负责执行环境

当前还未完全做到的部分：

- relationship 后果参数仍未完整迁入 `policies`
- 记忆写入规则仍未抽成独立可配置 policy
- 动态 overlay 目前主要覆盖 world effects，到更细粒度执行调参还不完整

### 4.3 选择性执法的实现分层

建议把“是否需要执法 agent”拆成两个阶段处理。

第一阶段：

- 不引入执法智能体
- 先做平台级 `enforcement provider`
- 由 deterministic / probabilistic 模型决定：
  - 是否被观察到
  - 是否被记录
  - 是否升级为 `warn`
  - 是否升级为 `block`

第二阶段：

- 保留同一套 enforcement provider 接口
- 再允许其中一部分决策由执法 agent 接管
- 执法 agent 负责“谁在场、谁看见、谁介入”
- 规则裁决、审计格式、后果持久化仍由平台掌握

默认建议：

- 当前仓库先实现第一阶段
- 不要在治理语义尚未稳定时先引入执法 agent

## 4.4 第一阶段选择性执法的最小输入

平台级选择性执法模型，建议最少读取以下输入：

- `rule_evaluation.decision`
- `rule_evaluation.risk_level`
- `rule_evaluation.matched_tags`
- `policy.inspection_level`
- `policy.sensitive_locations`
- `policy.subject_protection_bias`
- `world.time_period`
- `actor.status.governance_attention_score`
- 当前地点与主体距离或主体相关信号

它们不一定都直接决定拦截，但至少应共同影响：

- `observation_score`
- `intervention_score`
- `record_only / warn / block` 的升级路径

## 4.5 第一阶段建议的执行语义

建议把当前“命中规则后直接映射治理结果”的模型，逐步过渡为：

1. 规则层先输出 `allowed / soft_risk / violates_rule / impossible`
2. 执行层先计算 `observed: true/false`
3. 若未观察到，可输出 `allow` 或 `record_only`
4. 若已观察到，再根据风险、地点、主体保护等级决定 `warn / block`
5. 后果层再决定写入多少长期状态

这样可以表达：

- 同样的违规，不一定每次都被发现
- 同样被发现，不一定每次都被拦截
- 高风险、主体附近、敏感地点更容易从 `warn` 升级为 `block`

## 4.6 为什么第一阶段不直接上执法 agent

如果现在直接引入执法 agent，会同时引入大量新的未决问题：

- 执法者是否有位置与巡逻路线
- 执法者是否也受世界规则约束
- 执法者如何获得观察信息
- 多个执法者如何分工
- 执法者的权限层级与误判如何建模

这些问题本身是一个独立子系统。

因此更合理的顺序是：

- 先稳定治理语义
- 再抽象 enforcement provider 接口
- 最后再考虑把 provider 的一部分实现替换为执法 agent

## 4.7 建议的 provider 接口草案

为了后续可平滑替换成执法 agent，第一阶段就应把执行器收敛成稳定接口。

建议最小输出结构至少包含：

```yaml
governance_execution:
  decision: allow | record_only | warn | block
  reason: string
  observed: true | false
  observation_score: 0.0
  intervention_score: 0.0
  matched_signals: []
```

说明：

- `decision` 继续作为现有兼容主字段
- `observed` 用于表达是否真的被世界治理机制发现
- `observation_score` 用于解释“为什么这次被看到/没被看到”
- `intervention_score` 用于解释“为什么只是警告/为什么升级到拦截”
- `matched_signals` 保持解释链兼容

这样未来即便改成执法 agent，也仍可以要求它输出同一份结构，再交给平台持久化。

## 5. 对智能体能力的意义

这套结构不会压死智能体，前提是保留灰区。

最应保留给智能体的自由度：

- 目标路径选择
- 风险偏好
- 社会互动策略
- 从后果中学习并修正

最不应交给智能体的部分：

- 法条裁决
- 基础物理约束
- 审计与持久化

一句话：

**规则提供边界，治理提供摩擦，智能体提供策略。**
