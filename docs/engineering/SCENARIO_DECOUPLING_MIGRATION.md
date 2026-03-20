# Scenario Decoupling Migration

## 背景

本轮迁移的目标不是“给 TrumanWorld 换一层皮”，而是把运行时、API、存储、提示词中的 Truman 专有语义清理到只剩场景内容本身。

当前代码已经切换到 scenario-neutral 命名。运行时和对外契约不再要求调用方理解 `truman_*`、`target_cast_*`、`trigger_suspicion_score` 这类历史字段。

## 当前结论

- 运行时代码已经完成主要迁移
- API / OpenAPI 已移除旧字段兼容别名
- 持久化模型已切换到通用字段名
- Director 提示词与上下文已改为 subject / agent 语义
- 历史 Truman 命名仅保留在 Alembic 迁移历史和“确保旧字段不存在”的测试中

这意味着：项目现在已经可以基于 `md` / `yml` 场景内容继续扩展，而不再被 Truman 专有字段结构强耦合。

## Canonical Names

以下字段名是当前唯一有效的规范名。

### Director Observation

- `subject_alert_tracking_enabled`
- `subject_agent_id`
- `subject_alert_score`
- `suspicion_level`
- `continuity_risk`
- `focus_agent_ids`
- `notes`

### Director Memory

- `target_agent_ids`
- `target_agent_names`
- `trigger_subject_alert_score`

### Runtime Context

- `world.subject_alert_score`

### Director / Planner Domain

- `subject_agent_id`
- `subject_alert_score`
- `target_agent_ids`
- `target_agent_names`

## Removed Legacy Fields

以下字段已从活动代码路径和对外响应中删除：

- `truman_agent_id`
- `truman_suspicion_score`
- `target_cast_ids`
- `target_cast_names`
- `trigger_suspicion_score`

这些名字不应再被前端、脚本、测试夹具或新场景配置继续使用。

## Breaking Change Note

这轮迁移已经不是“仅弃用”，而是明确的 breaking change。

受影响方包括：

- 直接消费运行时 API 的前端
- 依赖 OpenAPI 生成类型的客户端
- 自定义脚本或数据导入工具
- 读取 director memory 落库字段的离线分析代码

如果外部消费者仍使用旧字段名，需要一并迁移到本文件列出的 canonical names。

## 场景构建含义

当前场景层已经具备以下前提：

- 运行时加载的是场景 bundle，而不是硬编码的 Truman world 路径语义
- Director 配置和 prompt 可以继续保留“某个具体场景的世界观内容”
- 但这些内容不再要求底层接口暴露 Truman 专属字段

因此，“基于 `md` / `yml` 构建场景”现在在技术上已可成立，剩余问题主要是场景资产本身的组织质量，而不是核心代码层的耦合。

## 当前已支持的场景语义

`scenario.yml` 现在除了场景标识外，还可以承载场景语义与能力开关。

当前已接入运行时主链路的字段包括：

- `adapter`
- `semantics.subject_role`
- `semantics.support_roles`
- `semantics.alert_metric`
- `capabilities.director`
- `capabilities.subject_alert_tracking`
- `capabilities.scene_guidance`

其中：

- `adapter` 决定复用哪个 Python scenario adapter
- `subject_role` 决定 observer / state updater / runtime context 中的主体角色
- `support_roles` 决定 director planner / manual planner / director backend / fallback heuristics 中的支援角色
- `alert_metric` 决定主体告警值读取与写入的状态字段
- `subject_alert_tracking` 决定是否启用主体告警跟踪链路；关闭后 state updater / runtime context / observer / alert-driven strategies 都会跳过这类信号

这意味着：

- 新场景不再必须使用 `truman` / `cast` / `suspicion_score`
- 只要复用现有 adapter，就可以通过 `scenario.yml` 派生不同角色语义的场景 bundle
- 主体告警值不再是平台默认世界机制，而是场景可选能力

## 当前已支持的 initial.yml 兼容输入

`initial.yml` 目前已经支持两类写法并行存在：

旧写法：

```yaml
initial_location: home
initial_goal: work
status:
  energy: 0.8
  suspicion_score: 0.2
plan:
  morning: work
  daytime: work
  evening: rest
```

新写法：

```yaml
spawn:
  location: workplace
  goal: greet
status:
  energy: 0.8
  suspicion_score: 0.2
plan:
  default: patrol
```

当前行为是：

- `spawn.location` 优先于 `initial_location`
- `spawn.goal` 优先于 `initial_goal`
- `status.<alert_metric>` 优先作为主体告警输入
- `status.alert_score` 次之
- `status.suspicion_score` 仍是兼容输入字段
- seed 会根据 `scenario.yml` 的 `semantics.alert_metric` 把最终值写入对应状态字段

因此，场景作者已经可以在不改公共 schema 的前提下：

- 使用更通用的 `spawn` 结构描述初始位置与目标
- 使用 `alert_metric` 将主体初始告警值映射到 `anomaly_score` 等新字段

## 当前仍未完全泛化的部分

以下部分仍然保留历史 Truman 语义或命名，需要后续继续收口：

- `TrumanWorldScenario` / `TrumanWorldSeedBuilder` 等类名
- `current_suspicion_score` 兼容字段仍然保留在 role context 中
- `initial.status.suspicion_score` 作为输入字段名仍未改成完全中性名字
- `plan.morning/daytime/evening` 仍然是默认保留计划字段

这些问题当前主要影响命名一致性和 DSL 完整度，不再构成场景主流程的结构性耦合。

## 仍然保留旧名的地方

以下旧名仍可能在仓库中被搜索到，但它们属于预期保留：

- Alembic migration history
- 用于断言旧字段已被删除的测试
- 早期设计文档中的历史示例

其中前两类不应删除：

- Alembic 需要保留真实历史，保证旧库可升级
- 测试需要继续防止兼容层意外回流

## 后续原则

- 新增场景能力时，禁止再引入 Truman 专属字段名
- 新接口先定义通用 domain vocabulary，再落到具体场景内容
- 场景差异应主要存在于 `md` / `yml` 资产，而不是 API / store / runtime schema
