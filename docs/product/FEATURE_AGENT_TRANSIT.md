# Agent 在途状态与连续移动

状态：第一阶段已实现。

## 1. 目标

让移动成为服务端权威的世界状态，而不只是前端收到 `move` 事件后补播的动画。Agent 从出发到到达期间不属于任一地点，页面刷新、SSE 重连和模拟暂停后仍可从世界快照恢复其路径。

## 2. 状态模型

```text
at_location
    │ move accepted
    ▼
in_transit
    │ arrival tick reached
    ▼
at_location
```

`move` 事件继续作为移动开始事件，以兼容现有时间线、统计和客户端。事件负载增加 `movement_id`、`started_tick`、`arrival_tick` 与 `state`。到达时产生 `move_arrived` 事件。

服务端只持久化移动区间，不写入逐帧坐标。客户端根据路径和移动区间进行连续插值，并在快照更新后校准。

第一阶段使用固定两个 tick 的移动耗时；基于道路长度、Agent 速度和拥堵的耗时模型留到后续迭代。

## 3. 验收场景

```gherkin
Feature: Agent 在地点之间移动

  Scenario: 接受移动后进入在途状态
    Given Alice 当前位于住宅
    When Alice 决定移动到咖啡店
    Then Alice 的移动状态为 in_transit
    And Alice 不计入住宅或咖啡店的在场人数
    And 咖啡店不会在到达前成为 Alice 的当前位置

  Scenario: 到达 tick 提交目的地
    Given Alice 正在前往咖啡店
    When 世界时钟到达该移动的 arrival_tick
    Then Alice 的当前位置变为咖啡店
    And Alice 的移动状态被清除
    And 世界产生一次 move_arrived 事件

  Scenario: 在途 Agent 不能执行地点动作
    Given Alice 正在移动
    When Alice 尝试交谈、工作、休息或再次移动
    Then 动作以 agent_in_transit 原因拒绝

  Scenario: 页面刷新恢复移动
    Given Alice 的在途状态已持久化
    When 导演控制台重新获取世界快照
    Then 快照在顶层 agents 中包含 Alice
    And Alice 不属于任一地点 occupants
    And 快照包含恢复连续路径所需的移动区间

  Scenario: 暂停和恢复不改变画面位置
    Given Alice 正在道路上连续移动
    When 模拟被暂停
    Then Alice 的逐帧位置停止推进
    When 模拟恢复
    Then Alice 从暂停时的像素位置继续移动
```

## 4. 兼容边界

- `locations[].occupants` 保留，语义严格限定为已经到达该地点的 Agent。
- 世界快照新增顶层 `agents[]`，作为完整 Agent 集合；旧客户端仍可读取地点数据。
- `current_location_id` 在 API 中对在途 Agent 返回 `null`，持久层保留出发地点用于兼容既有模拟代码，权威判定以 `movement.state` 为准。
- `move` 继续计入既有移动统计；`move_arrived` 不重复计数。
- 3D 客户端按程序化道路的实际长度计算播放时长，并在暂停时冻结逐帧进度。
- 服务端暂时保持固定两 tick：数据库地点坐标与程序化 3D 道路不是同一拓扑，在共享路线模型建立前不混用两套距离。

## 5. 暂不包含

- 逐像素服务端位置写入。
- 中途相遇、碰撞和动态避障。
- 基于共享道路拓扑的服务端移动耗时。
- 移动取消、折返和目的地变更。
- Godot 客户端实现。
