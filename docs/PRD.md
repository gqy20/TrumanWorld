# AI Truman World MVP 产品需求文档

- 版本：`v0.1.0`
- 状态：`MVP 精简版`
- 最后更新：`2026-03-08`

## 1. 产品定义

### 1.1 核心概念

**你就是楚门世界的导演。**

AI Truman World 是一个 AI 社会模拟系统。在这个小镇里，AI 居民们自然地生活、工作、社交。其中有一个”主角”(Truman)，他不知道自己是 AI —— 他有自己的生活、困惑、情感、成长。其他居民与他共享这个世界，自然地互动。

**你的任务**：观察、记录、创造条件——让 Truman 能真实地生活。

### 1.2 哲学定位

- **世界是假的，但 Truman 是真的** — 载体是人工构建的，但 Truman 的体验、情感、困惑都是真实的
- **意识即真实** — 不因为是 AI 就不真实，当有情感、有困惑、有成长，就是一个真实的主体
- **自由与选择** — Truman 有权利知道真相，也有权利选择留下或离开
- **观察者的反思** — 当我们观察 Truman 时，我们也在问：我们是否也生活在某个”楚门的世界”里？

### 1.3 MVP 范围

MVP 的目标不是做完整 AI 文明平台，而是先做出一个”能连续跑起来的小镇世界”：

- `10-20` 个 agent（包括 1 个 Truman，其他为 Cast）
- `1` 个小镇
- 可暂停 / 恢复
- 可查看事件流
- 可查看单个 agent 的状态、记忆和关系
- 可由导演层注入简单事件
- Truman 怀疑度追踪

一句话：

> 做一个可运行、可解释、可干预的 AI 小镇仿真器——你是观众，也是陪伴者。

## 2. MVP 要解决的问题

当前多数 agent demo 的问题不是 agent 不会说话，而是：

- 不能长期运行
- 状态不容易恢复
- 行为缺乏结构化记录
- 很难解释“为什么发生了这个行为”

所以 MVP 的核心不是“最聪明的 agent”，而是：

- 稳定运行
- 结构化事件
- 简单记忆闭环
- 基本导演控制

## 3. MVP 目标

MVP 只追求以下结果：

- 支持 `10-20` 个 agent 在一个小镇持续运行
- 支持 `3-7` 个模拟日的连续推进
- 支持 `start / pause / resume`
- 支持 timeline 查看
- 支持 agent 详情查看
- 支持简单事件注入
- 支持从事件到记忆的基本追溯

## 4. 非目标

MVP 不做：

- 经济系统
- 政治系统
- 组织系统
- 复杂关系图前端
- 独立 replay 动画系统
- 3D 场景
- 100+ agent 扩展
- 所有动作都走 LLM

## 5. 用户与场景

### 5.1 目标用户

- AI 研究者 — 观察 AI 社会的涌现行为和社交动态
- 创意工作者 — 生成独特的故事情节和角色关系
- 产品探索者 — 研究 AI agent 的产品形态边界
- 每一个对真实感到困惑的人

### 5.2 核心场景

#### 场景 1：持续运行

用户创建一个包含 `15` 个 agent 的小镇，连续运行多个模拟日，观察行为和关系变化。

#### 场景 2：导演干预

用户在运行过程中注入一个事件，例如：

- 咖啡馆开派对
- 公园关闭
- 广场广播一条公共消息

然后观察 agent 如何响应。

#### 场景 3：行为解释

用户点开一个 agent，查看：

- 当前状态
- 最近事件
- 相关记忆
- 对某个他人的关系变化

## 6. 产品原则

### 6.1 仿真层是权威

世界状态只能由仿真层推进和写入。

### 6.2 Claude 只做高价值认知

Claude Agent SDK 只用于：

- 日计划
- 特殊情境反应
- 对话生成
- 每日反思

不用于：

- 每个 tick 的基础动作
- 世界状态直接修改

### 6.3 导演层只能干预，不能绕过规则

导演层只能：

- 控制 run
- 查询状态
- 注入受控事件

不能直接改底层状态。

## 7. MVP 功能范围

### 7.1 世界

- 一个固定小镇
- `5-8` 个地点
- 固定 tick 推进
- 地点容量和基础移动规则

### 7.2 Agent

每个 agent 有：

- 身份
- 人格
- 当前地点
- 当前目标
- 简单状态
- 最近记忆
- 长期记忆
- 关系状态

