# World Design Docs

世界设计专题目录。

这个目录专门沉淀 world 相关的设计细节，不与通用工程文档混写。

建议阅读顺序：

1. [../WORLD_RULE_SYSTEM.md](../WORLD_RULE_SYSTEM.md) - 平台级总纲
2. [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) - 当前最需要先明确的设计待决项
3. [ASSET_MODEL.md](ASSET_MODEL.md) - world 资产分层与 bundle 组织
4. [FACT_NAMESPACE.md](FACT_NAMESPACE.md) - 平台统一 facts 命名空间
5. [RULES_SCHEMA.md](RULES_SCHEMA.md) - `rules.yml` 第一版 schema 草案
6. [POLICY_SCHEMA.md](POLICY_SCHEMA.md) - `policies/default.yml` 第一版 schema 草案
7. [RULE_ENFORCEMENT_MODEL.md](RULE_ENFORCEMENT_MODEL.md) - 规则、治理执行、后果三层模型
8. [AGENT_VISIBLE_SUMMARY.md](AGENT_VISIBLE_SUMMARY.md) - agent 侧可见的制度摘要层
9. [RUNTIME_PACKAGE.md](RUNTIME_PACKAGE.md) - bundle 资产装配成 runtime package 的方式
10. [NARRATIVE_WORLD_WORLD_DESIGN.md](NARRATIVE_WORLD_WORLD_DESIGN.md) - 当前默认场景的 world design 示例
11. [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) - 面向当前仓库的落地顺序

适合放置：

- world bundle 结构设计
- 规则资产与政策资产 schema
- 治理执行与审计解释链设计
- agent 自由度与制度边界划分
- 面向具体 scenario 的世界设计讨论
