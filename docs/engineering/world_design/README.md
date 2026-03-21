# World Design Docs

世界设计专题目录。

这个目录专门沉淀 world 相关的设计细节，不与通用工程文档混写。

当前状态：

- 已落地最小闭环：runtime package、facts namespace、最小 rule evaluator、最小 governance executor、最小 governance consequences、sim 接入、timeline 解释链、agent 侧轻量制度摘要
- 已新增：动态 world effects 到 policy facts 的最小 overlay、agent detail/front-end 摘要展示、规则反馈写入长期记忆
- 已新增：governance ledger、director 治理历史视图、粗糙治理 + 生计状态 MVP 设计稿
- 尚未落地：完整 reputation/economy/world evolution 扩展、更完整的动态 policy 调参与统一 feedback schema

建议阅读顺序：

1. [../WORLD_RULE_SYSTEM.md](../WORLD_RULE_SYSTEM.md) - 平台级总纲
2. [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) - 当前最需要先明确的设计待决项
3. [ASSET_MODEL.md](ASSET_MODEL.md) - world 资产分层与 bundle 组织
4. [FACT_NAMESPACE.md](FACT_NAMESPACE.md) - 平台统一 facts 命名空间
5. [RULES_SCHEMA.md](RULES_SCHEMA.md) - `rules.yml` 第一版 schema 草案
6. [POLICY_SCHEMA.md](POLICY_SCHEMA.md) - `policies/default.yml` 第一版 schema 草案
7. [RULE_ENFORCEMENT_MODEL.md](RULE_ENFORCEMENT_MODEL.md) - 规则、治理执行、后果三层模型
8. [AGENT_VISIBLE_SUMMARY.md](AGENT_VISIBLE_SUMMARY.md) - agent 侧可见的制度摘要层
9. [RELATIONSHIP_MODEL.md](RELATIONSHIP_MODEL.md) - 关系网络的状态模型、演化规则与边界
10. [MENTAL_STATE_MODEL.md](MENTAL_STATE_MODEL.md) - Agent 心智状态模型（情感/需求/认知）
11. [GOVERNANCE_ECONOMIC_MVP.md](GOVERNANCE_ECONOMIC_MVP.md) - 粗糙治理与最小生计闭环的一期方案
12. [RUNTIME_PACKAGE.md](RUNTIME_PACKAGE.md) - bundle 资产装配成 runtime package 的方式
13. [NARRATIVE_WORLD_WORLD_DESIGN.md](NARRATIVE_WORLD_WORLD_DESIGN.md) - 当前默认场景的 world design 示例
14. [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) - 面向当前仓库的落地顺序

适合放置：

- world bundle 结构设计
- 规则资产与政策资产 schema
- 治理执行与审计解释链设计
- agent 自由度与制度边界划分
- 面向具体 scenario 的世界设计讨论
