# AI Truman World 当前架构设计

- 状态：`Current Implementation`
- 基线日期：`2026-03-10`

## 1. 文档定位

这份文档描述的是仓库**当前已经落地的实现**，不是最初的 MVP 设想。

如果你想了解最初为什么要收缩范围、MVP 当时刻意不做什么，请看：

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [PRD.md](PRD.md)
- [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md)

## 2. 当前系统定位

当前项目已经不只是“最小可运行 Truman World MVP”，而是一个：

- 可持续运行的 AI 小镇仿真器
- 带导演层观察、干预和统计面板的控制台
- 带 scenario 抽象的多题材雏形
- 带运行恢复、timeline、世界健康度、LLM 调用统计的实验系统

一句话：

> 现在的 TrumanWorld 更接近“面向实验与观测的 AI 社会模拟系统”，而不只是最初定义里的 MVP 样机。

## 3. 当前后端结构

当前后端模块：

```text
backend/app/
├── api/           # HTTP 路由、查询、控制接口
├── sim/           # tick 编排、world state、调度与持久化主流程
├── agent/         # Agent runtime、prompt、provider、连接池
├── store/         # SQLAlchemy models、repository、持久化
├── scenario/      # 题材抽象层（truman_world / open_world）
├── director/      # 观察、策略、计划、干预记忆
├── infra/         # settings、logging、db
└── protocol/      # 协议定义
```

核心关系：

- `sim` 负责仿真主流程与 tick 编排
- `agent` 负责认知调用与 prompt/runtime 拼装
- `director` 负责观察、计划、干预策略
- `scenario` 负责题材特定规则和上下文注入
- `store` 负责状态持久化

## 4. 当前前端定位

当前前端已经不只是简单的 run 控制页，而是一个导演控制台：

- run 列表与控制
- 世界地图 / 世界快照
- 时间线与故事流查看
- agent 详情、关系、记忆查看
- director interventions 查看与注入
- 世界健康度、活动分布、统计信息面板

## 5. 当前已落地的关键能力

- Run 创建、启动、暂停、恢复
- 自动 tick 调度
- timeline / world snapshot / agent detail 查询
- director manual injection
- director automatic planning
- Truman suspicion / continuity risk 观测
- director memories 持久化
- LLM token 与成本统计
- scenario_type 持久化与按题材运行

## 6. 当前与 MVP 设计的主要差异

相对最初的 MVP 设计，当前实现新增或扩展了这些方向：

- 增加了 `scenario` 抽象层
- 增加了 `director` 独立模块
- 增加了更多 API 和观测接口
- 增加了运行恢复和调度生命周期
- 增加了世界健康度与 director 统计面板
- 增加了 `llm_calls` 统计链路

这些能力使当前系统更强，但也意味着它不再适合继续用“纯 MVP 架构”来描述。

## 7. 当前已知设计张力

当前实现大体可用，但仍存在一些需要后续收敛的点：

- `scenario` 抽象还未完全收口，主流程仍残留 Truman world 特定耦合
- 文档里宣称的 `Redis` / `pgvector` 能力目前更多是预留而非主链路依赖
- API 和前端暴露了不少内部运行与观测细节
- 测试主链路仍以 SQLite 为主，和生产 PostgreSQL 有差距

这部分不影响把系统描述为“当前实现”，但说明它仍处于快速演进阶段。

## 8. 阅读顺序建议

如果你是第一次进入项目，建议按这个顺序看：

1. [DEVELOPMENT.md](DEVELOPMENT.md)
2. [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md)
3. [SCENARIOS.md](SCENARIOS.md)
4. [PRD.md](PRD.md) 与 [ARCHITECTURE.md](ARCHITECTURE.md) 作为历史基线参考
