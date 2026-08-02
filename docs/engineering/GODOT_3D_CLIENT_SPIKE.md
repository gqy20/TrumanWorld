# Godot 3D 客户端技术验证计划

状态：基础 Web/Bridge、地图内容管线与权威时间/活动垂直切片已执行，20～50 Agent 性能验证尚未执行。

后继正式实施规格见 [GODOT_WORLD_IMPLEMENTATION.md](GODOT_WORLD_IMPLEMENTATION.md)。本文只保留
隔离技术验证范围和决策门槛，不作为完整迁移方案。

本文记录 Truman World 在现有 voxel 舞台稳定后，对 Godot Web 3D 客户端进行隔离验证的范围和决策标准。它不是当前前端迁移计划，也不改变 FastAPI 作为权威模拟状态来源的边界。

相关背景：

- 当前产品方案：[FEATURE_VOXEL_2_5D_WORLD_STAGE.md](../product/FEATURE_VOXEL_2_5D_WORLD_STAGE.md)
- 早期 Godot 2D 评估：[FEATURE_WORLD_2D_SCENE.md](../product/FEATURE_WORLD_2D_SCENE.md)
- 当前系统架构：[CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md)

## 1. 启动条件

满足以下条件后再启动验证：

1. R3F 动态 Agent 层、连续路径移动和实时事件流已稳定运行。
2. 已获得浏览器端真实性能数据，而不是仅根据功能清单判断引擎优劣。
3. 产品目标明确需要至少一项游戏引擎能力：自由导航、动态避障、复杂动画状态机、场景编辑器协作，或原生桌面与移动客户端。

如果需求仍是正交 2.5D 观察舞台、地点间移动和 DOM 信息面板，不启动迁移。

## 2. 验证目标

建立一个与正式世界页隔离的 Godot Web 垂直切片，验证：

- Godot Web 能否稳定嵌入 Next.js 导演控制台。
- 20 至 50 个 Agent 同屏移动时的帧率、内存和加载成本。
- FastAPI 世界事件能否通过 WebSocket 或 SSE 适配层驱动 Godot 场景。
- React 与 Godot 之间能否可靠同步选中 Agent、镜头焦点和详情面板。
- Godot 的场景编辑、导航和动画工作流是否显著降低后续制作成本。

## 3. 推荐架构

```text
Next.js director console
  ├─ timeline / panels / modals / accessibility fallback
  └─ isolated Godot Web host
       ├─ render and input
       ├─ local visual interpolation
       └─ postMessage / JavaScriptBridge
                 ↓
          frontend event adapter
                 ↓
          FastAPI authoritative state
```

第一版使用独立路由或同源 `iframe`，不把 Godot 生成的运行时代码直接耦合进 React 组件树。正式实现如需更紧密的 Canvas 集成，再评估自定义 HTML shell。

Godot 只负责渲染、输入和客户端插值：

- Agent 的身份、地点、事件与模拟时间来自 FastAPI。
- Godot 不运行 LLM Agent，不保存权威世界状态。
- 路径到达后必须以服务端快照校准。
- 途中相遇、中断和拥堵仍需要后端 `in_transit` 模型，不由客户端自行推断。

## 4. 最小协议

React 到 Godot：

```json
{
  "type": "world_snapshot",
  "run_id": "run-id",
  "tick": 42,
  "locations": [],
  "agents": []
}
```

```json
{
  "type": "world_event",
  "event": {
    "id": "event-id",
    "tick_no": 43,
    "event_type": "move",
    "actor_agent_id": "agent-id",
    "payload": {
      "from_location_id": "library",
      "to_location_id": "cafe"
    }
  }
}
```

Godot 到 React：

```json
{
  "type": "selection_changed",
  "kind": "agent",
  "id": "agent-id"
}
```

协议需要版本号、运行 ID 和消息类型白名单。宿主页面必须校验 `postMessage` 来源，不能直接执行 Godot 传入的任意命令。

## 5. Web 约束

- Godot 4.7.1 Web 使用 WebGL 2.0 Compatibility renderer，不使用 Forward+、Mobile 或 WebGPU。
- 优先使用单线程 Web 导出，避免为 `SharedArrayBuffer` 引入 COOP/COEP，并影响第三方页面集成。
- Godot 4.x 的 C# 项目不能导出到 Web，验证代码使用 GDScript。
- 多线程或 GDExtension 仅在单线程性能无法达标后评估。
- WebSocket Web 导出不能依赖自定义握手 Header。认证优先使用同站 Cookie、短期连接令牌或经过审查的子协议。
- 移动端必须单独测试 WebAssembly 启动时间、WebGL 兼容性和后台标签页恢复行为。

参考：

- [Godot Web export](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html)
- [JavaScriptBridge](https://docs.godotengine.org/en/4.4/tutorials/platform/web/javascript_bridge.html)
- [WebSocketPeer](https://docs.godotengine.org/en/stable/classes/class_websocketpeer.html)
- [NavigationAgent3D](https://docs.godotengine.org/en/stable/classes/class_navigationagent3d.html)

## 6. 垂直切片范围

包含：

- 一张与正式 voxel 世界相同布局的测试地图。
- 20 至 50 个简化 Agent。
- `idle / walking / talking / working` 四种视觉状态。
- 基于录制事件 fixture 和实时事件流的路径移动。
- Agent 点击、镜头聚焦、React 详情面板联动。
- reduced-motion、低画质模式和连接中断后的快照恢复。

不包含：

- 正式页面替换。
- 后端在途状态改造。
- 物理战斗、玩家控制或完整游戏 HUD。
- 正式美术资产批量迁移。
- 原生桌面和移动端发布。

## 7. 评估指标

同一台桌面设备和一台目标移动设备上，对 R3F 正式舞台与 Godot 切片记录：

| 指标 | 说明 |
|------|------|
| 首次可交互时间 | 从页面导航到镜头可操作 |
| 冷启动传输体积 | WASM、脚本、纹理和场景资源总量 |
| 稳态帧率 | 20、50 个移动 Agent 下的 P50 / P95 |
| 主线程长任务 | 交互期间超过 50ms 的任务数量 |
| 内存峰值 | 加载完成与连续运行 10 分钟后的内存 |
| 状态延迟 | FastAPI 事件产生到场景开始反馈的时间 |
| 恢复能力 | 断流、切换标签页、重新连接后的校准结果 |
| 制作效率 | 完成一个新地点和一种动画状态所需改动 |

## 8. 决策门槛

只有同时满足以下条件，才提出正式迁移 ADR：

1. Godot 在目标设备达到可接受的加载和稳定帧率。
2. 场景、动画或导航制作效率明显优于继续扩展 R3F。
3. React 与 Godot 的通信没有造成双重状态源。
4. DOM 可访问性后备视图、监控和自动化测试可以保留。
5. 产品路线确认需要浏览器之外的原生客户端，或需要复杂游戏引擎能力。

否则保留 R3F 为正式舞台，并将 Godot 验证结果归档为技术研究。

## 9. 预期产物

- `spikes/godot-world/` 独立 Godot 工程。
- `frontend/app/labs/godot-world/` 隔离宿主页。
- 版本化的世界事件 DTO。
- 性能对比记录与浏览器兼容矩阵。
- 最终 ADR：继续 R3F、局部采用 Godot，或迁移 3D 客户端。
