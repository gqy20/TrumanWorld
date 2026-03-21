# Engineering Docs

工程与实现目录。

适合放置：

- 当前实现说明
- 环境搭建
- 测试与质量规范
- 代码结构说明

当前文档：

- [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md)
- [DEVELOPMENT.md](DEVELOPMENT.md)
- [EVENTS_INCREMENTAL_QUERY.md](EVENTS_INCREMENTAL_QUERY.md) - 事件增量查询（✅ 已实现）
- [AGENT_BACKEND_ABSTRACTION.md](AGENT_BACKEND_ABSTRACTION.md) - Agent backend 解耦与 Claude/LangGraph 双选设计
- [SCENARIO_DECOUPLING_MIGRATION.md](SCENARIO_DECOUPLING_MIGRATION.md) - 场景解耦迁移结果与当前规范字段
- [WORLD_RULE_SYSTEM.md](WORLD_RULE_SYSTEM.md) - 平台级世界宪法 / 规则系统 / 社会演化机制设计
- [world_design/README.md](world_design/README.md) - world 设计专题目录，细化资产层、治理执行层与落地路线

world design 当前状态：

- 已落地最小闭环：bundle 资产加载、runtime package、facts、最小 rule evaluator、timeline 解释链、agent 轻量摘要
- 尚未落地：治理执行层、动态 policy overlay、关系与经济的完整后果层
