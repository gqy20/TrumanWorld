# World Design Decisions

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 文档目的

这份文档不是展开新概念，而是收敛当前 world 设计里必须尽快明确的关键决策点。

目标：

- 避免后续实现阶段边做边改边界
- 让资产化、规则裁决、治理执行三条线有共同语言
- 为后续 schema 和代码实现提供稳定前提

## 2. 需要优先明确的七项决策

### 2.1 资产边界

必须先明确以下文件分别承载什么：

- `world.yml`
- `rules.yml`
- `policies/*.yml`
- `constitution.md`

当前建议：

- `world.yml`：静态事实、地点、节律、公开常识、基础字典
- `rules.yml`：制度规则、合法性判断、风险判断、优先级、解释 key
- `policies/*.yml`：动态政策、巡查强度、关闭地点、敏感区域、临时例外
- `constitution.md`：人类可读制度说明、冲突顺序、显规则与潜规则

需要明确的问题：

- `world.yml` 是否允许放“半规则内容”
- `policies` 是只覆盖参数，还是允许覆盖规则条目
- `constitution.md` 是否需要被 API 间接消费

### 2.2 平台事实空间

规则资产必须引用统一 facts，而不是直接耦合 Python 字段名。

第一版建议事实命名空间：

- `actor.*`
- `target_agent.*`
- `target_location.*`
- `world.*`
- `policy.*`

候选事实示例：

- `actor.location_id`
- `actor.workplace_id`
- `actor.status.<key>`
- `target_location.type`
- `target_location.capacity_remaining`
- `world.time_period`
- `world.is_weekend`
- `policy.closed_locations`

需要明确的问题：

- 是否允许规则直接读取 `actor.profile.*`
- `world_effects` 是否全部并入 `policy.*`
- 第一版是否允许自定义 scenario facts

### 2.3 裁决语义

规则层输出什么结果，必须先定。

当前建议至少区分：

- `allowed`
- `violates_rule`
- `impossible`

可选扩展：

- `soft_risk`
- `needs_enforcement_review`

需要明确的问题：

- 是否保留现有 `accepted/rejected` 作为对外兼容层
- `violates_rule` 是否允许动作先发生、后处罚
- `soft_risk` 是否独立于 `violates_rule`

### 2.4 治理执行层职责

必须明确治理执行层是不是独立存在。

当前建议：

- 是独立层
- 第一阶段不是完整政府 agent
- 更适合做平台级 `enforcement` 执行器

治理执行层负责：

- 是否发现
- 是否介入
- 是否拦截、警告、记录
- 如何施加后果

需要明确的问题：

- director 是否可以直接调治理参数
- 执行层是否写自己的事件类型
- 执行层是否能触发二次干预
- 第一阶段是否需要执法 agent，还是先用平台执行器

### 2.5 硬拦截与软违规边界

必须明确哪些情况由系统直接阻止，哪些情况进入治理层。

建议直接硬拦截：

- 地点不存在
- agent 不存在
- 容量已满
- 会话冲突
- 其他系统或物理不可执行约束

建议进入治理层：

- 制度违规
- 异常行为
- 高风险但非物理不可能行为

需要明确的问题：

- “地点关闭”是硬拦截还是治理拦截
- “夜间限制”是制度违规还是软风险
- “主角附近异常行为”是规则违规还是连续性风险

### 2.6 智能体可见摘要

需要明确 agent 到底看到什么制度信息。

当前建议不要直接暴露完整 `rules.yml`，而是暴露压缩摘要：

- 当前可行动作
- 当前高风险提示
- 当前政策通知
- 最近被拦或被警告的原因

需要明确的问题：

- 是否按角色暴露不同摘要
- 是否允许 agent 看到“原因”但看不到“条文”
- 是否要把最近的治理处置写进 agent 记忆

### 2.7 第一阶段范围

必须明确第一阶段做什么，不做什么。

建议第一阶段只覆盖：

- 动作：`move` / `work` / `talk` / `rest`
- 资产：`rules.yml`、`policies/default.yml`、`constitution.md`
- 裁决：最小规则评估
- 解释链：event payload 记录规则与治理结果

第一阶段不建议覆盖：

- 经济系统
- goods / permits
- 复杂组织治理
- 自定义脚本式 rule effect
- 完整政府机构建模

## 3. 推荐决策顺序

建议按以下顺序明确：

1. 资产边界
2. 平台 facts
3. 裁决语义
4. 硬拦截与软违规边界
5. 治理执行层职责
6. agent 可见摘要
7. 第一阶段范围

原因：

- 前 4 项决定 schema
- 第 5 项决定 sim 链路
- 第 6 项决定 agent context 设计
- 第 7 项决定当前迭代能否收敛

## 4. 当前建议的默认结论

如果需要先在没有最终共识时继续推进，建议采用以下默认结论：

- 资产采用四层：`world` / `rules` / `policies` / `constitution`
- 平台 facts 第一版只开放五个命名空间：`actor` / `target_agent` / `target_location` / `world` / `policy`
- 裁决语义至少区分 `allowed` / `violates_rule` / `impossible`
- 制度违规不等于物理拦截，先进入治理执行层
- 第一阶段治理执行层先采用平台级执行器，不直接引入执法 agent
- 智能体只读取压缩制度摘要，不直接读取完整法条
- 第一阶段只做最小资产层、最小规则裁决层和解释链

## 5. 后续可继续展开的子文档

建议后续补充：

- `RULES_SCHEMA.md`
- `POLICY_SCHEMA.md`
- `FACT_NAMESPACE.md`
- `AGENT_VISIBLE_SUMMARY.md`
- `NARRATIVE_WORLD_WORLD_DESIGN.md`
