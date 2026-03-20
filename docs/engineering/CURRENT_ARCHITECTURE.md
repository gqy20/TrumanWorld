# AI Narrative World 当前架构设计

- 类型：`engineering`
- 状态：`active`
- 负责人：`repo`
- 基线日期：`2026-03-10`

## 1. 系统定位

当前系统是一个面向实验与观测的 AI 社会模拟系统：

- 可持续运行的 AI 小镇仿真器
- 带导演层观察、干预和统计面板的控制台
- 带 scenario 抽象的多题材雏形
- 带运行恢复、timeline、世界健康度、LLM 调用统计的实验系统

> 历史设计文档见 [../references/](../references/)

## 2. 当前后端结构

当前后端模块：

```text
backend/app/
├── api/           # HTTP 路由、查询、控制接口
├── sim/           # tick 编排、world state、调度与持久化主流程
├── agent/         # Agent runtime、prompt、provider、连接池
├── store/         # SQLAlchemy models、repository、持久化
├── scenario/      # 题材抽象层（narrative_world / open_world）
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

## 3. 当前前端定位

当前前端已经不只是简单的 run 控制页，而是一个导演控制台：

- run 列表与控制
- 世界地图 / 世界快照
- 时间线与故事流查看
- agent 详情、关系、记忆查看
- director interventions 查看与注入
- 世界健康度、活动分布、统计信息面板

## 4. 当前已落地的关键能力

- Run 创建、启动、暂停、恢复
- 自动 tick 调度
- timeline / world snapshot / agent detail 查询
- director manual injection
- director automatic planning
- subject alert / continuity risk 观测
- director memories 持久化
- LLM token 与成本统计
- scenario_type 持久化与按题材运行
- 事件增量查询（since_tick 参数，节省 99% 带宽）

## 5. 当前已知设计张力

当前实现大体可用，但仍存在一些需要后续收敛的点：

- `scenario` 抽象已基本收口，但仍保留少量兼容层与历史命名
- 文档里宣称的 `Redis` / `pgvector` 能力目前更多是预留而非主链路依赖
- API 和前端暴露了不少内部运行与观测细节
- 测试主链路仍以 SQLite 为主，和生产 PostgreSQL 有差距

这部分不影响把系统描述为“当前实现”，但说明它仍处于快速演进阶段。

## 6. 阅读顺序建议

如果你是第一次进入项目，建议按这个顺序看：

1. [../engineering/DEVELOPMENT.md](../engineering/DEVELOPMENT.md)
2. [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md)
3. [../references/SCENARIOS.md](../references/SCENARIOS.md)
