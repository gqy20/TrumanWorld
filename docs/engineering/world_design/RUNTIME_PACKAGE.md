# Runtime Package

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 目标

bundle 中的 world design 资产不应在 runtime 中以松散字典形式四散流动。

平台应把它们装配成一个统一的 runtime package。

一句话：

**bundle 资产先组装成 package，再进入 sim、agent、director 等模块。**

当前实现状态：

- 已实现最小版 runtime package
- 当前入口为 `load_world_design_runtime_package(scenario_id: str | None)`
- 当前 package 已包含 `world_config / rules_config / policy_config / constitution_text`
- 当前只支持默认 policy 文件 `policies/default.yml`
- 动态 overlay 尚未实现

## 2. 为什么需要 runtime package

当前 bundle 读取方式以单文件读取为主。

如果后续继续直接在不同模块各自读取：

- `world.yml`
- `rules.yml`
- `policies/*.yml`
- `constitution.md`

会带来几个问题：

- 加载逻辑分散
- schema 校验分散
- 缓存和回退逻辑分散
- sim、agent、director 对同一资产的理解不一致

因此需要统一 runtime package。

## 3. package 应包含什么

第一版建议 package 至少包含：

- `scenario_id`
- `world_config`
- `rules_config`
- `policy_config`
- `constitution_text`
- `facts_schema_version`
- `rule_schema_version`
- `policy_schema_version`

可选：

- `metadata`
- `resolved_defaults`
- `validation_warnings`

## 4. 建议数据结构

当前 runtime 层已经形成类似结构：

```python
WorldDesignRuntimePackage(
    scenario_id="narrative_world",
    world_config={...},
    rules_config={...},
    policy_config={...},
    constitution_text="...",
    facts_schema_version=1,
    rule_schema_version=1,
    policy_schema_version=1,
)
```

当前实际实现还包括：

- `facts_schema_version`
- `rule_schema_version`
- `policy_schema_version`

第一版已经不再只传零散 `dict`。

## 5. 加载顺序建议

建议统一加载顺序：

1. 读取 bundle
2. 读取 `world.yml`
3. 读取 `rules.yml`
4. 读取 `policies/default.yml`
5. 读取 `constitution.md`
6. 进行 schema 校验与默认值补齐
7. 生成 runtime package

这样可以保证：

- 所有模块看到的是同一份解析结果
- 默认值和兼容逻辑只写一处

## 6. 第一版加载失败策略

必须先定义失败策略。

当前实现：

- `world.yml` 缺失：视为严重错误
- `rules.yml` 缺失：回退为空规则集
- `policies/default.yml` 缺失：回退到平台默认 policy 值
- `constitution.md` 缺失：回退为空文本

这样更适合渐进迁移。

## 7. package 的消费方

### 7.1 `sim`

主要消费：

- `rules_config`
- `policy_config`
- `world_config`

用途：

- rule evaluation
- enforcement input
- world state projection

### 7.2 `agent`

主要消费：

- `world_config`
- `policy_config`
- `constitution_text` 的有限解释性输出

用途：

- agent visible summary
- world common knowledge
- risk and notice injection

### 7.3 `director`

主要消费：

- `policy_config`
- `world_config`

用途：

- 调整治理参数
- 生成干预解释
- 对场景结构做观察和控制

## 8. 与当前仓库的关系

当前仓库已经有：

- `backend/app/scenario/bundle_registry.py`
- `backend/app/scenario/runtime/world_config.py`

现在还已经有：

- `backend/app/scenario/runtime/world_design.py`
- `backend/app/scenario/runtime/world_design_models.py`

已经落地的方向是：

- 在 `backend/app/scenario/runtime/` 下增加 world design package 装配逻辑
- 不再让各模块直接各自读取 bundle 文件

## 9. 第一版建议接口

当前已提供入口：

- `load_world_design_runtime_package(scenario_id: str | None) -> WorldDesignRuntimePackage`

同时仍保留单文件 helper 作为兼容层。

## 10. package 与缓存

这层天然适合缓存。

当前缓存 key 包含：

- `project_root`
- `scenario_id`

后续如果支持 policy 动态叠加，可再扩展运行时变体缓存策略。

## 11. package 与动态 policy

第一版 package 可先只包含默认 policy。

后续如果支持 director 注入临时 policy，可演进为：

- 基础 package：bundle 级静态资产
- 运行时 overlay：run 级动态 policy

这样不会把 bundle 静态资产和 run 时动态状态混在一起。

当前尚未实现上述 overlay 结构。

## 12. 第一版默认结论

建议默认采用：

- world design 资产先装配成 runtime package
- package 统一由 runtime 层生产
- sim / agent / director 都消费 package，而不是分别读取散文件
- 动态 policy 后续通过 overlay 叠加，而不是直接污染 bundle 基础资产

## 13. 后续待展开问题

后续可继续细化：

- package 的具体 Pydantic 模型
- 动态 policy overlay 结构
- package 与 run 级缓存失效策略
- runtime package 的 validation warnings 输出
