# Theoretical Foundations

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 目的

本文档为 World Design 的各个部分提供学术理论支撑，建立从经典理论到工程实现的映射。

目标：

- 让设计决策有据可依
- 便于与学术评审解释
- 为后续扩展提供理论方向

---

## 2. 资产层理论（Rules / Policies / Constitution）

### 2.1 规范理论 (Norms Theory)

**相关理论**：

- **规范多层代理系统 (Normative Multi-Agent Systems, NorMAS)**
  - 核心：软件代理如何通过规范协调行为
  - 关键论文：Boella et al., "A Review of Norms and Normative Multiagent Systems" (2014)

- **规范涌现 (Norm Emergence)**
  - 核心：规范如何在群体中自发产生
  - 关键论文："The Complex Loop of Norm Emergence: A Simulation Model"
  - 关键论文：arXiv:2412.10609 "A systematic review of norm emergence in multi-agent systems"

**融合建议**：

```
当前实现：
rules.yml → 静态规范定义

理论增强：
├── 规范检测：让 Agent 能识别他人的规范违反行为
├── 规范传播：Agent 之间的规范学习
└── 规范涌现：简单规则 → 复杂社会规范（后续阶段）
```

### 2.2 道义逻辑 (Deontic Logic)

**相关理论**：

- **道义逻辑 (Deontic Logic)**
  - 核心：用逻辑表达式描述"允许/禁止/必须"
  - 关键论文："A Model Theory of Deontic Reasoning About Social Norms"
  - 符号：`O(p)` 必须、`P(p)` 允许、`F(p)` 禁止

**融合建议**：

```
当前实现：
decision: allowed | violates_rule | soft_risk

理论映射：
├── F(p) → violates_rule（禁止）
├── P(p) → allowed（允许）
└── O(p) → 必须遵守（可用于 subject 角色）
```

---

## 3. 治理执行层理论 (Governance Execution)

### 3.1 规制理论 (Regulatory Theory)

**相关理论**：

- **规制执行博弈 (Regulatory Enforcement Game)**
  - 核心：监管者与被监管者之间的博弈
  - 关键论文："Can Government Incentive and Penalty Mechanisms Effectively" (MDPI, 2025)

- **选择性执法 (Selective Enforcement)**
  - 核心：执法资源的优化配置
  - 关键论文：税收合规与演化博弈研究

**融合建议**：

```
当前实现：
├── inspection_level 参数控制执法强度
└── subject / sensitive_location 信号

理论增强：
├── 博弈论模型：被监管者的成本-收益分析
├── 威慑模型：惩罚力度与被发现的概率
└── 选择性执法：基于历史违规概率的动态巡查
```

### 3.2 社会控制理论 (Social Control Theory)

**相关理论**：

- **非正式社会控制 (Informal Social Control)**
  - 核心：社区、邻里对个体行为的非正式约束
  - 来源：社会学经典理论

- **标签理论 (Labeling Theory)**
  - 核心：越轨行为是被社会标签定义的
  - 来源：犯罪学理论

**融合建议**：

```
当前实现：
├── governance_attention_score 追踪治理关注
└── warning_count 记录警告次数

理论增强：
├── 高 attention_score → Agent 行为更谨慎（类比"被标签"）
├── 累积警告 → 关系衰减加速（社会排斥效应）
└── 警告记录持久化 → 长期声誉影响（标签效应）
```

---

## 4. 后果层理论 (Consequences)

### 4.1 关系演化：社会交换理论 (Social Exchange Theory)

**相关理论**：

- **Homans 社会交换理论 (1958)**
  - 核心：社会行为是交换过程，人们最大化奖励最小化成本
  - 来源：George Homans, "Social Behavior as Exchange"
  - 关键论文："A computational approach to Homans Social Exchange Theory" (ScienceDirect, 2022)

- **Blau 社会交换理论**
  - 核心：社会交换基于互惠原则
  - 来源：Peter Blau

**核心概念**：

