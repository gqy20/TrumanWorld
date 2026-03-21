# World Design Implementation Roadmap

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 总体策略

不直接重写 `sim` 主链路。

先做制度资产层，再做最小规则裁决层，最后补治理执行层和解释链。

当前实现状态：

- 已完成阶段 1、阶段 2、阶段 3 的最小可用版本
- 已完成阶段 4 的最小可用版本
- 已完成治理后果层的最小可用版本
- 已补上解释链的最小暴露路径：timeline `rule_evaluation / governance_execution`、agent context `world_rules_summary`
- 阶段 5 关系后果层仍停留在设计阶段

## 2. 推荐阶段

### 阶段 1：资产层落位

状态：`已完成（最小版）`

目标：

- 在 bundle 中新增 `constitution.md`
- 在 bundle 中新增 `rules.yml`
- 在 bundle 中新增 `policies/default.yml`
- 扩展 loader，支持读取完整 world design 资产包

这个阶段重点不是 evaluator，而是 schema 与边界。

当前已落地：

- `bundle_registry.py` 已支持读取 `rules.yml`、`policies/default.yml`、`constitution.md`
- `backend/app/scenario/runtime/world_design.py` 已装配统一 `WorldDesignRuntimePackage`
- `rules.yml` 缺失时回退为空规则集
- `policies/default.yml` 缺失时回退到平台默认 policy 值
- `constitution.md` 缺失时回退为空文本

### 阶段 2：统一 facts

状态：`已完成（最小版）`

目标：

- 定义平台 facts 命名空间
- 让 `rules.yml` 只引用统一 facts
- 避免规则资产直接耦合 Python 字段名

第一版建议支持：

- `actor.*`
- `target_agent.*`
- `target_location.*`
- `world.*`
- `policy.*`

当前已落地：

- 已有 `fact_resolver.py`
- 规则评估不再直接耦合零散 Python 字段名
- 当前 facts 主要覆盖 actor / target_agent / target_location / world / policy 几个基础域
- 仍未形成独立文档化 schema 校验器，属于运行时约定

### 阶段 3：最小规则裁决层

状态：`已完成（最小版）`

目标：

- 在动作进入 `ActionResolver` 前做规则评估
- 输出结构化裁决结果
- 不推翻现有物理校验和基础执行逻辑

第一版只需要支持少量规则模板和条件操作符。

当前已落地：

- 已有 `rule_evaluator.py`
- 当前支持按 `action_types` 触发、按事实条件匹配、按 `priority + decision` 排序裁决
- 当前决策类型为 `allowed / soft_risk / violates_rule / impossible`
- `soft_risk` 允许动作继续执行，但会附带解释结果
- `RuleEvaluationResult` 已可输出 `matched_tags`
- 这是最小实现，不代表最终治理语义

### 阶段 4：治理执行层

状态：`已完成（最小版）`

目标：

- 根据 `violates_rule` 或高风险裁决，决定是否观察到、是否介入
- 把执行强度主要交给 `policies/*.yml`
- 记录执行事件和长期状态变化

第一阶段不必实现完整政府组织模拟。

当前已落地：

- 已有 `governance_executor.py`
- 当前把 `rule_evaluation` 映射为 `allow / warn / block / record_only`
- `impossible` 当前固定映射为 `block`
- `soft_risk` 当前默认映射为 `warn`
- `violates_rule` 当前会根据 `inspection_level` 和命中的治理信号决定 `warn` 或 `block`
- `subject` / `sensitive_location` 等信号会把治理结果提升为更严格处置
- accepted / rejected event payload 已可附带 `governance_execution`
- agent context 已可读取最近 `block / warn` 结果形成轻量反馈

当前明确未实现：

- 选择性执法
- 观测概率 / 巡查概率
- 更细的长期处罚或违规记录持久化
- 政府或治理 agent
- 更细的 policy overlay 与运行时动态调度

### 阶段 4.5：治理后果层

状态：`已完成（最小版）`

目标：

- 把 `warn / block` 写入 agent 的长期状态
- 让治理执行真正形成跨 tick 的制度记忆
- 为 `current_risks` 和后续治理升级提供稳定输入

当前已落地：

- 已有 `governance_consequences.py`
- 当前会把 `warn / block` 写回 actor 自身的运行时 `status`
- 当前已落地的状态字段包括 `warning_count` 与 `governance_attention_score`
- `warn` 与 `block` 会以不同强度提升 `governance_attention_score`
- `governance_attention_score` 已开始驱动 agent context 中的 `current_risks`

当前明确未实现：

- 持久化层面的独立违规记录模型
- attention / warning 的时间衰减
- 治理后果对 relationship / reputation / economy 的外溢

### 阶段 5：关系后果层

状态：`未开始`

目标：

- 把 relationship 明确归入后果层，而不是继续散落在持久化细节中
- 让关系更新读取规则裁决结果与 `policy` 上下文
- 支持正向、负向和时间衰减三类变化
- 在 perception / prompt / API 中暴露派生后的 `relationship_level`

这一阶段重点不是做复杂社交图，而是让“关系为什么变化”可解释、可调参、可与场景一致。

## 3. 当前仓库的建议切入点

### 3.1 Bundle 侧

- 扩展 `backend/app/scenario/bundle_registry.py`
- 增加对 `rules.yml`、`constitution.md`、`policies/` 的加载能力

### 3.2 Runtime 侧

- 在 `backend/app/scenario/runtime/` 下增加 world design 运行时装配
- 把散落的 world design 配置收敛成一个 package

### 3.3 Simulation 侧

- 在 `backend/app/sim/` 下引入最小 rule evaluation
- 保留 `ActionResolver` 的底层执行职责
- 后续再补治理执行器
- 不再把 relationship 演化语义只写在持久化提交逻辑里

### 3.4 API / Timeline 侧

- 在 event payload 中增加规则解释信息
- 后续统一暴露到 timeline / agent detail

当前已落地：

- rejected / accepted event payload 已可附带 `rule_evaluation`
- rejected / accepted event payload 已可附带 `governance_execution`
- timeline payload 已可透传 `rule_evaluation / governance_execution`
- context event formatting 已补 `rule_feedback_reason / governance_feedback_reason`

### 3.5 Relationship 侧

- 定义 relationship update policy 的最小接口
- 支持根据事件类型、地点类型、时段和角色语义调制增量
- 在 context builder 中派生 `relationship_level`
- 避免运行时更新无条件覆盖 seed 的 `relation_type`

## 4. 当前不建议立即做的内容

- 完整经济系统
- 商品与许可体系
- 完整组织治理建模
- 复杂 DSL
- 让 agent 直接读完整规则文件

先把 world 设计的基础资产层和解释链打稳。

## 5. 下一步的具体实施建议

按当前代码状态，下一步应优先做：

1. `policy` 到执行层和后果层的映射继续细化，而不只是 inspection-level 与固定 attention delta
2. 规则反馈写入长期记忆或更稳定的 agent 学习闭环
3. relationship 后果层与规则裁决、治理处置结果打通
4. attention / warning 的衰减与恢复机制
5. 动态 policy overlay 与运行时调参
