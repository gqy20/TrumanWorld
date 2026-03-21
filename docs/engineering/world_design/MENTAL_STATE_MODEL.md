# Mental State Model

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 目标

为 Agent 增加结构化的心理状态，支撑更类人的行为决策。

当前 Agent 的决策主要由以下因素驱动：

- 制度规则（rules / policies）
- 关系状态（relationship）
- 记忆（memory）
- 治理关注度（governance_attention_score）

这些是**外部输入**。但人的行为还受**内部心理状态**驱动——同样的外部条件，不同的心理状态会导致不同的行为选择。

一句话：

**心智状态是 Agent 的内部驱动力，与外部制度共同决定行为选择。**

## 2. 为什么需要这一层

### 2.1 当前决策的局限

当前 Agent 的行为选择主要依赖：

- Planner：早晨生成日计划（基于记忆和世界状态）
- Reactor：遇到事件时的反应（基于当前情境）
- Reflector：晚间反思（基于全天事件）

但这些决策**没有结构化的内部状态**作为输入。Planner/Reactor 看到的只是事件列表，不感知 Agent 的"心情"或"需求紧迫度"。

### 2.2 引入心智状态的价值

| 价值 | 说明 |
|-----|------|
| **行为一致性** | 相同事件在不同情绪下产生不同反应 |
| **需求驱动** | 饥饿的人优先觅食，而非社交 |
| **长期演化** | 心智状态随经验缓慢变化，形成独特的个体轨迹 |
| **可解释性** | 行为背后有心理动机的解释 |
| **类人感** | 与真实人类决策更接近 |

### 2.3 与 AgentSociety 的差距

AgentSociety 明确实现了三层心智模型：

- **情感 (Emotions)**：对事件的即时情绪反应
- **需求 (Needs)**：马斯洛需求层次的动态追踪
- **认知 (Cognition)**：对社会议题的态度和信念

当前 TrumanWorld 尚未实现这三层。

## 3. 三层心智结构

### 3.1 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    Mental State三层结构                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    情感层 (Emotions)                    │   │
│  │   即时情绪反应，受事件触发，快速变化                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    需求层 (Needs)                      │   │
│  │   马斯洛需求层次，满足度动态变化，较慢变化                │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    认知层 (Cognition)                  │   │
│  │   社会态度、信念、价值观，长期稳定但可缓慢演化             │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    人格层 (Personality)                │   │
│  │   静态人格特质，影响心智响应模式（已有）                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 情感层 (EmotionalState)

#### 3.2.1 数据结构

```python
class EmotionalState:
    # 维度模型
    valence: float        # [-1, 1] 效价：正面 vs 负面
    arousal: float       # [0, 1] 唤醒度：平静 vs 激活
    dominance: float     # [0, 1] 主控感：被支配 vs 主控

    # 基础情绪（Russell 环形模型）
    joy: float           # 快乐
    sadness: float       # 悲伤
    anger: float        # 愤怒
    fear: float         # 恐惧
    surprise: float     # 惊讶
    disgust: float      # 厌恶

    # 复合情绪
    anxiety: float      # 焦虑（fear + uncertainty）
    excitement: float   # 兴奋（joy + high_arousal）
    contentment: float  # 满足（joy + low_arousal）
    frustration: float  # 挫败（anger + helplessness）

    def get_dominant_emotion(self) -> str:
        """返回当前最强的情绪"""
        ...

    def decay(self, dt: float) -> None:
        """情绪随时间自然衰减"""
        ...
```

#### 3.2.2 情感更新规则

| 触发条件 | 情感变化 |
|---------|---------|
| 社交成功 | joy ↑, anxiety ↓ |
| 社交被拒 | sadness ↑, frustration ↑ |
| 被警告/拦截 | fear ↑, anxiety ↑ |
| 帮助他人 | joy ↑, contentment ↑ |
| 遇到危险 | fear ↑, anger ↑（如果愤怒主导） |
| 经历熟悉 Routine | contentment ↑（小幅） |

#### 3.2.3 情感对行为的影响

| 情感状态 | 行为倾向 |
|---------|---------|
| 高 joy | 更愿意社交、尝试新事物 |
| 高 sadness | 回避社交、偏好独处 |
| 高 anger | 激进行为增加、风险偏好上升 |
| 高 fear | 回避风险、寻求安全 |
| 高 anxiety | 犹豫增加、决策变慢 |

### 3.3 需求层 (NeedState)

#### 3.3.1 数据结构

