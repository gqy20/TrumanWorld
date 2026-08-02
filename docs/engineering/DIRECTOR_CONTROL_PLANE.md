# 导演智能体控制平面

导演系统采用分层控制结构：Director cognition 负责提出干预，确定性控制层负责校验并编译
directive，Actor cognition 显式接收 directive，模拟执行层仍通过 `ActionResolver` 统一裁决。

```text
World snapshot
  -> candidate availability ranking
  -> Director StateGraph (select -> propose -> validate -> repair)
  -> DirectorPlan proposal
  -> validated DirectorDirective
  -> AgentActionInvocation.directives
  -> ActionIntent / ActionResult
  -> directive status and simulation events
```

## 事实来源

跨 tick 的控制事实保存在 `director_directives`；LangGraph state 只服务于一次认知运行，不作为
业务持久化来源。这样可以避免 checkpoint、世界事件和数据库任务状态之间出现冲突。

directive 状态为 `pending`、`active`、`succeeded`、`failed`、`expired` 或 `cancelled`。
同一角色收到新 directive 时，旧的活跃 directive 会以 `superseded` 原因取消。超过
`expires_at_tick` 的任务会自动过期。

每条 directive 通过 `source_memory_id` 关联导演记忆，并记录 `attempt_count`、最后尝试、最后
有效进展、最后动作和替代指令。记忆的消费与效果状态由真实执行结果派生，不再只表示计划已生成。

## 候选角色与自适应执行

导演只会看到可执行候选人。正在移动或与非主体角色交谈的 Actor 会被排除；已经与主体交谈的
Actor 会优先于空闲但距离更远的角色。模型返回后，LangGraph validation 节点会再次校验目标，
无效目标由 repair 节点确定性替换。

Actor 接受指令但动作不满足 completion criteria 时会累计尝试：第二次偏离将 advisory 升级为
priority，第三次偏离标记为 `target_drift`。下一个 tick 会把原目标重新分配给另一名可用角色，
并通过 `replaced_by_directive_id` 保留完整追踪链。

## 控制模式

- `advisory`：普通导演建议，Actor 可以结合现场自主决策。
- `priority`：高优先级或即时任务，在 Actor 上下文中优先呈现。
- `enforced`：停电、关闭等确定性世界干预；世界效果仍由现有导演事件服务执行。

无论模式如何，角色动作都不能绕过 `ActionResolver`、世界规则和治理规则。

## 执行回执

Actor 输出可以携带 `directive_id`、`directive_disposition` 和原因。运行时只接受本次 invocation
中实际存在的 directive ID，未知 ID 会被丢弃。回执随 Action payload 进入事件，控制仓储根据
真实 `ActionResult` 和 completion criteria 更新任务状态。

## Tick 一致性

inline 与 isolated tick 都执行以下生命周期：

1. 加载或生成 DirectorPlan；
2. 将 proposal 编译为 directive 并分配给目标 Actor；
3. Actor 返回带 directive 关联的动作；
4. 持久化世界结果、导演计划与 directive；
5. 根据 accepted/rejected results 完成、失败或过期 directive。

自动导演仍由 `TRUMANWORLD_DIRECTOR_AUTO_INTERVENTION_ENABLED` 控制，认知后端由
`TRUMANWORLD_DIRECTOR_BACKEND` 选择。决策间隔使用
`TRUMANWORLD_DIRECTOR_DECISION_INTERVAL`，最小值为 1。

Prometheus 指标包括 `trumanworld_director_decision_total`、
`trumanworld_director_directive_total` 和 `trumanworld_director_directive_response_ticks`，用于区分
图运行成功与业务目标真正达成。
