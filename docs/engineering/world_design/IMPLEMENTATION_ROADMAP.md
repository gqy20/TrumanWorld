# World Design Implementation Roadmap

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 总体策略

不直接重写 `sim` 主链路。

先做制度资产层，再做最小规则裁决层，最后补治理执行层和解释链。

## 2. 推荐阶段

### 阶段 1：资产层落位

目标：

- 在 bundle 中新增 `constitution.md`
- 在 bundle 中新增 `rules.yml`
- 在 bundle 中新增 `policies/default.yml`
- 扩展 loader，支持读取完整 world design 资产包

这个阶段重点不是 evaluator，而是 schema 与边界。

### 阶段 2：统一 facts

目标：

- 定义平台 facts 命名空间
- 让 `rules.yml` 只引用统一 facts
- 避免规则资产直接耦合 Python 字段名

第一版建议支持：

- `actor.*`
- `target_agent.*`
- `target_location.*`
- `world.*`
- `policy.*`

### 阶段 3：最小规则裁决层

目标：

- 在动作进入 `ActionResolver` 前做规则评估
- 输出结构化裁决结果
- 不推翻现有物理校验和基础执行逻辑

第一版只需要支持少量规则模板和条件操作符。

### 阶段 4：治理执行层

目标：

- 根据 `violates_rule` 或高风险裁决，决定是否观察到、是否介入
- 把执行强度主要交给 `policies/*.yml`
- 记录执行事件和长期状态变化

第一阶段不必实现完整政府组织模拟。

## 3. 当前仓库的建议切入点

### 3.1 Bundle 侧

- 扩展 `backend/app/scenario/bundle_registry.py`
- 增加对 `rules.yml`、`constitution.md`、`policies/` 的加载能力

### 3.2 Runtime 侧

- 在 `backend/app/scenario/runtime/` 下增加 world design 运行时装配
- 把散落的 world design 配置收敛成一个 package

### 3.3 Simulation 侧

- 在 `backend/app/sim/` 下引入最小 rule evaluation
- 保留 `ActionResolver` 的底层执行职责
- 后续再补治理执行器

### 3.4 API / Timeline 侧

- 在 event payload 中增加规则解释信息
- 后续统一暴露到 timeline / agent detail

## 4. 当前不建议立即做的内容

- 完整经济系统
- 商品与许可体系
- 完整组织治理建模
- 复杂 DSL
- 让 agent 直接读完整规则文件

先把 world 设计的基础资产层和解释链打稳。
