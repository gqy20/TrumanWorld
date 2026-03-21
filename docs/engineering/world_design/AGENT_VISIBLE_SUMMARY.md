# Agent Visible Summary

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 目标

agent 不应直接读取完整 `rules.yml` 或 `policies/*.yml`。

平台应把复杂制度状态压缩成 agent 可理解、可行动的摘要。

一句话：

**agent 读取制度摘要，不直接读取法条原文。**

## 2. 为什么要有这一层

如果直接把完整规则暴露给 agent，会带来几个问题：

- prompt 负载过大
- agent 行为容易退化成“逐条合规检查”
- 平台难以调整规则实现而保持 agent 接口稳定
- 很多治理参数和内部解释并不适合直接暴露

因此平台需要单独定义 agent-facing summary。

## 3. 这一层的职责

agent visible summary 负责回答：

- 我现在可以安全做什么
- 我现在做什么风险更高
- 当前有哪些环境或政策变化
- 我最近因为什么被拦、被警告或失败

它不负责回答：

- 规则引擎内部如何求值
- 具体命中了哪条内部规则
- 治理执行层使用了哪些内部阈值

## 4. 第一版建议结构

建议在 agent runtime context 中增加一段结构化摘要：

```yaml
world_rules_summary:
  available_actions: []
  blocked_constraints: []
  current_risks: []
  policy_notices: []
  recent_rule_feedback: []
```

## 5. 字段建议

### 5.1 `available_actions`

表示当前时刻对该 agent 来说优先可行或相对稳妥的动作。

示例：

- `move`
- `talk`
- `rest`
- `work`

说明：

- 这不是全量系统能力枚举
- 更偏“当前可行动作摘要”

### 5.2 `blocked_constraints`

表示当前明确不可行或应避免的约束。

示例：

- `目标地点已关闭`
- `当前地点已满员，无法进入`
- `当前处于会话流程中，不能切换其他动作`

说明：

- 可以是人类可读短句
- 也可以附带结构化 `reason_code`

### 5.3 `current_risks`

表示当前环境中的风险提示。

示例：

- `夜间社交会提高异常风险`
- `主体附近的异常行为更容易被注意`
- `敏感区域中的聚集行为风险较高`

说明：

- 重点是让 agent 理解“风险上升”，而不是直接禁止

### 5.4 `policy_notices`

表示当前正在生效的关键政策或环境变化。

示例：

- `咖啡馆临时关闭`
- `广场有活动，社交机会增加`
- `医院区域停电`

说明：

- 这层最适合承载世界变化通知

### 5.5 `recent_rule_feedback`

表示最近与 agent 自身相关的制度反馈。

示例：

- `你刚才试图进入关闭地点，被拦下`
- `你最近的深夜社交行为提高了风险`
- `你在敏感区域的异常行为引起了注意`

说明：

- 这是 agent 学习闭环的关键
- 应尽量和最近事件、记忆形成一致

## 6. 按角色暴露

建议这一层允许按角色做差异化摘要，而不是完全相同。

例如：

- 主体角色更容易看到“我感到异常”类反馈
- cast/support 更容易看到“保持自然”“避免异常引导”类风险提示
- 背景角色只看到最基础的政策通知和行动约束

这层差异化应由 scenario runtime bridge 负责组装，而不是让 rule engine 自己决定。

## 7. 与内部规则解释的边界

建议：

- agent 可以看到“为什么不合适”
- agent 不一定要看到“命中了哪条内部 rule_id”
- agent 原则上不直接看到内部优先级和执行阈值

这是为了避免 agent 过度 meta-game 平台内部机制。

## 8. 与记忆系统的关系

`recent_rule_feedback` 不应只是临时 prompt 文本。

更合理的做法是：

- 当治理执行或规则反馈对 agent 有显著影响时
- 将其中一部分写入 agent 可检索记忆

这样 agent 才能形成真正的长期策略，而不是只依赖单次上下文窗口。

## 9. Narrative World 的建议摘要

对 `narrative_world`，第一版建议重点暴露：

- 当前地点或附近地点的关闭/停电/活动通知
- 当前是否处于高风险时段
- 主体附近异常行为的风险提示
- 最近被拦、被警告、被注意的原因

不建议直接暴露：

- 完整治理参数
- 所有 rule_id
- 内部巡查概率

## 10. 第一版默认结论

建议默认采用：

- agent 只读取结构化制度摘要
- 摘要以 `available_actions / blocked_constraints / current_risks / policy_notices / recent_rule_feedback` 为核心
- 可按角色差异化暴露
- 近期显著反馈应与记忆系统衔接

## 11. 后续待展开问题

后续可继续细化：

- 摘要是纯文本还是结构化对象
- 如何控制摘要长度
- 哪些治理事件应写入长期记忆
