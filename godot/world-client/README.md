# Truman World Godot Client

Phase 0～2 隔离客户端，用于验证 Godot Web、Next.js 宿主、版本化 Bridge 协议、语义地图
内容管线以及权威世界时间下的持续活动表现。它尚未连接正式 Run，也不是当前世界页的默认渲染器。

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