```python
class NeedState:
    """马斯洛需求层次（简化版）"""

    # 底层需求（高优先级）
    physiological: float    # [0, 1] 生理需求（饥饿、口渴、健康）
    safety: float        # [0, 1] 安全需求（稳定、免受威胁）

    # 中层需求
    belonging: float       # [0, 1] 社交需求（友谊、亲密）
    esteem: float         # [0, 1] 尊重需求（成就、尊重）

    # 高层需求（低优先级）
    self_actualization: float  # [0, 1] 自我实现（创造力、意义）

    def get_dominant_need(self) -> str:
        """返回当前最迫切的需求名称"""
        ...

    def get_satisfaction_level(self, need: str) -> float:
        """返回某需求的满足程度"""
        ...

    def update_from_event(self, event: Event) -> None:
        """根据事件更新需求满足度"""
        ...
```

#### 3.3.2 需求与行为的映射

| 需求状态 | 驱动的行为 |
|---------|-----------|
| physiological ↓ | 寻找食物/餐厅、回家 |
| safety ↓ | 回避危险区域、寻求安全地点 |
| belonging ↓ | 主动找人聊天、参与社交 |
| esteem ↓ | 寻求表现机会、追求成就 |
| self_actualization ↓ | 探索新活动、创造性表达 |

#### 3.3.3 需求更新规则

| 事件 | 需求变化 |
|-----|---------|
| 吃饭/休息 | physiological ↑ |
| 睡眠恢复 | physiological ↑, safety ↑ |
| 社交成功 | belonging ↑ |
| 被尊重/赞扬 | esteem ↑ |
| 工作成就 | esteem ↑ |
| 创造性活动 | self_actualization ↑ |
| 长时间无社交 | belonging ↓ |
| 遭遇危险/冲突 | safety ↓, esteem ↓ |

### 3.4 认知层 (CognitionState)

#### 3.4.1 数据结构

```python
class CognitionState:
    """认知状态：信念、态度、价值观"""

    # 社会议题态度
    # 值域 [0, 1]，0.5 表示中立
    # < 0.5 偏向负面，> 0.5 偏向正面
    attitudes: dict[str, float]  # {
    #     "gun_control": 0.3,    # 反对枪支管控
    #     "ubi": 0.7,            # 支持UBI
    # }

    # 对特定群体的态度（偏见/刻板印象）
    # 值域 [-1, 1]，负数表示负面态度
    group_attitudes: dict[str, float]  # {
    #     "neighbors": 0.2,
    #     "authority": -0.3,
    # }

    # 对政府的信任度
    # 值域 [0, 1]
    government_trust: float

    # 信息茧房暴露度
    # 值域 [0, 1]，越高表示越只接触同质信息
    echo_chamber_exposure: float

    # 开放性（对新信息的接受度）
    # 值域 [0, 1]
    openness_to_new_ideas: float

    def update_attitude(self, topic: str, exposure: float, perspective: float) -> None:
        """更新议题态度

        Args:
            topic: 议题名称
            exposure: 信息暴露度 [0, 1]
            perspective: 信息立场 [0, 1]，0.5=中立，<0.5=负面，>0.5=正面
        """
        ...

    def calculate_persuasion(self, message_stance: float) -> float:
        """计算态度被说服的程度"""
        ...
```

#### 3.4.2 认知对行为的影响

| 认知状态 | 行为倾向 |
|---------|---------|
| 高 government_trust | 更服从规则、对政策响应更积极 |
| 低 openness_to_new_ideas | 更坚持己见、不易被说服 |
| 高 echo_chamber_exposure | 观点更极化、社交更同质 |
| 负面 group_attitude | 对特定群体更冷漠或敌意 |

#### 3.4.3 认知更新规则

| 触发条件 | 认知变化 |
|---------|---------|
| 接触异质观点 | openness_to_new_ideas ↑, echo_chamber_exposure ↓ |
| 持续接触同质观点 | echo_chamber_exposure ↑ |
| 政策有效体验 | government_trust ↑ |
| 政策负面体验 | government_trust ↓ |
| 成功说服他人 | esteem ↑（间接） |
| 被他人说服 | openness_to_new_ideas ↑（间接） |

## 4. 与现有组件的关系

### 4.1 在 Agent Context 中的位置

```
Agent Context
├── world_rules_summary     (已有)
├── relationships           (已有)
├── memories               (已有)
├── governance_attention   (已有)
│
├── [新增] mental_state    (新增)
│   ├── emotions           (情感)
│   ├── needs             (需求)
│   └── cognition         (认知)
```

### 4.2 心智状态如何影响决策

```
外部输入（事件）
       │
       ▼
┌──────────────────────────────────────────┐
│           心智状态更新                      │
│  events → emotional_update()             │
│         → need_update()                   │
│         → cognition_update()              │
└──────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│           行为决策输入                      │
│  need = needs.get_dominant()             │
│  emotion = emotions.get_dominant()       │
│  attitude = cognition.get(topic)          │
│                                          │
│  context_builder.inject_mental_state(...)  │
└──────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│           Planner / Reactor / Reflector   │
│  (考虑心智状态后生成行为意图)               │
└──────────────────────────────────────────┘
```

