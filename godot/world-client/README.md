# Truman World Godot Client

Phase 0～3 与 Phase 4 具身展示切片，用于验证 Godot Web、Next.js 宿主、版本化 Bridge 协议、
语义地图内容管线、权威世界时间、对象占用、连续动作和对话表现。它尚不是当前世界页的默认渲染器。

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

开发导出额外支持在私有局域网地址上使用普通 HTTP：

```bash
make godot-export-web
make frontend-dev
```

`godot-export-web` 会对 Godot 单线程导出壳应用一个受限补丁：仅对 RFC 1918、共享地址空间和
IPv6 ULA 主机忽略 Secure Context 启动检查，并使用 Dummy 音频驱动。这个开发构建不提供音频、
麦克风、剪贴板或 Gamepad；公网部署仍应使用 HTTPS。

连接真实 Campus Run：

```text
http://127.0.0.1:13000/labs/godot-world?runId=<run-id>
```

未提供 `runId` 时保留本地 Fixture 模式。真实模式由 Next.js 获取世界快照并订阅现有 SSE；Godot
不直接持有 API 凭据，收到世界事件后由宿主重新获取权威快照完成位置和资源状态校准。

Godot Web 导出物生成到 `frontend/public/godot-world/`，该目录除 `.gitkeep` 外不进入 Git。

## 地图制作与导出

地图源场景按 scenario 拆分为 `scenes/maps/<scenario_id>.tscn`。当前注册了 `campus_world` 与
`narrative_world`；Web 宿主根据世界快照的 `scenario_id` 选择白名单中的场景，不接受任意资源路径。
语义节点通过稳定 ID 描述 District、Location、
Zone、Portal、Route、Interactable、Slot、Spawn 和 Camera Anchor；`AmbientLandmark3D` 仅用于
视觉内容，不进入后端空间契约。

可通过两种方式导出：

- Godot 编辑器菜单 `项目 > 工具 > Export World Map`；
- 校园命令 `make godot-export-map`；
- 楚门小镇命令 `make godot-export-narrative-map`。

产物分别写入对应的 `scenarios/<scenario_id>/map/world-map.json`。提交前运行 `make godot-check`；
该命令会检查所有已注册地图，重新导出到临时文件并拒绝过期产物。后端加载器还会校验稳定 ID、
引用关系、入口连通性和 SHA-256 内容哈希。同一个 Run 不支持中途更换 scenario；切换世界应创建或
打开另一个 Run，Godot Web 页面会随 `scenario_id` 重新装载地图。

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

当前角色采用程序化人形，可表现步行、慢跑、排队、坐下、饮用、使用设施和相向交谈。右键拖动
旋转导演镜头，中键拖动平移，滚轮缩放；选中居民后镜头会平滑跟随。客户端还会按权威世界时间
更新昼夜环境，并用场景内环形标记显示资源可用、占用和排队状态。
