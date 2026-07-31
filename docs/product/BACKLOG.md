# Backlog

> 快速记录功能需求和待办事项，重要项目请同步创建 GitHub Issue

- 类型： `product`
- 版本： `v0.1.0`
- 最后更新： `2026-07-31`

## In Progress

<!-- 当前正在处理 -->

- [x] **Voxel 2.5D Phase 1：Plot / Parcel System**
  - [x] 抽离 `VoxelPlot`、plot layout、入口和 agent anchors
  - [x] 默认 narrative / campus 场景布局无重叠测试
  - [x] renderer 使用 plot 输出，保持地点和角色点击链路
- [x] **可靠性收口**
  - [x] 修复 pulse 首次轮询、时间线筛选分页和迟到响应覆盖
  - [x] 修复 run 删除时治理/经济数据清理
  - [x] 增加数据库 readiness，生产环境强制写操作密码
  - [x] 修复 Docker、hooks、CI 和 Railway 配置漂移

## Todo (P1)

<!-- 高优先级 -->

- [ ] **P1: 结构化心智模型尚未正式落地**
  - [ ] **P1: `mental_state` 尚未进入 Agent 主上下文** - 当前只有 `mood`、`emotional_valence`、`governance_attention_score` 等零散信号，还没有统一的 `mental_state`
  - [ ] **P1: 情感层未结构化** - 尚无 `EmotionalState`、dominant emotion、自然衰减和事件驱动更新
  - [ ] **P2: 需求层未实现** - 尚无 `NeedState`、需求衰减与行为优先级映射
  - [ ] **P3: 认知层未实现** - 尚无 `CognitionState`、议题态度和信息暴露更新

- [ ] **P1: 记忆系统仍需继续收敛**
  - [x] **importance 基础计算已落地** - 事件 importance、主观 importance、`memory_category` 与基础 consolidation 已有实现
  - [ ] **P2: 记忆过期机制仍偏弱** - 当前主要依赖 category/consolidation，没有真正的 TTL、遗忘或强衰减清理
  - [ ] **P2: 语义记忆缺失** - 目前以 episodic / daily plan / daily reflection 为主，没有独立 `semantic` memory
  - [ ] **P2: 记忆膨胀** - 对话与例行行为长期运行后仍可能累积大量 memory
  - [ ] **P2: 检索与排序仍可继续优化** - 现在已可按 importance 排序，但缺更强的检索策略和压缩策略
  - [ ] **P3: 每日反思内容重复** - 反思内容仍有模板化和主题重复的问题

- [ ] **P1: 导演注入分层模型未正式定型**
  - [x] **P1: Layer 2 上下文注入层已是当前主链路** - 广播、活动、关闭地点、停电等导演事件已可进入 agent 侧上下文和世界效果
  - [ ] **P1: Layer 1 强制世界层仍未正式展开** - 更强的地点依赖、设施约束与世界事实修改仍需进入仿真规则
  - [ ] **P1: 当前阶段暂停扩展强制世界规则** - 在没有更完整地点运营/设施依赖模型前，先不要把“咖啡厅必须有电才能营业”这类硬规则做深
  - [ ] **P1: 手动导演测试优先覆盖上下文注入链路** - 先验证 Truman/cast 在收到停电、广播、关闭地点等上下文后的行为变化
  - [ ] **P2: 后续再恢复世界规则层设计** - 当手动注入验证充分后，再补地点可用性、动作拒绝、设施依赖等真实仿真规则

- [ ] **P1: 前端导演控制台尚未完整接入后端治理/经济能力**
  - [ ] **P1: director cases / restrictions 缺少稳定运营视图**
  - [ ] **P2: agent economic summary 尚未进入 agent 详情页**
  - [ ] **P2: 治理与经济反馈缺少统一前端信息架构**
