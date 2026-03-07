# AI Truman World MVP 架构设计

- 版本：`v0.1.0`
- 状态：`MVP 精简版`
- 最后更新：`2026-03-07`

## 1. 架构结论

MVP 推荐架构：

- 后端：`Python`
- 前端：`TypeScript`
- 智能体认知：`Claude Agent SDK`
- 存储：`Postgres + pgvector`

一句话：

> 用 Python 做仿真和智能体编排，用 TypeScript 做导演控制台。

## 2. 为什么这样收缩

之前的设计更像完整平台，MVP 会有这些风险：

- 模块太多，第一版落地慢
- 表太多，迁移和查询复杂
- 前端目标太大，拖慢主路径

因此精简原则是：

- 保留仿真主干
- 保留导演层
- 保留结构化事件
- 保留最小记忆闭环
- 砍掉非关键独立模块

## 3. 精简架构图

```text
                   Director Layer
              Next.js + TypeScript UI
                           |
                           v
                    FastAPI API Layer
                           |
        +------------------+------------------+
        |                  |                  |
        v                  v                  v
      sim               agent              store
  tick/world/rules   Claude SDK        db/event/memory
                           |
                           v
                Postgres + pgvector
```

## 3.1 Scenario Layer

当前后端已经在 `sim / agent / director` 之外补了一层 `scenario`：

- `backend/app/scenario/base.py`
- `backend/app/scenario/truman_world/scenario.py`
- `backend/app/scenario/open_world/scenario.py`

这一层的职责是：

- 组织题材特定规则
- 配置 runtime 与 agent context
- 连接 director、state updater、seed builder
- 向 `SimulationService` 暴露统一接口

也就是说：

- `sim` 负责世界运行
- `agent` 负责认知与决策
- `director` 负责观察和轻计划
- `scenario` 决定“这个世界按什么题材运行”

目前已经落地两个 scenario：

- `TrumanWorldScenario`
- `OpenWorldScenario`

其中 `OpenWorldScenario` 是一个最小示例，用来验证这套抽象不是只服务 Truman world。

## 4. 语言边界

### 后端：Python

后端负责：

- simulation loop
- run lifecycle
- action resolver
- agent orchestration
- Claude Agent SDK 接入
- event / memory persistence

### 前端：TypeScript

前端负责：

- 导演控制台
- run 控制
- timeline 查看
- agent 详情页

结论很明确：

- 不做 Node.js 后端主逻辑
- 不做 Python 前端模板主导 UI

## 5. 模块收缩方案

MVP 后端只保留 4 个模块：

- `api`
- `sim`
- `agent`
- `store`

### `api`

负责：

- HTTP API
- run 控制
- 查询

### `sim`

负责：

- SimulationRunner
- WorldState
- ActionResolver
- tick 推进
- 关系更新
- 场景无关的 orchestration

不再负责：

- Truman world 的 heuristic
- Truman world 的 seed 数据
- Truman world 的状态更新规则

这些逻辑已经上浮到 `scenario/`。

### `agent`

负责：

- Claude Agent SDK 封装
- agent registry
- agent config loader
- prompt loader
- planner
- reactor
- reflector

注意：

- `dialogue_generator` 不单独作为模块
- 先作为 `reactor` 的一个分支场景

### `store`

负责：

- SQLAlchemy models
- event persistence
- memory retrieval
- run state persistence

## 6. 基于 IssueLab 的智能体架构参考

TrumanWorld 的智能体层建议参考 `IssueLab` 的这几个做法：

- agent 配置独立放在 `agents/<id>/`
- `agent.yml` 和 `prompt.md` 分离
- MCP、skills、subagents 作为可选能力
- runtime 只负责执行，不直接承担系统总控

参考仓库：

- `gqy20/IssueLab`

参考点：

- `agents/<user>/agent.yml`
- `agents/<user>/prompt.md`
- `.mcp.json`
- `.claude/skills/`
- `.claude/agents/`

### 6.1 推荐目录结构

```text
agents/
  alice/
    agent.yml
    prompt.md
    .mcp.json         # optional
    .claude/skills/   # optional
    .claude/agents/   # optional
```

### 6.2 为什么这个设计适合 TrumanWorld

因为它天然解决了几个问题：

- agent 人格不会硬编码在 Python 代码里
- 新增 agent 不需要修改核心逻辑
- 单个 agent 的能力边界可以独立配置
- prompt、工具、技能可以按 agent 维度管理

### 6.3 与 IssueLab 的关键差异

TrumanWorld 不能直接照搬 `IssueLab`，因为两者运行模型不同。

`IssueLab` 更像：

- 事件触发式 agent 执行
- 基于 GitHub workflow 的 orchestration
- 单次任务型状态

TrumanWorld 则是：

- tick-based 持续仿真
- 世界状态长期存在
- agent 拥有持续记忆和关系演化

所以可以复用的是：

- agent registry 方式
- prompt/config 分离方式
- 能力开关方式
- Claude Agent SDK runtime 封装方式

不能复用的是：

- GitHub Actions orchestration
- workflow dispatch 触发模型
- Issue 驱动的单轮任务流

## 7. Agent Runtime 细化

建议 `agent` 模块内部继续分成：

```text
agent/
  registry.py
  config_loader.py
  prompts/
    system.md
  system_prompt.py
  prompt_loader.py
  runtime.py
  context_builder.py
  planner.py
  reactor.py
  reflector.py
```

