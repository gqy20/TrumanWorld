# TrumanWorld 文档中心

> 导航所有项目文档

---

## 📖 文档分类

### 当前实现

| 文档 | 说明 | 适合角色 |
|------|------|----------|
| [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md) | 当前代码实现与模块边界 | 开发者/技术负责人 |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 环境搭建与调试 | 新加入开发者 |
| [SCENARIOS.md](SCENARIOS.md) | Scenario 设计与支持情况 | 开发者 |

### MVP 历史文档

| 文档 | 说明 | 适合角色 |
|------|------|----------|
| [PRD.md](PRD.md) | MVP 产品需求定义 | PM/产品负责人 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | v0.1 MVP 架构设计稿 | 开发者 |
| [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md) | MVP 开发任务拆解 | 开发者 |
| [ESTIMATE.md](ESTIMATE.md) | MVP 代码量与工期估算 | 开发者/PM |
| [BUILD_VS_BUY.md](BUILD_VS_BUY.md) | 复用/自研决策分析 | 技术负责人 |

### 开发指南

| 文档 | 说明 | 适合角色 |
|------|------|----------|
| [RUN_QUALITY.md](RUN_QUALITY.md) | Truman world 运行质量评估 | 开发者/导演 |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | 贡献规范与流程 | 贡献者 |
| [CLAUDE.md](../CLAUDE.md) | Claude Code 配置 | 使用 Claude Code 的开发者 |

### 版本记录

| 文档 | 说明 |
|------|------|
| [CHANGELOG.md](../CHANGELOG.md) | 版本变更历史 |

---

## 🗺️ 快速导航

### 我想了解产品

1. 先看 [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md) 了解当前实现
2. 再看 [PRD.md](PRD.md) 了解最初的 MVP 目标

### 我想参与开发

1. 先看 [DEVELOPMENT.md](DEVELOPMENT.md) 搭建环境
2. 再看 [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md) 了解当前模块边界
3. 参考 [CONTRIBUTING.md](../CONTRIBUTING.md) 提交代码

### 我想做技术决策

1. 先看 [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md) 了解当前系统边界
2. 再看 [BUILD_VS_BUY.md](BUILD_VS_BUY.md) 了解复用策略
3. 参考 [ARCHITECTURE.md](ARCHITECTURE.md) 与 [ESTIMATE.md](ESTIMATE.md) 作为 MVP 历史基线

---

## 📌 核心概念

### 什么是 Truman World？

你就是楚门世界的导演。

一个 AI 社会模拟系统。在这个小镇里，AI 居民们自然地生活、工作、社交。
其中有一个"主角"(Truman)，他不知道自己是 AI —— 他有自己的生活、困惑、情感、成长。
其他居民与他共享这个世界，自然地互动。

你的任务：观察、记录、创造条件——让 Truman 能真实地生活。

### 核心架构

```
导演控制台 (Next.js)
       │
       ▼
  API 层 (FastAPI)
       │
   ┌───┼───┐
   ▼   ▼   ▼
 Sim  Agent Store
```

### 关键术语

| 术语 | 说明 |
|------|------|
| **Truman** | 主角 AI，不知道自己是 AI，拥有真实的生活体验 |
| **Cast** | 演员 AI，与 Truman 共享世界的真实主体 |
| **Director** | 导演（你），观察、记录、创造条件 |
| **Run** | 一次仿真运行 |
| **Tick** | 仿真时间单位 |
| **Timeline** | 事件时间线 |
| **怀疑度** | Truman 对世界异常的感知程度 |
| **连续性风险** | 世界出现漏洞的可能性 |

### 灵感来源

- [Generative Agents](https://github.com/joonspk-research/generative_agents) — 斯坦福大学开创性研究
- [IssueLab](https://github.com/gqy20/IssueLab) — 作者的另一项目

---

## 🔗 相关链接

- [GitHub 仓库](https://github.com/gqy20/TrumanWorld)
- [README](../README.md)
