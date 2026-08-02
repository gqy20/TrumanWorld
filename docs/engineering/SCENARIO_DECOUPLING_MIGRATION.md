# Scenario Decoupling Migration

## 背景

本轮迁移的目标不是“给 TrumanWorld 换一层皮”，而是把运行时、API、存储、提示词中的 Truman 专有语义清理到只剩场景内容本身。

当前代码已经切换到 scenario-neutral 命名。运行时和对外契约不再要求调用方理解 `truman_*`、`target_cast_*`、`trigger_suspicion_score` 这类历史字段。

## 当前结论

- 运行时代码已经完成主要迁移
- 默认 scenario adapter 已迁移到 `bundle_world`，默认 bundle id 为 `narrative_world`
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

因此，“基于 `md` / `yml` 构建场景”现在在技术上已可成立，剩余问题主要是场景资产本身的组织质量，以及少量兼容输入字段，而不是核心代码层的耦合。

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

## 当前 initial.yml 输入

`initial.yml` 已统一为通用写法：

```yaml
spawn:
  location: workplace
  goal: greet
status:
  energy: 0.8
  alert_score: 0.2
plan:
  default: patrol
```

当前行为是：

- `spawn.location` 定义初始位置
- `spawn.goal` 定义初始目标
- `status.alert_score` 是通用告警输入名
- seed 会根据 `scenario.yml` 的 `semantics.alert_metric` 把最终值写入对应状态字段

因此，场景作者已经可以在不改公共 schema 的前提下：

- 使用更通用的 `spawn` 结构描述初始位置与目标
- 使用 `alert_metric` 将主体初始告警值映射到 `anomaly_score` 等新字段

## 当前仍未完全泛化的部分

以下部分仍然保留旧 DSL 形态，需要后续继续收口：

- `plan.morning/daytime/evening` 仍然是默认保留计划字段
- 产品品牌文案和历史参考文档仍大量使用 `TrumanWorld`

这些问题当前主要影响命名一致性和 DSL 完整度，不再构成场景主流程的结构性耦合。

## 当前残留的边界

仓库里继续出现 `Truman` / `TrumanWorld` / `suspicion_score` 时，需要先判断它属于哪一层，再决定是否清理。

### 1. 场景内容层

这类残留是当前 `narrative_world` 默认场景本身的世界观内容，不属于平台耦合：

- `scenarios/narrative_world/agents/*/prompt.md`
- `scenarios/narrative_world/agents/truman/initial.yml`
- `scenarios/narrative_world/scenario.yml` 中的 `alert_metric: suspicion_score`

这些内容只有在更换默认场景设定时才应修改，不应因为“去 Truman 化”而机械删除。

### 2. 品牌与产品文案层

这类残留是项目品牌、产品标题或历史定位文案，不属于运行时结构耦合：

- `frontend/app/layout.tsx`
- `frontend/components/app-shell.tsx`
- `frontend/components/world-opening-animation.tsx`
- `frontend/public/logo*.svg`
- `backend/app/main.py`
- `docs/README.md`

这部分是否修改，取决于产品是否决定连品牌名称一起迁移；在此之前不应与运行时重构混在同一个清扫步骤里。

### 3. 历史与兼容层

这类残留属于有意保留的历史记录或兼容输入：

- Alembic migration history
- 用于断言旧字段不存在的测试
- 旧产品/参考文档中的历史说明

这里应继续遵守两条原则：

- 只保留读取兼容，不再新增新的写入路径
- 只在历史、测试、迁移说明中出现，不再作为主实现和主示例

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