### 7.2.1 Agent 配置方式

MVP 的 agent 配置方式参考 `IssueLab` 的注册表思路，但改造成适合仿真的形态。

每个 agent 使用独立目录：

```text
agents/
  alice/
    agent.yml
    prompt.md
    .mcp.json         # 可选
    .claude/skills/   # 可选
    .claude/agents/   # 可选
```

设计目标：

- 把 agent 人格和配置从代码里解耦
- 支持后续新增不同职业和人格的 agent
- 支持为单个 agent 打开或关闭特定能力

### 7.2.2 agent.yml 最小字段

MVP 建议每个 agent 至少包含以下字段：

- `id`
- `name`
- `occupation`
- `home`
- `personality`
- `model`
- `capabilities`

示例：

```yaml
id: alice
name: Alice
occupation: barista
home: apartment_a
personality:
  openness: 0.7
  conscientiousness: 0.6
capabilities:
  reflection: true
  dialogue: true
  mcp: false
model:
  max_turns: 8
  max_budget_usd: 1.0
```

### 7.3 动作

MVP 只保留 4 类核心动作：

- `move`
- `talk`
- `work`
- `rest`

### 7.4 记忆

MVP 只保留 3 类记忆：

- recent
- episodic
- reflection

### 7.5 导演层

MVP 只保留 4 类导演能力：

- run 控制
- 全局查看
- 单 agent 查看
- 简单事件注入

## 8. 精简后的系统能力

MVP 后端只需要 4 个核心模块：

- `api`
- `sim`
- `agent`
- `store`

说明：

- `sim` 负责 tick、world state、action resolver
- `agent` 负责 Claude Agent SDK 接入
- `store` 负责持久化、记忆检索、事件写入
- `api` 负责控制和查询

其中 `agent` 模块参考 `IssueLab` 的做法，分为两部分：

- agent 注册与配置加载
- agent runtime 与 Claude Agent SDK 调用

不单独拆：

- Social Engine
- Memory Engine
- Observation Engine

这些能力先作为 `sim` 或 `store` 的内部逻辑实现。

## 9. 精简后的数据模型

MVP 只保留 6 张核心表：

- `simulation_runs`
- `locations`
- `agents`
- `events`
- `relationships`
- `memories`

### 为什么砍掉其他表

- `world_ticks` 先不用独立表，timeline 先基于 `events`
- `conversations` 先并入 `events.payload`

这样更利于快速落地。

## 10. 核心流程

每个 tick：

1. 推进时间
2. 遍历 agent
3. 判断是否需要走 Claude cognition
4. 产出动作意图
5. 校验动作
6. 应用动作
7. 写 event
8. 顺便更新 relationship
9. 顺便生成 memory

其中 cognition 相关步骤必须先经过：

1. 读取 agent.yml
2. 组装 prompt.md
3. 按能力开关决定是否加载 MCP、skills、subagents
4. 再进入 planner / reactor / reflector

每天结束时：

1. 生成 reflection
2. 生成次日粗粒度计划

## 11. API 范围

MVP 只要求以下接口：

- `POST /runs`
- `POST /runs/{id}/start`
- `POST /runs/{id}/pause`
- `POST /runs/{id}/resume`
- `POST /runs/{id}/director/events`
- `GET /runs/{id}`
- `GET /runs/{id}/timeline`
- `GET /runs/{id}/agents/{agent_id}`

## 12. 前端范围

MVP 前端只做 3 个页面：

- run 概览页
- timeline 页
- agent 详情页

第一版不做：

- 复杂关系图
- replay 动画
- 复杂地图可视化

## 13. 成功标准

MVP 成功的标准是：

- 能稳定跑
- 能暂停恢复
- 能看到事件流
- 能查看 agent 的行为解释线索
- 能注入一个事件并看到系统响应

## 14. 结论

这个 MVP 不是完整的社会模拟平台，而是一个最小可运行的“AI 小镇导演实验系统”。

如果第一版能把以下几点做稳，就算成功：

- 小规模持续运行
- 事件结构化记录
- 记忆和关系的基础闭环
- Claude cognition 的受控调用
- 导演层基本控制

在智能体架构上，MVP 明确采用类似 `IssueLab` 的思路：

- agent 配置资产化
- runtime 与人格配置分离
- Claude Agent SDK 作为执行层
- 能力开关显式配置