### `registry.py`

负责扫描 `agents/*/agent.yml`，构建可用 agent 列表。

### `config_loader.py`

负责解析：

- 人格
- 职业
- home
- model config
- capability switches

### `prompt_loader.py`

负责加载 `agents/<id>/prompt.md`，并与世界上下文、记忆上下文拼装。

### `prompts/system.md`

负责维护项目级 system prompt，包括：

- 统一语言要求
- 世界规则边界
- 输出边界
- 全局行为约束

这个文件不承载具体角色人格。

### `system_prompt.py`

负责加载 `prompts/system.md`，供 Claude Agent SDK 的 `system_prompt` 选项统一注入。

分层约定：

- `prompts/system.md` 负责全局规则
- `agents/<id>/prompt.md` 负责角色身份与风格
- `prompt_loader.py` 负责运行时上下文拼装

### `runtime.py`

负责统一封装 Claude Agent SDK 的调用入口。

### `context_builder.py`

负责组装：

- 当前世界状态
- 当前地点
- nearby agents
- retrieved memories
- 当前目标

### 能力开关建议

参考 `IssueLab` 的设计，建议保留显式开关：

- `enable_reflection`
- `enable_dialogue`
- `enable_mcp`
- `enable_subagents`

这样后面可以方便地区分：

- 普通居民 agent
- 社交型 agent
- 特殊角色 agent

## 8. 不单独拆分的内容

以下内容先不独立成大模块：

- `Social Engine`
- `Memory Engine`
- `Observation Engine`

原因：

- 社会关系更新可以在 `sim` 中作为事件后的派生逻辑
- 记忆写入和检索可以在 `store` 中完成
- 观察能力就是 `api` 查询能力，不必单独叫一个 engine

## 9. 精简数据表

MVP 只保留 6 张表：

- `simulation_runs`
- `locations`
- `agents`
- `events`
- `relationships`
- `memories`

### 表职责

#### `simulation_runs`

- run 生命周期
- 当前 tick
- 当前状态

#### `locations`

- 地点信息
- 坐标
- 容量

#### `agents`

- 当前状态
- 当前目标
- 当前地点
- profile / personality

#### `events`

- 所有结构化事件
- 包括 talk 事件
- 包括导演注入事件

#### `relationships`

- familiarity
- trust
- affinity

#### `memories`

- recent
- episodic
- reflection

### 明确不建的表

- `world_ticks`
- `conversations`

原因：

- tick 先由 `simulation_runs.current_tick` + `events` 表达
- 对话先放在 `events.payload`

## 10. Tick 流程

每个 tick 只走一个主流程：

```text
1. 推进世界时间
2. 选择一个 agent
3. 判断是否需要 Claude cognition
4. 生成动作意图
5. 校验动作
6. 应用动作
7. 写 event
8. 更新 relationship
9. 写 memory
```

这比拆成很多“引擎间调用”更适合 MVP。

## 11. Claude Agent SDK 的使用边界

只在以下场景调用：

- 早晨生成粗粒度日计划
- 遇到社交或异常事件时做 reaction
- 晚上做 reflection

不在以下场景调用：

- 每个 tick 的基础移动
- 简单 work/rest 执行
- 直接改 world state

### 调用前置步骤

每次进入 Claude cognition 前，统一走：

1. 从 registry 获取 agent 配置
2. 加载 prompt.md
3. 根据能力开关决定是否加载 MCP、skills、subagents
4. 由 context builder 拼装输入
5. 调用 planner / reactor / reflector

## 12. 导演层设计

导演层是 MVP 的产品特征，但范围要小。

### 只保留 4 个导演能力

- `start_run`
- `pause_run`
- `inspect`
- `inject_event`

### 事件注入范围

只允许简单世界事件：

- 某地点举办活动
- 某地点关闭
- 广播公共消息

不允许：

- 直接改 agent 属性
- 直接改 relationships
- 直接改 memories

## 13. 前端范围

MVP 前端只保留：

- `/runs`
- `/runs/[id]`
- `/runs/[id]/timeline`
- `/runs/[id]/agents/[agentId]`

不做：

- 复杂 graph 页面
- replay 动画页面
- 复杂地图渲染

## 14. API 范围

MVP 核心接口：

- `POST /runs`
- `POST /runs/{id}/start`
- `POST /runs/{id}/pause`
- `POST /runs/{id}/resume`
- `POST /runs/{id}/director/events`
- `GET /runs/{id}`
- `GET /runs/{id}/timeline`
- `GET /runs/{id}/agents/{agent_id}`

## 15. 第一阶段实现顺序

建议实现顺序：

1. `simulation_runs / agents / locations / events` 表
2. `SimulationRunner`
3. agent registry + config loader + prompt loader
4. 基础 rule-based 动作
5. timeline API
6. Claude planner / reactor / reflector
7. memories / relationships
8. director event injection
9. 简单前端页面

## 16. 最终判断

更适合 MVP 的架构不是“完整平台架构”，而是：

- 一个小而稳的 simulation core
- 一个受控的 Claude cognition 层
- 一套参考 `IssueLab` 的 agent registry / runtime 体系
- 一个最小导演控制台
- 一套足够解释行为的事件与记忆数据

先把这个闭环跑通，比一开始把系统拆得很漂亮更重要。
