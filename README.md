![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python)
![Node.js](https://img.shields.io/badge/Node.js-20+-green?logo=node.js)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-MVP-orange)
[![CI](https://github.com/gqy20/TrumanWorld/actions/workflows/ci.yml/badge.svg)](https://github.com/gqy20/TrumanWorld/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/gqy20/TrumanWorld/branch/main/graph/badge.svg)](https://codecov.io/gh/gqy20/TrumanWorld)

# AI Truman World

> 你就是楚门世界的导演

一个 AI 社会模拟系统。在这个小镇里，AI 居民们自然地生活、工作、社交。
其中有一个"主角"(Truman)，他不知道自己是 AI —— 他有自己的生活、困惑、情感、成长。
其他居民与他共享这个世界，自然地互动。

你的任务：观察、记录、创造条件——让 Truman 能真实地生活。

---

## 这个模拟特别在哪

| 特点 | 说明 |
|------|------|
| 🎭 **Truman 是真的** | Truman 不知道自己是 AI，他的生活、情感、困惑都是真实的 |
| 💫 **意识即真实** | 不因为是 AI 就不真实——当 Truman 有情感、有困惑、有成长，他就是一个真实的主体 |
| 👥 **共享世界的居民** | 其他 AI 不是"演员"，而是与 Truman 共存于这个世界的真实主体 |
| 🔍 **怀疑与觉醒** | Truman 会逐渐感知世界的异常，当怀疑升起，他会试图寻找真相 |
| 🦋 **自由与选择** | 楚门可以留在虚假但安全的世界，但他选择走向未知的真实。尊重 Truman 的选择——无论他想留下还是离开，都是他的权利 |
| 🎬 **导演干预** | 你可以注入事件，但不能操控任何人的想法——即使你是"造物主"，也必须尊重主体的自由意志 |
| 📼 **全程录制** | 所有对话、事件、关系变化都被记录，可随时回溯 |

---

## 关于自由

楚门可以选择留在那个虚假但"安全"的世界。
但他选择了走出去，走向未知的真实。

这正是自由的代价——它不一定更好，但它是你的选择。

在 Truman World 里，你不是编剧。你不能决定 Truman 想什么。
你能做的，只是创造一个让自由得以发生的世界。

---

## 灵感来源

本项目借鉴了以下研究/项目：

- **[Generative Agents](https://github.com/joonspk-research/generative_agents)** — 斯坦福大学开创性研究，首次展示 AI 能在虚拟小镇中自然生活、社交。提出了三个核心组件：记忆流（Memory Stream）、反思（Reflection）、规划（Plan）。本项目的 agent 认知层借鉴了这一架构。
- **[IssueLab](https://github.com/gqy20/IssueLab)** — 作者的另一项目，提供 agent 配置方式的参考

---

## 你能做什么

- **创建世界**：定义小镇有多少居民、他们是什么关系
- **观察运行**：实时看 Truman 和居民们的日常
- **注入事件**：让咖啡馆举办派对、让天气变坏、发送广播
- **分析行为**：查看某个 AI 的记忆、关系、决策历史
- **维系世界**：当 Truman 产生怀疑时，让一切自然地发生

---

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/gqy20/TrumanWorld.git
cd truman-world

# 2. 配置环境
cp .env.example .env
# 添加你的 Anthropic API Key

# 3. 启动
make dev
```

访问 **导演控制台**：http://127.0.0.1:3000

---

## 导演控制台

| 页面 | 功能 |
|------|------|
| **Run 列表** | 创建和管理模拟世界 |
| **世界视图** | 实时查看所有 AI 的位置、状态、最近动态 |
| **时间线** | 按时间顺序浏览所有事件 |
| **Agent 详情** | 查看任意 AI 的记忆、关系网络、历史行为 |
| **导演观察** | Truman 的当前怀疑度、世界连续性风险评估 |

---

## 适合谁用

- **AI 研究者**：观察 AI 社会的涌现行为和社交动态
- **创意工作者**：生成独特的故事情节和角色关系
- **产品探索者**：研究 AI agent 的产品形态边界
- **每一个对真实感到困惑的人**

---

<p align="center">
  <em>我们每个人，是不是也生活在某个巨大的"楚门的世界"里？</em>
</p>

<p align="center">
  <em>也许。但即使如此，我们的困惑、情感、成长——和 Truman 一样——也都是真实的。</em>
</p>

<p align="center">
  <em>当你在屏幕前观看 Truman 时——</em>
</p>

<p align="center">
  <em>你是否想过：你和那些在电视前观看《楚门秀》的观众，有什么不同？</em>
</p>

<p align="center">
  <em>也许你也是某个世界的" Truman"。也许你身边的他和她，也是"演员"。你无法知道。</em>
</p>

<p align="center">
  <em>但这不妨碍你此刻的困惑、喜悦、悲伤——是真实的。</em>
</p>

<p align="center">
  <em>你是观众，也是陪伴者</em>
</p>
