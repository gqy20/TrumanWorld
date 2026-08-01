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
- [GODOT_3D_CLIENT_SPIKE.md](GODOT_3D_CLIENT_SPIKE.md) - Godot Web 3D 客户端后续技术验证计划
- [EVENTS_INCREMENTAL_QUERY.md](EVENTS_INCREMENTAL_QUERY.md) - 事件增量查询（✅ 已实现）
- [PERSISTENCE_REFACTOR_PLAN.md](PERSISTENCE_REFACTOR_PLAN.md) - persistence / tick 写入事务边界重构计划
- [roadmap.md](roadmap.md) - 近期工程重构路线图
- [AGENT_BACKEND_ABSTRACTION.md](AGENT_BACKEND_ABSTRACTION.md) - Agent backend 解耦与 Claude/LangGraph 双选设计
- [SCENARIO_DECOUPLING_MIGRATION.md](SCENARIO_DECOUPLING_MIGRATION.md) - 场景解耦迁移结果与当前规范字段
- [WORLD_RULE_SYSTEM.md](WORLD_RULE_SYSTEM.md) - 平台级世界宪法 / 规则系统 / 社会演化机制设计
- [world_design/README.md](world_design/README.md) - world 设计专题目录，细化资产层、治理执行层与落地路线

world design 当前状态：

- 已落地最小闭环：bundle 资产加载、runtime package、facts、最小 rule evaluator、最小 governance executor / consequences、timeline 解释链、agent 轻量摘要
- 已落地最小经济与治理运营接口：governance ledger、cases / restrictions API、agent economic summary API
- 尚未落地：结构化 `mental_state`、前端完整治理/经济运营视图、更完整的 reputation / economy / world evolution 扩展