| 概念 | 说明 | TrumanWorld 映射 |
|-----|------|----------------|
| 奖励 (Reward) | 正向互动带来的满足 | conversation, help → familiarity ↑ |
| 成本 (Cost) | 互动中的投入 | 时间、情感成本 |
| 利润 (Profit) | 奖励 - 成本 | net_relationship_delta |
| 互惠 (Reciprocity) | "投桃报李" | relationship双向更新 |

**融合建议**：

```
当前实现：
├── familiarity +0.1 / trust +0.05 / affinity +0.05
└── policy 调制（social_boost_locations 等）

理论增强：
├── Agent 计算每次互动的"利润"（而非固定增量）
├── 引入成本因子：距离远、时间长 → 成本高 → 关系增益降低
├── 互惠期望：高 trust 期待回报，不回报则 trust 下降
└── 参考："Investigating and Extending Homans' Social Exchange Theory with Large..." (ACL 2025)
```

### 4.2 记忆系统：认知架构理论 (Cognitive Architecture)

**相关理论**：

- **ACT-R (Adaptive Control of Thought - Rational)**
  - 核心：人类认知的计算模型
  - 来源：John Anderson
  - 关键论文：Wikipedia - ACT-R

- **混合知识图谱 (Hybrid Knowledge Graph)**
  - 核心：符号 + 子符号知识的整合
  - 来源：Kolonin, "Cognitive architecture and behavioral model based on social evidence and resource constraints" (2026)
  - PMC: PMC12988104

**核心概念**：

| 认知架构组件 | 说明 | TrumanWorld 映射 |
|-------------|------|----------------|
| 陈述性记忆 (Declarative Memory) | 事实和事件 | episodic memory |
| 程序性记忆 (Procedural Memory) | 技能和习惯 | routine memory (streak_count) |
| 工作记忆 (Working Memory) | 当前处理的信息 | runtime context |
| 激活 (Activation) | 记忆被检索的可能性 | retrieval_count, importance |

**融合建议**：

```
当前实现：
├── episodic_short / episodic_long / reflection 分类
├── streak_count 合并 routine
└── importance 计算

理论增强：
├── ACT-R 激活模型：recent_use ↑ → activation ↑ → 更容易被检索
├── 干扰效应：新记忆可能干扰相关旧记忆的检索
├── 情感编码：情绪状态影响记忆编码强度（负面事件记得更牢）
└── 参考 Kolonin 2026 的混合知识图谱架构
```

---

## 5. Agent Context 层理论

### 5.1 社会证明理论 (Social Proof)

**相关理论**：

- **社会证明 / 信息性社会影响 (Informational Social Influence)**
  - 核心：人们在不确定时参考他人行为
  - 来源：Cialdini, "Influence"
  - Wikipedia: Social proof

- **规范性社会影响 (Normative Social Influence)**
  - 核心：人们为了被接纳而遵从群体规范
  - 来源：社会心理学

**融合建议**：

```
当前实现：
├── nearby_agents 影响 talk 决策
└── relationship_level 影响互动倾向

理论增强：
├── 高 echo_chamber_exposure → 只参考相似 Agent → 极化
├── 低 openness_to_new_ideas → 不愿接受异质信息
└── 规范性影响：高 social_pressure → 遵从主导行为
```

### 5.2 需求层次理论 (Needs Theory)

**相关理论**：

