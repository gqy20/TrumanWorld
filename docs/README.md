# Narrative World 文档中心

> 当前仓库采用轻量文档结构：产品、工程、运维、参考。

## 1. 文档目录

| 目录 | 职责 | 说明 |
|------|------|------|
| [product/](product/README.md) | 产品与功能定义 | 说明要做什么、目标用户是谁、功能边界在哪里 |
| [engineering/](engineering/README.md) | 工程与实现 | 当前实现、环境搭建、代码结构、工程约定 |
| [operations/](operations/README.md) | 运维与部署 | 部署、发布、运行质量与 runbook |
| [references/](references/README.md) | 参考材料 | 场景资料、估算、任务拆解、历史设计稿 |

## 2. 快速导航

### 我想了解当前系统

1. 看 [engineering/CURRENT_ARCHITECTURE.md](engineering/CURRENT_ARCHITECTURE.md)
2. 再看 [engineering/DEVELOPMENT.md](engineering/DEVELOPMENT.md)
3. 如需题材资料，补看 [references/SCENARIOS.md](references/SCENARIOS.md)

### 我想了解产品方向

1. 看 [product/FEATURE_WORLD_2D_SCENE.md](product/FEATURE_WORLD_2D_SCENE.md)
2. 如需历史基线，补看 [references/PRD.md](references/PRD.md)

### 我想做技术决策

1. 看 [engineering/CURRENT_ARCHITECTURE.md](engineering/CURRENT_ARCHITECTURE.md)
2. 看 [engineering/WORLD_RULE_SYSTEM.md](engineering/WORLD_RULE_SYSTEM.md)
3. 看 [engineering/world_design/README.md](engineering/world_design/README.md)
4. 看 [references/BUILD_VS_BUY.md](references/BUILD_VS_BUY.md)
5. 如需回看 MVP 方案，看 [references/MVP_ARCHITECTURE.md](references/MVP_ARCHITECTURE.md)

### 我想部署和排障

1. 看 [operations/RAILWAY_DEPLOYMENT.md](operations/RAILWAY_DEPLOYMENT.md)
2. 看 [operations/RUN_QUALITY.md](operations/RUN_QUALITY.md)

## 3. 文档约定

### 3.1 文档类型

- 功能文档使用 `FEATURE_<TOPIC>.md`
- 工程实现文档使用稳定主题名，如 `CURRENT_ARCHITECTURE.md`、`DEVELOPMENT.md`
- 运维文档优先使用 `RUNBOOK_<TOPIC>.md` 或 `<PLATFORM>_DEPLOYMENT.md`

### 3.2 使用原则

- 新功能文档优先放在 `product/`
- 与代码实现直接相关的说明优先放在 `engineering/`
- 世界制度、规则资产、治理执行、world bundle 设计细节优先放在 `engineering/world_design/`
- 部署、运行和排障优先放在 `operations/`
- 估算、历史稿和分析材料放在 `references/`

## 4. 外部入口

- 项目总览：[../README.md](../README.md)
- 贡献流程：[../CONTRIBUTING.md](../CONTRIBUTING.md)
- 版本记录：[../CHANGELOG.md](../CHANGELOG.md)
