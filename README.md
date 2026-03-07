# AI Truman World

> **观察 AI 社会的诞生与演化**

一个可持续运行、可观察、可回放的 AI 社会模拟系统。创建 10-20 个拥有独立人格的 AI agent，让它们在小镇中生活、社交、成长，记录每一段关系的变化与每一个故事的诞生。

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python)
![Node.js](https://img.shields.io/badge/Node.js-20+-green?logo=node.js)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-MVP-orange)

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🧠 **独立人格** | 每个 agent 拥有独特的人格特质、职业和日常习惯 |
| 🔄 **持续演化** | 关系网络随时间自然发展，记忆持续积累 |
| 👁️ **全景观测** | 导演控制台实时查看任意 agent 的状态与记忆 |
| 🎬 **事件注入** | 随时介入世界，创造故事转折 |
| 📜 **可追溯** | 完整事件时间线，支持行为回溯与分析 |

---

## 🎯 你能做什么

- **创建 AI 居民**：通过配置文件定义 agent 的人格、职业和行为模式
- **观察社会演化**：看 agent 们如何建立关系、形成群体、产生冲突与合作
- **导演故事**：注入突发事件（如"咖啡馆举办派对"），观察群体反应
- **分析行为**：追溯任意 agent 的决策链，理解"为什么 TA 会这样做"

---

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/gqy20/TrumanWorld.git
cd truman-world

# 2. 配置环境
cp .env.example .env
# 编辑 .env 添加你的 Anthropic API Key

# 3. 一键启动
make dev
```

启动后访问：
- **导演控制台**: http://127.0.0.1:3000
- **API**: http://127.0.0.1:8000/api

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────┐
│              导演控制台 (Next.js)                    │
│          run 控制 · timeline · agent 详情             │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│              API 层 (FastAPI)                        │
│     run 生命周期 · 事件注入 · 状态查询                │
└─────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   Sim 仿真层   │ │  Agent 认知层  │ │  Store 存储层  │
│ tick · world  │ │ planner ·     │ │ PostgreSQL   │
│ action · rules│ │ reactor ·     │ │ pgvector     │
│               │ │ reflector     │ │ Redis        │
└───────────────┘ └───────────────┘ └───────────────┘
```

---

## 📚 文档导航

### 入门

| 文档 | 说明 |
|------|------|
| [开发指南](docs/DEVELOPMENT.md) | 环境搭建、调试技巧、测试运行 |
| [贡献指南](CONTRIBUTING.md) | 代码规范、PR 流程、提交规范 |
| [CLAUDE.md](CLAUDE.md) | Claude Code 开发助手配置 |

### 产品与技术

| 文档 | 说明 |
|------|------|
| [产品需求](docs/PRD.md) | MVP 功能定义与设计目标 |
| [架构设计](docs/ARCHITECTURE.md) | 技术架构与模块说明 |
| [任务拆解](docs/TASK_BREAKDOWN.md) | 开发任务分解与优先级 |
| [Build vs Buy](docs/BUILD_VS_BUY.md) | 复用/自研决策分析 |
| [代码估算](docs/ESTIMATE.md) | 代码量与工期预估 |

### 其他

| 文档 | 说明 |
|------|------|
| [文档中心](docs/INDEX.md) | 文档分类导航 |
| [变更日志](CHANGELOG.md) | 版本历史 |

---

## 🔧 技术栈

- **后端**: Python 3.12+ · FastAPI · SQLAlchemy
- **前端**: Next.js 15 · TypeScript · Tailwind CSS
- **AI**: Claude Agent SDK
- **存储**: PostgreSQL + pgvector · Redis

---

## 📦 Agent 配置示例

在 `agents/alice/agent.yml` 中定义一个 agent：

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
```

然后在 `prompt.md` 中定义她的角色和行为规范。

---

## 🗺️ 开发路线图

### 已完成
- [x] MVP 产品与架构设计
- [x] 核心数据模型与迁移
- [x] Agent 注册表与运行时
- [x] 仿真服务与导演控制台
- [x] Run 生命周期管理

### 进行中
- [ ] 记忆系统与关系演化
- [ ] Timeline 实时刷新
- [ ] Claude Provider 完整集成

### 规划中
- [ ] 100+ agent 扩展测试
- [ ] 关系图谱可视化
- [ ] Replay 回放系统

---

## 🤝 参与贡献

详见 [贡献指南](CONTRIBUTING.md)。

---

## 📄 License

MIT License

---

<p align="center">
  <em>在 Truman World 里，每个 AI 都是自己故事的主角</em>
</p>