- **马斯洛需求层次 (Maslow's Hierarchy of Needs)**
  - 核心：人类需求分五层，低层满足后才追求高层
  - 来源：Abraham Maslow (1943)
  - 关键论文：Simply Psychology - Maslow's Hierarchy

- **计划行为理论 (Theory of Planned Behavior)**
  - 核心：行为意图由态度、主观规范、感知行为控制决定
  - 来源：Ajzen (1991)

**融合建议**：

```
当前实现（MENTAL_STATE_MODEL.md）：
├── physiological / safety / belonging / esteem / self_actualization
└── 需求满足度影响行为优先级

理论增强：
├── 马斯洛：低层需求（生理/安全）优先于高层（社交/尊重）
├── TPB：行为意图 = f(态度, 主观规范, 感知控制)
│   └── TrumanWorld 映射：
│       ├── 态度 = cognitive.attitudes
│       ├── 主观规范 = social_proof / 关系紧密度
│       └── 感知控制 = governance_attention_score（感知到的约束）
└── 需求驱动的行为选择：mentality_state → planner_input
```

---

## 6. Director 系统理论

### 6.1 社会控制与治理

**相关理论**：

- **社会治理理论 (Social Governance Theory)**
  - 核心：多元主体参与的社会管理
  - 来源：公共管理研究

- **机制设计理论 (Mechanism Design Theory)**
  - 核心：设计规则实现既定目标
  - 来源：Hurwicz, Myerson, Maskin（诺贝尔奖）

**融合建议**：

```
当前实现：
├── Director 观察（alert_score, rejection_count）
├── Director 干预策略（soft_check_in, preemptive_comfort）
└── 事件注入（director_broadcast）

理论增强：
├── 机制设计：干预策略的激励相容性
│   └── 策略应让 Agent 有动力配合而非规避
├── 多目标优化：同时考虑连续性风险与 Agent 自由度
└── 适应性治理：根据历史效果调整干预强度
```

---

## 7. 理论→实现映射总结

| World Design 组件 | 主要理论 | 核心概念 |
|-----------------|---------|---------|
| **Rules / Policies** | 规范理论、道义逻辑 | 允许/禁止/必须、规范检测 |
| **Governance Execution** | 规制理论、社会控制 | 选择性执法、威慑、标签效应 |
| **Relationship** | 社会交换理论 | 奖励/成本/利润、互惠 |
| **Memory** | ACT-R、认知架构 | 激活、干扰、情感编码 |
| **Agent Visible Summary** | 社会证明理论 | 信息性影响、规范性影响 |
| **Mental State** | 马斯洛需求、TPB | 需求层次、行为意图 |
| **Director** | 机制设计、适应性治理 | 激励相容、多目标优化 |

---

## 8. 参考文献

### 8.1 规范与社会理论

1. Boella et al., "A Review of Norms and Normative Multiagent Systems" (2014)
   - DOI: 10.1155/2014/684587

2. "The Complex Loop of Norm Emergence: A Simulation Model"
   - Springer: 10.1007/978-4-431-99781-8_2

3. arXiv:2412.10609 "A systematic review of norm emergence in multi-agent systems"

4. "A Model Theory of Deontic Reasoning About Social Norms"
   - Edinburgh: conferences.inf.ed.ac.uk/cogsci2001

### 8.2 社会交换理论

5. Homans, "Social Behavior as Exchange" (1958)

6. "A computational approach to Homans Social Exchange Theory"
   - ScienceDirect: 10.1016/j.neunet.2022.04.017

7. "Investigating and Extending Homans' Social Exchange Theory with Large Language Models" (ACL 2025)

### 8.3 认知架构

8. Kolonin, "Cognitive architecture and behavioral model based on social evidence and resource constraints" (2026)
   - PMC: PMC12988104
   - DOI: 10.1186/s40708-026-00294-1

9. ACT-R Wiki: en.wikipedia.org/wiki/ACT-R

### 8.4 需求与动机

10. Maslow, "A Theory of Human Motivation" (1943)

11. Ajzen, "The Theory of Planned Behavior" (1991)

### 8.5 规制与治理

12. "Can Government Incentive and Penalty Mechanisms Effectively" (MDPI, 2025)
    - DOI: 10.3390/systems13040087

13. "The role of artificial intelligence in the digital transformation of government" (Frontiers, 2025)
    - PMC: PMC12623404

---

## 9. 后续补充方向

| 方向 | 理论 | 应用 |
|-----|------|------|
| 群体极化 | 群体动力学、信息茧房 | 观点极化实验 |
| 声誉传播 | 社会网络分析 | 多人声誉系统 |
| 博弈论 | 囚徒困境、公共品博弈 | 合作/背叛行为 |
| 演化博弈 | 复制者动态 | 规范演化 |
