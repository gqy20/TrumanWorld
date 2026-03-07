# TrumanWorld 文档中心

> 导航所有项目文档

---

## 📖 文档分类

### 产品文档

| 文档 | 说明 | 适合角色 |
|------|------|----------|
| [PRD.md](PRD.md) | MVP 产品需求定义 | PM/产品负责人 |
| [BUILD_VS_BUY.md](BUILD_VS_BUY.md) | 复用/自研决策分析 | 技术负责人 |

### 技术文档

| 文档 | 说明 | 适合角色 |
|------|------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 技术架构与模块设计 | 开发者 |
| [ESTIMATE.md](ESTIMATE.md) | 代码量与工期估算 | 开发者/PM |
| [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md) | 开发任务拆解 | 开发者 |

### 开发指南

| 文档 | 说明 | 适合角色 |
|------|------|----------|
| [DEVELOPMENT.md](DEVELOPMENT.md) | 环境搭建与调试 | 新加入开发者 |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | 贡献规范与流程 | 贡献者 |
| [CLAUDE.md](../CLAUDE.md) | Claude Code 配置 | 使用 Claude Code 的开发者 |

### 版本记录

| 文档 | 说明 |
|------|------|
| [CHANGELOG.md](../CHANGELOG.md) | 版本变更历史 |

---

## 🗺️ 快速导航

### 我想了解产品

1. 先看 [PRD.md](PRD.md) 了解 MVP 目标
2. 再看 [ARCHITECTURE.md](ARCHITECTURE.md) 了解技术方案

### 我想参与开发

1. 先看 [DEVELOPMENT.md](DEVELOPMENT.md) 搭建环境
2. 再看 [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md) 了解任务
3. 参考 [CONTRIBUTING.md](../CONTRIBUTING.md) 提交代码

### 我想做技术决策

1. 先看 [BUILD_VS_BUY.md](BUILD_VS_BUY.md) 了解复用策略
2. 参考 [ESTIMATE.md](ESTIMATE.md) 评估工作量

---

## 📌 核心概念

### 什么是 Truman World？

一个 AI 社会模拟系统，创建 10-20 个拥有独立人格的 AI agent，让它们在小镇中生活、社交、成长。

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
| **Agent** | AI 居民，拥有人格、职业、记忆 |
| **Run** | 一次仿真运行 |
| **Tick** | 仿真时间单位 |
| **Director** | 导演层，控制仿真和注入事件 |
| **Timeline** | 事件时间线 |

---

## 🔗 相关链接

- [GitHub 仓库](https://github.com/gqy20/TrumanWorld)
- [README](../README.md)