### 4.3 与其他层的交互

| 组件 | 关系 |
|-----|------|
| **Relationship** | 心智状态影响关系演化；关系状态影响心智（如被拒绝 → sadness） |
| **Memory** | 情绪影响记忆编码权重（负面事件记得更牢）；记忆影响认知更新 |
| **World Rules** | 认知状态影响对规则的态度（高 trust → 更遵守） |
| **Governance** | 高 anxiety/fear 时对治理干预更敏感 |
| **Agent Visible Summary** | 可暴露部分心智状态（如"你现在很焦虑"） |

## 5. 数据持久化

### 5.1 存储位置

心智状态存储在 `Agent.status` 中：

```python
# Agent.status 结构扩展
{
    # 现有字段
    "governance_attention_score": 0.3,
    "alert_metric": 0.5,
    "world_role": "subject",

    # 新增心智字段
    "mental_state": {
        "emotions": {
            "valence": 0.6,
            "arousal": 0.4,
            "joy": 0.7,
            "sadness": 0.1,
            "anger": 0.0,
            "fear": 0.2,
        },
        "needs": {
            "physiological": 0.8,    # 有点饿
            "safety": 0.9,
            "belonging": 0.4,       # 有点孤独
            "esteem": 0.6,
            "self_actualization": 0.3,
        },
        "cognition": {
            "attitudes": {
                "gun_control": 0.5,
                "ubi": 0.6,
            },
            "group_attitudes": {},
            "government_trust": 0.7,
            "echo_chamber_exposure": 0.3,
            "openness_to_new_ideas": 0.5,
        }
    }
}
```

### 5.2 持久化策略

- 心智状态在每个 tick 结束时更新
- 全部持久化太昂贵，采用**增量更新**
- 关键状态变化（如 dominant_need 切换）触发持久化

## 6. Agent Visible Summary 的扩展

新增心智相关的摘要字段：

```yaml
world_rules_summary:
  available_actions: []
  blocked_constraints: []
  current_risks: []
  policy_notices: []
  recent_rule_feedback: []

  # 新增
  mental_state_summary:
    current_mood: "有点焦虑"           # 派生自 emotions
    dominant_need: "社交需求"          # 来自 needs.get_dominant()
    recent_emotion_change: "被拒绝后感到难过"  # 来自最近情感变化
```

## 7. 第一阶段实施范围

### 7.1 推荐优先实现

| 优先级 | 内容 | 理由 |
|-------|------|------|
| **P1** | 情感层基础版 | 影响最直接，实现最简单 |
| **P1** | 需求层基础版 | 马斯洛结构清晰，与行为映射明确 |
| **P2** | 认知层基础版 | 需要定义议题集合，较复杂 |

### 7.2 第一阶段简化假设

- **情感**：简化为 valence + arousal + 3-4 种基础情绪
- **需求**：简化为 5 维马斯洛，每 tick 自然衰减最低需求
- **认知**：先不做，留给后续阶段

### 7.3 实施阶段

```
Phase 1.1: 情感层（1-2周）
├── 定义 EmotionalState 类
├── 事件 → 情感 更新规则
├── 情感 → 行为倾向 影响（prompt 中注入）
└── 与 World Rules Summary 集成

Phase 1.2: 需求层（2周）
├── 定义 NeedState 类
├── Tick 自然衰减机制
├── 需求满足度更新规则
└── 需求 → 行为优先级 影响

Phase 2: 认知层（2-3周，可选）
├── 定义 CognitionState 类
├── 社会议题态度建模
├── 信息接触 → 认知更新
└── 认知 → 规则态度 影响
```

## 8. 当前不建议做的内容

- 复杂的多因子情感计算模型
- 全面的认知图谱建模
- 完整的人格 × 心智交互模型
- 群体心智（集体情绪、群体极化）

先把单 Agent 心智状态落地，再考虑群体层面。

## 9. 与 IMPLEMENTATION_ROADMAP 的衔接

建议在 `IMPLEMENTATION_ROADMAP.md` 中新增：

```markdown
### 阶段 6：心智模型层

状态：`待启动`

目标：

- 为 Agent 增加结构化的心理状态
- 支撑更类人的行为决策
- 为认知模拟实验提供基础

当前建议实施范围：

- 情感层（基础版）
- 需求层（基础版）
- 与 Agent Visible Summary 的集成

当前明确不做：

- 完整认知层
- 复杂情感计算模型
- 群体心智建模
```

## 10. 默认结论

- 心智模型是 Agent Context 层的扩展
- 三层结构：情感 → 需求 → 认知
- 第一阶段只做情感和需求层，认知层留后续
- 心智状态存储在 Agent.status 中
- 与 Relationship、Memory、World Rules 形成交互网络
- 不做群体心智，先做单 Agent
