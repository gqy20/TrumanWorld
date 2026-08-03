# Truman World Godot Client

Phase 0～3 隔离客户端，用于验证 Godot Web、Next.js 宿主、版本化 Bridge 协议、语义地图
内容管线、权威世界时间以及对象占用和排队表现。它尚不是当前世界页的默认渲染器。

## 本地运行

```bash
make godot-test
make godot-export-map
make godot-export-web
make frontend-dev
```

打开：

```text
http://127.0.0.1:13000/labs/godot-world
```

连接真实 Campus Run：

```text
http://127.0.0.1:13000/labs/godot-world?runId=<run-id>
```

未提供 `runId` 时保留本地 Fixture 模式。真实模式由 Next.js 获取世界快照并订阅现有 SSE；Godot
不直接持有 API 凭据，收到世界事件后由宿主重新获取权威快照完成位置和资源状态校准。

Godot Web 导出物生成到 `frontend/public/godot-world/`，该目录除 `.gitkeep` 外不进入 Git。

## 地图制作与导出

地图源场景为 `scenes/maps/campus_world.tscn`。语义节点通过稳定 ID 描述 District、Location、
Zone、Portal、Route、Interactable、Slot、Spawn 和 Camera Anchor；`AmbientLandmark3D` 仅用于
视觉内容，不进入后端空间契约。

可通过两种方式导出：

- Godot 编辑器菜单 `项目 > 工具 > Export World Map`；
- 仓库命令 `make godot-export-map`。

两种方式都会更新 `scenarios/campus_world/map/world-map.json`。提交前运行 `make godot-check`；该命令
会重新导出到临时文件并拒绝过期产物，后端加载器还会校验稳定 ID、引用关系、入口连通性和
SHA-256 内容哈希。

## 当前协议

Host 到 Godot：

- `initialize`
- `world_snapshot`
- `focus_entity`
- `dispose`

Godot 到 Host：

- `ready`
- `selection_changed`

`ready` 还会报告当前 `map_id` 和 `map_content_hash`，初始化时客户端拒绝不匹配的地图版本。
协议版本为 `1`。Godot、TypeScript 和测试 Fixture 必须一起更新协议主版本。

`world_snapshot` 的客户端核心字段为 `tick / world_time / run_status / simulation_speed`。Agent 包含
服务端权威的米制位置、移动进度和活动状态；Godot 的 `ClientClock` 只投影两次校准之间的显示时间，
暂停时冻结表现，倍速变化时重新同步，不在客户端宣布活动完成。

Phase 3 中，`activities.yml` 定义活动步骤、时长区间和资源要求，`object_types.yml` 定义对象
Affordance，Godot 地图继续定义柜台、座位和排队槽位的坐标。服务端快照中的 `object_states` 是占用
与队列的权威事实，Agent 的 `visual_state / zone_id / queue_position` 只驱动客户端表现。
