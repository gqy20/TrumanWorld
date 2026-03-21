# World Asset Model

- 类型：`engineering`
- 状态：`draft`
- 负责人：`repo`
- 基线日期：`2026-03-21`

## 1. 目标

world 设计的第一优先级是资产化，但资产化的对象应是“制度内容”和“世界内容”，不是把所有执行逻辑搬进 YAML。

一句话：

**世界内容资产化，执行语义代码化。**

## 2. 资产分层

### 2.1 `world.yml`

职责：

- 静态世界事实
- 地点、实体、公开常识、时间节律
- 规则引用的数据字典

典型内容：

- `world_start_time`
- `daily_rhythm`
- `locations`
- `location_id_map`
- `location_purposes`
- `social_norms`

它回答的是：

- 世界里有什么
- 这些对象默认是什么样

### 2.2 `rules.yml`

职责：

- 制度规则
- 行为合法性判断
- 风险型规则
- 规则优先级和解释 key

它回答的是：

- 什么情况下允许
- 什么情况下违规
- 什么情况下高风险

### 2.3 `policies/default.yml`

职责：

- 默认政策参数
- 可切换、可覆盖的动态治理值
- 世界运行时的制度基线

典型内容：

- `closed_locations`
- `inspection_level`
- `sensitive_locations`
- `talk_risk_after_hour`

它回答的是：

- 当前制度环境是什么样
- 哪些规则参数正在被临时覆盖

### 2.4 `constitution.md`

职责：

- 人类可读的世界原则
- 显规则与潜规则说明
- 规则冲突顺序
- 面向前端、调试、运营的制度解释

它不直接参与求值，但参与解释链。

## 3. 平台事实空间

规则资产不应直接绑定 Python 字段名，而应引用平台统一 facts。

第一版建议只支持以下命名空间：

- `actor.*`
- `target_agent.*`
- `target_location.*`
- `world.*`
- `policy.*`

示例：

- `actor.location_id`
- `actor.workplace_id`
- `actor.status.suspicion_score`
- `target_location.type`
- `target_location.capacity_remaining`
- `world.time_period`
- `world.is_weekend`
- `policy.closed_locations`

## 4. 为什么要先做资产模型

当前仓库已经有 bundle 加载基础，但还没有制度资产层。

如果不先把 world 相关内容分层：

- 规则会继续散落在 Python 和 prompt 中
- scenario 无法只靠换 bundle 改制度
- 后续引擎即使抽出来，也只是换地方写硬编码

因此第一阶段重点应是：

1. 定义资产边界
2. 定义 facts 命名空间
3. 让 scenario bundle 能稳定承载 world 制度内容

## 5. 当前仓库的建议目录

```text
scenarios/<scenario_id>/
  scenario.yml
  constitution.md
  world.yml
  rules.yml
  policies/
    default.yml
```

第一阶段不必马上引入：

- `goods.yml`
- `permits.yml`
- 复杂经济与组织建模

先把世界设计的基础制度层站住。
