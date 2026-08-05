# Godot 具身世界完整实施方案

- 类型：`engineering`
- 状态：`in_progress`（Phase 0～4 与正式世界页受控接入已实现）
- 目标版本：Godot `4.7.1-stable` Standard / GDScript
- 适用范围：浏览器端 3D 世界、地图内容生产、具身活动展示
- 不改变：FastAPI 权威状态、LangGraph 认知、Director 控制平面、数据库事实来源

本文定义 Truman World 从 React Three Fiber Voxel 舞台演进为 Godot 具身世界客户端的完整
实现边界、数据模型、通信协议、仓库结构、开发阶段、测试策略和迁移门槛。

它不是要求立即删除现有 R3F 舞台的迁移命令。实施必须先完成隔离垂直切片，再依据本文的量化
门槛决定是否替换正式世界 Canvas。前置技术验证见
[GODOT_3D_CLIENT_SPIKE.md](GODOT_3D_CLIENT_SPIKE.md)。

## 1. 决策摘要

Truman World 采用以下长期分层：

```text
LangGraph / Director
  负责：人物为什么行动、何时重新计划、是否回应社会机会
                    ↓ high-level intent / directive
FastAPI embodied simulation
  负责：世界时间、活动状态、空间占用、感知、偶遇、规则裁决和持久化
                    ↓ authoritative snapshot / event
Godot world client
  负责：地图与角色场景、动画、镜头、输入、本地插值和视觉反馈
                    ↓ selection / inspected object
Next.js director console
  负责：运行控制、时间线、人物详情、导演视图、认证和可访问性后备界面
```

核心决策：

1. Godot 接管 3D 世界客户端和地图制作，不接管 LLM、Director 或业务数据库。
2. FastAPI 仍是角色位置、活动、占用、偶遇和世界事件的唯一权威来源。
3. Next.js 继续作为产品外壳；Godot Web 通过同源宿主页嵌入，不复制导演控制台。
4. 地图编辑在 Godot 中完成，并导出确定性的 `world-map.json` 给后端和客户端共同消费。
5. 高层认知 Tick 与具身模拟时间分离；不能通过提高 LLM 调用频率模拟连续运动。
6. 第一阶段使用显式导航图和交互锚点，不让后端解析 Godot NavMesh 二进制。
7. 现有 R3F 舞台在 Godot 达到验收门槛前保留为可回退客户端。

### 1.1 实施状态

截至 2026-08-05，Phase 0～4 与正式世界页首轮受控接入已完成：

- 固定并验证 Godot `4.7.1-stable`；
- 建立 `godot/world-client/` 隔离工程；
- 建立 `/labs/godot-world` Next.js 宿主页；
- 实现版本化 Envelope 和双向来源校验；
- 实现 `ready / initialize / world_snapshot / focus_entity / selection_changed / dispose`；
- 使用三名 Fixture Agent 完成静态场景 Spawn 和点击选择；
- 增加 Godot Headless 测试与 Web Release 导出 Make 目标；
- 通过真实 Chromium 中的 iframe、WebAssembly 和选择闭环验证。
- Godot 已提供语义地图节点、编辑器菜单和 Headless 确定性导出器；
- `campus_world` 已生成版本化 `world-map.json`，覆盖地点、区域、门、路线、对象、槽位、出生点和镜头锚点；
- FastAPI Scenario 层已校验地图 Manifest、稳定 ID、跨对象引用、路线连通性和内容哈希；
- Web 运行场景直接实例化同一地图场景，并在 `ready` 中上报 `map_id` 与内容哈希。
- FastAPI 使用导出地图的米制 Route Graph 作为移动距离与路径的权威来源；
- Move 已从仅依赖 Tick 的状态迁移为带精确开始/到达世界时间的米/秒路径区间；
- Agent 已持久化 `ActivityInstance`，支持导航、执行、完成和中断的确定性状态迁移；
- 世界快照直接提供 `tick / world_time / run_status / simulation_speed`、权威坐标和活动进度；
- Godot ClientClock 在暂停、恢复和倍速变化后按服务端世界时间校准，Agent 只做视觉插值；
- 页面刷新从数据库恢复活动，自动调度会跳过忙碌 Agent，避免活动中重复触发认知决策。
- `campus_world` 已加载并严格校验 `activities.yml` 与 `object_types.yml`；
- 咖啡活动被确定性分解为点单、落座和饮用步骤，区间时长由 Run Seed 稳定解析；
- 柜台、座位和排队槽位来自 Godot 地图，服务端负责唯一占用、队首推进、完成/中断释放；
- 资源冲突、刷新恢复、槽位坐标和队列站位已经由 API 端到端测试覆盖；
- 活跃移动或活动会阻止睡眠时段快进，避免一个 Tick 直接消费完整持续区间；空闲世界仍可快进到起床时间；
- Campus Actor 已允许输出 `start_activity / interrupt_activity`，上下文会提供合法活动及目标地点；
- Godot Labs 支持通过 `?runId=<id>` 获取真实快照并订阅 SSE，事件到达后批量通知并校准快照。
- Phase 4 首个服务端切片已落地：确定性网格空间索引会从移动路径、活动槽位和地点入口解析
  权威位置，按 Zone、距离、Seed 冷却相位和既有对话筛选唯一偶遇候选。
- `encounter_candidate_created` 会在下一认知轮只唤醒稳定选定的一方进入 LangGraph；交谈映射为
  `stop_and_talk`，保持原动作则记录 `ignore`。交谈会冻结双方的路径进度，暂停并释放活动资源；
  对话关闭后按剩余时长恢复移动或原活动，刷新恢复时也会修复已失去对话的孤立暂停状态。
- CLI 已提供 `world spatial`、`world encounters`、`agent activity-start` 和
  `agent activity-interrupt`，调试写操作复用正式 Tick 锁、事务和事件持久化。
- Godot Web 会从同一份语义地图生成轻量道路、地点建筑和活动物件；居民标签按世界尺寸渲染，
  不再以固定屏幕字号遮挡舞台。正式 Voxel 舞台会为进行中的具身活动显示可点击状态和进度。
- Godot 单线程开发导出会在私有局域网 HTTP 上跳过启动壳的 Secure Context 检查，并使用 Dummy
  音频驱动；补丁不对公网主机放行，正式部署仍使用 HTTPS。
- Godot 居民已经从标记点升级为程序化具身角色，支持步行、慢跑、排队、坐下、饮用、交谈和
  使用设施的连续姿态；移动、动作、活动进度与权威世界时钟同步，客户端不反向修改事实状态。
- 活跃对话由后端根据对话生命周期事件投影到世界快照；客户端据此让参与者相向、区分说话与
  倾听，并显示最近一句话。暂停中的移动或活动会自然表现为原地交谈。
- 世界客户端已经具备导演式轨道镜头、角色跟随、昼夜光照、道路与建筑体量、树木和路灯等环境
  层，以及交互槽位的可用、占用、排队视觉状态。程序化建筑采用低墙与后半屋顶的切面式结构，
  避免地点中心的室内居民被实心建筑遮挡，同时不篡改后端权威位置。
- 正式 `/runs/[runId]/world` 页面提供 `director / stage / 3d` 三种 URL 驱动视图；Godot 作为第三种
  观察方式复用 `WorldContext` 的权威快照、轮询和 SSE，不再创建第二套页面数据源。
- `world-snapshot-adapter` 将正式世界响应投影为版本化 Godot 协议；Godot 的角色/地点选择会同步
  回统一 URL、智能体弹窗和世界信息抽屉。`/labs/godot-world` 继续作为独立 Fixture 与协议调试入口。
- 楚门小镇采用三层空间：`44×34m` 语义核心保持地点、入口和路线坐标不变；`180×110m` 视觉缓冲区
  延续道路、街区、住宅和绿化；约 `300×346m` 的海面与地平线层配合距离雾隐藏资产边缘。外围建筑
  使用低成本 LOD，不进入 Agent 导航或后端位置事实。
- 建筑正面由 Blender 生成器的局部朝向统一控制，纵向街道住宅会围绕地块中心旋转；道路和人行道
  贯穿视觉缓冲区，不再在核心地块边缘截断。摄影棚边界保留为叙事资产，但移出普通概览镜头，只有
  专门的剧情镜头才能揭示。

Godot 已进入正式世界页但尚未成为默认视图。Phase 4 仍缺少 Portal 传播、同行、主动加入活动、
室内外切换与更完整的多人会话编排；这些能力不能由客户端自行补造权威状态。当前矢量角色和
Blender 小镇属于首轮正式展示资产，后续可在协议不变的前提下继续替换角色骨骼、动画树和模块化
场景资产。

## 2. 目标与非目标

### 2.1 目标

- 角色拥有权威位置、朝向、运动模式、活动进度和资源占用。
- 地图包含建筑、Zone、入口、道路、对象和交互槽位，而不只是地点中心点。
- 高层意图能够确定性分解为进入、排队、落座、使用对象和离开等步骤。
- 角色能够在途中或活动现场感知他人，产生偶遇、招呼、交谈和同行。
- 页面刷新、暂停、恢复、断流重连和回放后，角色状态保持一致。
- 地图制作者主要使用 Godot Editor，而不是手写大量坐标。
- 20 至 50 个简化角色同屏时保持可接受的 Web 性能。
- Next.js 中的时间线、Director、详情面板和 DOM 无障碍能力继续可用。

### 2.2 非目标

- 不构建传统多人联机游戏服务器。
- 不让 Godot Web 客户端直接写入世界状态或数据库。
- 不把 LangGraph 节点迁移成 GDScript。
- 不在第一阶段实现战斗、刚体破坏、载具或复杂物理。
- 不要求所有背景建筑都可进入。
- 不在第一阶段实现自由玩家角色控制。
- 不为每一渲染帧持久化坐标。
- 不用 YAML 编写碰撞算法、寻路算法或复杂行为程序。

## 3. 当前基线与需要替换的边界

当前系统已经具备：

- FastAPI Tick、事务化事件写入和运行恢复。
- LangGraph Actor / Director 认知链路。
- 服务端 `in_transit` 状态、路线节点、距离、速度和到达 Tick。
- 共享 World Map V1 道路拓扑。
- R3F 连续插值、步态、路口让行和视觉避让。
- Next.js 世界快照、SSE 时间线和导演控制台。

当前缺口：

- 服务端只知道地点间移动，不知道角色在室内或道路上的细粒度占用。
- 移动中的角色不属于任何地点，也不能参与社会互动。
- 座位、柜台、门、队列和交互对象没有权威状态。
- 视觉避让与路口让行不影响服务端事实。
- R3F 场景主要由程序化 Prefab 构建，精细场景制作成本持续上升。

Godot 不直接替换上述后端能力，而是替换或吸收以下前端职责：

- `frontend/components/voxel/` 的场景构建与角色表现。
- 前端程序化建筑布局中的可视场景部分。
- 手写的低层动画状态和相机交互。
- 后续地图、室内、对象、碰撞体和触发区的编辑工作流。

`SceneWorld -> VoxelScenePlan -> Three.js` 在迁移期间保留；Godot 使用独立、版本化的 DTO，不能
直接依赖 React 类型或 Three.js 对象。

## 4. 状态所有权

| 状态 | 权威所有者 | Godot 是否计算 | 是否持久化 |
|------|------------|----------------|------------|
| Run 状态和世界时间 | FastAPI | 只显示 | 是 |
| Agent 高层目标 | LangGraph / FastAPI | 否 | 是 |
| Director Directive | Director / FastAPI | 只显示结果 | 是 |
| 当前活动及步骤 | FastAPI | 播放对应表现 | 是 |
| 位置、路径区间、到达时间 | FastAPI | 插值和校准 | 是 |
| NavGraph | 地图导出物 | 可读取 | Scenario 快照 |
| NavMesh | Godot 场景 | 可用于视觉路径 | 作为资产 |
| 资源占用和队列 | FastAPI | 显示 | 是 |
| 感知和偶遇候选 | FastAPI | 显示提示 | 是/短期状态 |
| 动画相位和骨骼姿态 | Godot | 是 | 否 |
| 局部视觉避让 | Godot | 是 | 否 |
| 相机、选中和 Hover | Godot/React UI | 是 | 否 |
| 记忆、关系和事件 | FastAPI | 只消费 | 是 |

任何影响人物后续决策、社会记忆或世界规则的结果，都必须先成为 FastAPI 权威事件。Godot 不能因
本地碰撞、动画结束或客户端距离检测自行宣布一次相遇已经发生。

## 5. 仓库结构

正式实施采用以下目录：

```text
TrumanWorld/
├── backend/
│   └── app/
│       ├── sim/
│       │   ├── spatial/
│       │   ├── navigation/
│       │   ├── activity/
│       │   ├── affordance/
│       │   ├── occupancy/
│       │   ├── perception/
│       │   └── encounter/
│       └── protocol/
│           └── world_client.py
├── frontend/
│   ├── app/labs/godot-world/
│   ├── components/godot/
│   │   ├── godot-world-host.tsx
│   │   ├── godot-bridge.ts
│   │   └── protocol.ts
│   └── public/godot-world/
├── godot/
│   └── world-client/
│       ├── project.godot
│       ├── export_presets.cfg
│       ├── scenes/
│       │   ├── app/
│       │   ├── world/
│       │   ├── agents/
│       │   ├── locations/
│       │   └── props/
│       ├── scripts/
│       │   ├── autoload/
│       │   ├── protocol/
│       │   ├── world/
│       │   ├── agents/
│       │   ├── camera/
│       │   └── editor/
│       ├── resources/
│       ├── assets/
│       └── tests/
└── scenarios/
    └── <scenario_id>/
        ├── world.yml
        ├── activities.yml
        ├── object_types.yml
        └── map/
            ├── manifest.yml
            ├── world-map.json
            └── source_scene.tscn
```

技术验证阶段仍可先放在 `spikes/godot-world/`。决定正式采用后再移动到 `godot/world-client/`，避免
试验工程在未通过门槛前成为生产依赖。

## 6. 工具链与版本

- 引擎：Godot `4.7.1-stable` Standard。
- 脚本：GDScript，不使用 C#，确保 Web 导出可用。
- Web 渲染：Compatibility renderer / WebGL 2.0。
- 默认导出：单线程 Web；只有性能证据充分时才评估线程和 COOP/COEP。
- 资产：glTF 2.0 / GLB，贴图优先 Web 兼容压缩格式。
- Node 包管理继续使用项目现有 pnpm。
- Godot 版本必须记录在 `godot/version.txt` 或 CI 环境变量中，不能依赖开发者本机最新版本。

升级 Godot 次版本前必须：

1. 阅读官方迁移说明；
2. 重新导入全部资产；
3. 运行 Headless 测试和 Web 冒烟测试；
4. 比较导出体积、启动时间和帧率；
5. 单独提交版本升级。

## 7. Godot 场景模型

### 7.1 根场景

```text
WorldClient (Node)
├── WorldRoot (Node3D)
│   ├── Environment
│   ├── StaticGeometry
│   ├── NavigationRegion3D
│   ├── Locations
│   ├── Interactables
│   ├── Agents
│   └── Effects
├── CameraRig (Node3D)
├── SelectionController (Node)
├── OverlayAnchorRoot (Node3D)
└── Diagnostics (CanvasLayer, debug build only)
```

Autoload：

```text
BridgeClient       # JavaScriptBridge / host message adapter
ProtocolCodec      # version check, decode, validation
WorldStore         # latest authoritative snapshot and sequence
EntityRegistry     # entity_id -> Node
AssetRegistry      # semantic preset -> PackedScene
ClientClock        # interpolation time, pause and speed
Telemetry          # FPS, load and sync metrics
```

Autoload 不保存跨刷新业务事实。重载后必须重新向宿主请求完整快照。

### 7.2 地图节点类型

地图制作者通过编辑器节点表达语义：

| 节点 | 作用 |
|------|------|
| `WorldDistrict3D` | 街区范围和默认视觉环境 |
| `WorldLocation3D` | 建筑或公共地点根节点 |
| `WorldZone3D` | 房间、柜台区、座位区、入口区 |
| `WorldPortal3D` | 门、楼梯、楼层和室内外连接 |
| `RouteNode3D` | 权威导航图节点 |
| `RouteEdge3D` | 权威导航连接和距离属性 |
| `Interactable3D` | 可交互世界对象 |
| `InteractionSlot3D` | 使用对象时角色站位和朝向 |
| `SpawnAnchor3D` | 初始化或恢复的安全站位 |
| `CameraAnchor3D` | 地点聚焦镜头预设 |
| `AmbientLandmark3D` | 纯视觉建筑，不进入模拟 |

所有可导出节点必须有稳定 ID。重命名显示名称不能改变 ID；删除或替换 ID 属于 Scenario 数据迁移。

### 7.3 Agent 场景

```text
AgentAvatar3D (CharacterBody3D)
├── CollisionShape3D
├── NavigationAgent3D
├── VisualRoot
│   └── Skeleton3D / MeshInstance3D
├── AnimationTree
├── InteractionTarget (Marker3D)
├── SpeechAnchor (Marker3D)
├── SelectionArea (Area3D)
└── AgentPresenter (Node)
```

第一版动画状态：

```text
idle
walk
jog
queue
sit_down
sit_idle
stand_up
talk
listen
drink
use_object
```

动画状态由权威活动映射而来；动画完成只能通知宿主“表现已播完”，不能直接提交活动完成。

## 8. 地图制作与导出

### 8.1 为什么不直接共享 `.tscn`

Python 后端不应解析 Godot 场景文件和 NavMesh 内部格式。正式共享边界是稳定、版本化、可审查的
JSON 导出物：

```text
Godot source_scene.tscn
        ↓ editor export plugin
world-map.json
        ├── FastAPI Scenario loader
        ├── contract tests
        └── Godot runtime verification
```

### 8.2 导出 Manifest

最小结构：

```json
{
  "schema_version": 1,
  "map_id": "campus-world-v2",
  "meters_per_unit": 1.0,
  "content_hash": "sha256:...",
  "districts": [],
  "locations": [],
  "zones": [],
  "portals": [],
  "route_nodes": [],
  "route_edges": [],
  "interactables": [],
  "interaction_slots": [],
  "spawn_anchors": [],
  "camera_anchors": []
}
```

示例对象：

```json
{
  "id": "studio-cafe.window-seat-1",
  "type": "chair",
  "location_id": "studio-cafe",
  "zone_id": "studio-cafe.seating",
  "transform": {
    "position": [12.5, 0.0, 8.2],
    "rotation_y_degrees": 180
  },
  "slot_ids": ["studio-cafe.window-seat-1.sit"]
}
```

导出必须：

- 按稳定 ID 排序，避免无意义 Diff；
- 检查重复 ID、悬空引用和不连通路线；
- 将 Godot 坐标明确转换为项目坐标约定；
- 计算内容哈希；
- 在 CI 中重新导出并检查工作树无差异；
- 禁止把编辑器临时节点和纯视觉 Mesh 导入后端。

### 8.3 导航权威

第一阶段使用显式 Route Graph 作为服务端权威路线：

- 室外道路、室内走廊、门和交互槽位都映射为节点与边；
- 路径距离使用米；
- 后端在图上寻路并计算到达时间；
- Godot 根据相同节点生成平滑路径；
- `NavigationAgent3D` 只用于视觉转向、局部避让和安全贴地；
- 快照到达时，Godot 必须向权威路径进度收敛。

后续如需自由导航，可新增 NavMesh 导出适配器，但必须先定义跨 Python/Godot 可复现的路径协议。

## 9. Scenario 与 YAML 边界

YAML 管理设计时事实，地图 JSON 管理编辑器导出的空间事实，数据库管理运行时事实。

```text
设计时规则：YAML
空间几何/锚点：Godot Editor -> JSON
运行时状态：PostgreSQL / World Event
算法：Python / GDScript
```

### 9.1 `world.yml`

```yaml
schema_version: 2

world_start_time: 2026-03-02T06:00:00+00:00

spatial:
  map_id: campus-world-v2
  map_manifest: map/world-map.json
  meters_per_unit: 1.0

clock:
  cognition_interval_minutes: 5
  simulation_step_seconds: 5

perception:
  vision_range_meters: 8.0
  conversation_range_meters: 1.8
  hearing_range_meters: 5.0

encounter:
  candidate_distance_meters: 2.5
  candidate_timeout_seconds: 15
  cooldown_minutes: 30
```

### 9.2 `object_types.yml`

```yaml
schema_version: 1

object_types:
  cafe_chair:
    visual_preset: cafe_chair_wood
    slots:
      - kind: sit
        capacity: 1
    affordances:
      - action: sit
        executor: occupy_slot
        duration_seconds: [2, 4]
        interruptible: true

  coffee_counter:
    visual_preset: coffee_counter
    affordances:
      - action: order_coffee
        executor: service_queue
        duration_seconds: [30, 90]
        capacity: 1
```

### 9.3 `activities.yml`

```yaml
schema_version: 1

movement_profiles:
  walk:
    speed_mps: 1.35
    acceleration_mps2: 1.2
  jog:
    speed_mps: 2.5
    acceleration_mps2: 1.8

activities:
  drink_coffee:
    executor: consume_at_location
    default_duration_minutes: [8, 20]
    interruptible: true
    requirements:
      location_types: [cafe]
      item: coffee

  plaza_jog:
    executor: traverse_route
    movement_profile: jog
    interruptible: true
    completion:
      default_laps: [1, 3]
      allowed_routes: [central-quad-loop]
```

YAML 不保存当前坐标、队列、活动进度、感知结果、偶遇、对话或关系。复杂执行逻辑通过稳定
`executor` ID 注册到 Python，不允许在 YAML 中嵌入任意表达式或脚本。

## 10. 后端具身模拟模型

### 10.1 空间状态

```python
@dataclass(slots=True)
class SpatialState:
    entity_id: str
    position_meters: Vec3
    facing_radians: float
    zone_id: str | None
    route_edge_id: str | None
    route_progress: float
    movement_mode: str
```

权威位置可以由路径、开始时间和速度计算，不要求每个模拟步写数据库。持久化至少保存：

- 路线 ID 和节点序列；
- 开始/预计到达世界时间；
- 最近提交的空间状态；
- 暂停、中断和恢复信息。

### 10.2 活动实例

```python
@dataclass(slots=True)
class ActivityInstance:
    id: str
    agent_id: str
    activity_type: str
    status: str
    step_index: int
    started_at_world_time: datetime
    expected_end_world_time: datetime | None
    target_entity_id: str | None
    claimed_resource_ids: tuple[str, ...]
    parent_intent_id: str | None
    interruption_reason: str | None
```

状态机：

```text
planned
  → navigating
  → waiting_for_resource
  → performing
  → completed
       ↘ interrupted
       ↘ failed
       ↘ cancelled
```

### 10.3 资源占用

资源包括座位、柜台服务位、门口通行位、床和交互槽位。

```text
available → reserved → occupied → releasing → available
```

要求：

- 同一资源不能被两个活动同时权威占用；
- 预约有过期时间；
- 活动失败或取消必须释放资源；
- 抢占、排队和释放在 Tick 事务内完成；
- 排队顺序使用可复现排序，不依赖 Python 集合遍历顺序。

### 10.4 感知与偶遇

感知由服务端空间索引产生：

```text
SpatialIndex
  → range query
  → zone / portal / visibility filter
  → relationship and recent-contact context
  → PerceptionEvent
  → EncounterCandidate
```

第一版感知不需要复杂光线追踪：

- 同 Zone 默认可见；
- Portal 关闭时阻断跨 Zone 感知；
- 道路上按距离和方向筛选；
- 说话按听觉范围传播；
- 对象遮挡和完整视锥留到后续阶段。

偶遇可能结果：

```text
ignore
acknowledge
greet
stop_and_talk
walk_together
join_activity
```

低成本规则先计算是否值得唤醒智能体；只有需要人物判断时才调用 LangGraph。

## 11. 时间模型

### 11.1 两层时钟

现有 `run.tick_minutes` 继续作为认知和事务边界，默认 5 分钟。新增模拟时间处理活动内部过程：

```text
Cognition Tick：分钟级，运行 Actor / Director 图
Simulation Step：秒级或离散事件级，推进活动和空间状态
Render Frame：毫秒级，只在客户端插值
```

不能因为需要更细的动作而每秒调用 LLM。

### 11.2 离散事件优先

持续活动记录开始和预计结束时间：

```text
10:12:30 order_started
10:13:20 order_completed
10:13:20 drink_started
10:25:00 drink_expected_complete
```

模拟推进到下一个认知 Tick 前，按时间顺序处理区间内的完成、中断、到达、资源释放和相遇事件。
只有碰撞密集或接近检测需要时，才在内存中使用 1 至 5 秒微步；微步不逐个持久化。

### 11.3 持续时间

- 移动：`path_distance_meters / actual_speed_mps`。
- 固定动作：配置基础秒数或区间。
- 排队：由前方活动和服务资源剩余时间派生。
- 开放活动：由持续时间、圈数、需要满足度或日程中断条件结束。
- 随机区间：使用 Run Seed，保证相同输入可重放。

## 12. 高层意图与任务分解

LangGraph 输出保持高层：

```json
{
  "action_type": "start_activity",
  "activity_type": "drink_coffee",
  "target_location_id": "studio-cafe",
  "reason": "下午课程前休息一下"
}
```

后端 `ActivityPlanner` 分解为：

```text
Navigate(cafe.entrance)
Enter(cafe)
AcquireService(cafe.counter)
Order(coffee)
Wait(order)
AcquireOptional(cafe.available_seat)
Sit
Consume(coffee)
ReleaseResources
```

确定性执行器处理正常路径。以下情况才重新唤醒认知：

- 目标不可达；
- 等待超过角色容忍度；
- 关键资源长期不可用；
- 发生高价值偶遇；
- Director Directive 到达；
- 日程即将冲突；
- 世界规则使活动不可继续。

Director 只能改变机会、优先级、地点状态或提供建议，不能绕过 `ActionResolver` 和资源裁决。

## 13. 客户端协议

### 13.1 传输边界

浏览器版本由 Next.js 宿主负责认证、请求世界快照和订阅 SSE。宿主通过 JavaScriptBridge 或
`postMessage` 将经过校验的消息批量发送给 Godot。Godot 不在第一版直接连接 FastAPI。

这样可以：

- 复用现有 API base URL、Cookie 和错误处理；
- 避免 Godot Web 的自定义 Header 限制；
- 保持单一 SSE 连接；
- 由 React 控制重连和降级；
- 让 R3F 与 Godot 共享同一上游数据源。

### 13.2 通用 Envelope

```json
{
  "protocol_version": 1,
  "message_id": "uuid",
  "run_id": "run-id",
  "sequence": 1042,
  "sent_at": "2026-08-03T10:00:00Z",
  "type": "world_snapshot",
  "payload": {}
}
```

要求：

- 未知协议主版本立即拒绝并显示兼容错误；
- 未知消息类型记录一次限流 Warning，不执行；
- `run_id` 不匹配时丢弃；
- `sequence` 小于等于已应用序号时幂等忽略；
- 单次消息设置体积上限；
- 不允许传递脚本、NodePath 或可执行表达式。

### 13.3 Host → Godot

正式消息：

```text
initialize
world_snapshot
world_event_batch
run_status_changed
simulation_speed_changed
focus_entity
set_quality
dispose
```

快照示例：

```json
{
  "type": "world_snapshot",
  "payload": {
    "map_id": "campus-world-v2",
    "map_content_hash": "sha256:...",
    "tick": 42,
    "world_time": "2026-03-02T09:30:00Z",
    "run_status": "running",
    "agents": [
      {
        "id": "mei",
        "position_meters": [12.4, 0.0, 8.7],
        "facing_radians": 1.57,
        "zone_id": "studio-cafe.counter",
        "movement": null,
        "activity": {
          "type": "queue",
          "status": "waiting_for_resource",
          "progress": 0.0
        }
      }
    ],
    "object_states": [],
    "conversations": []
  }
}
```

移动事件必须包含路径、世界时间区间和权威终点，不能只给目标地点 ID。

### 13.4 Godot → Host

Godot 只发送用户界面意图和客户端遥测：

```text
ready
selection_changed
inspect_requested
camera_changed
visual_action_completed
client_metric_batch
client_error
snapshot_required
```

`selection_changed` 不直接改变模拟状态；React 可以据此打开 Agent 或地点详情。

### 13.5 同步策略

- 初次加载必须应用完整快照后才显示世界。
- 事件按序批量应用，不能每条跨 Bridge 调用一次。
- 发现序号缺口时暂停应用增量并请求完整快照。
- 后台标签页恢复后请求快照校准。
- Run 暂停时冻结客户端世界时间和动画推进。
- Run 倍速只改变世界时间映射，不改变权威完成顺序。
- 大误差立即校准，小误差在短窗口内平滑收敛。

## 14. Next.js 宿主实现

`GodotWorldHost` 负责：

1. 加载版本化 Godot Web 导出物；
2. 等待 Godot `ready`；
3. 在实验页获取当前世界快照，或在正式页接收 `WorldContext` 提供的受控快照；
4. 复用正式页已有 SSE，避免为嵌入视图建立重复事件连接；
5. 处理重连、快照校准和 Run 切换；
6. 将选择事件同步给 React 面板；
7. 收集加载、帧率和错误指标；
8. 在失败时切回 R3F 或 DOM 世界视图。

宿主页必须：

- 校验 `postMessage` 的 `origin` 和 `source`；
- 使用显式消息白名单；
- 在卸载时关闭 SSE、移除监听并通知 Godot dispose；
- 不把管理口令、Cookie 或内部 Header 发送给 Godot；
- 为键盘用户保留 DOM Agent/Location 列表；
- 显示明确的加载、失败和重试状态。

## 15. 持久化与事务

建议新增或扩展以下运行时数据：

```text
agent_runtime_states
  agent_id
  spatial_state_json
  activity_state_json
  updated_tick

world_object_states
  run_id
  object_id
  state_json
  updated_tick

activity_instances
  id
  run_id
  agent_id
  activity_type
  status
  started_at_world_time
  expected_end_world_time
  state_json

resource_claims
  run_id
  resource_id
  activity_id
  status
  expires_at_world_time
```

第一阶段可以把空间和活动快照保存在 Agent JSON 字段中，但资源唯一占用必须有数据库约束或事务内
确定性裁决，不能依赖客户端。

以下操作必须位于现有 Tick 提交边界内：

- 活动步骤推进；
- 资源申请与释放；
- Agent 权威空间状态更新；
- World Event 写入；
- 记忆和关系派生；
- Scenario 状态更新。

Godot 动画失败不能回滚已经提交的世界事件；客户端恢复时依据最新快照重新选择表现状态。

## 16. World Event 扩展

建议新增通用事件：

```text
activity_planned
activity_started
activity_step_started
activity_step_completed
activity_interrupted
activity_resumed
activity_completed
activity_failed
resource_reserved
resource_released
perception_observed
encounter_candidate_created
encounter_resolved
walk_together_started
walk_together_ended
zone_entered
zone_left
```

时间线不必展示全部低层事件。事件包含 `visibility` 或 `narrative_priority`：

- `internal`：只用于恢复和调试；
- `detail`：Agent 详情可见；
- `story`：进入导演时间线；
- `alert`：需要运营关注。

不要为每秒位置变化写事件。

## 17. 咖啡馆垂直切片

第一阶段只做一个生产级场景，不直接扩整座小镇。

### 17.1 场景内容

- 一个室外入口和一扇门；
- 一个柜台和一个服务槽位；
- 一条最多五人的队列；
- 四张桌子、八个座位；
- 一个室外露台；
- 三至五名自主角色；
- `idle / walk / queue / order / sit / drink / talk / leave`；
- 熟人在入口、队列或座位区形成偶遇；
- 无座、长队、关门和日程冲突的失败路径。

### 17.2 完整行为

```text
Agent decides drink_coffee
  → ActivityPlanner selects Studio Cafe
  → route to entrance
  → enter zone
  → reserve/queue for counter
  → order and receive coffee
  → reserve available seat or choose takeaway
  → sit and consume
  → perceive nearby acquaintance
  → ignore/greet/talk based on cognition
  → release seat
  → resume schedule
```

### 17.3 垂直切片验收

- 两个 Agent 不能占用同一座位。
- 排队顺序在相同 Seed 下可复现。
- 中途暂停和恢复不改变结果。
- 刷新页面后恢复正确位置、活动和对象占用。
- 断开 SSE 后重连不会重复播放已应用事件。
- 角色相遇由后端产生，客户端距离检测不能伪造。
- 活动时间符合路径距离、速度、排队和配置持续时间。
- Godot 与 R3F 可以读取同一 Run，业务事实一致。

## 18. 实施阶段

### Phase 0：协议与空壳

状态：✅ 已完成（2026-08-03）。

- 建立隔离 Godot 工程和 Next.js Labs 宿主页。
- 固定 Godot 版本和 Web 导出流程。
- 实现 `ready / initialize / world_snapshot / selection_changed`。
- 使用录制 Fixture 渲染静态地图和 Agent。

退出条件：Godot 能稳定嵌入控制台，选中 Agent 能打开 React 详情。

### Phase 1：地图内容管线

状态：✅ 已完成（2026-08-03）。

- 实现场景节点类型和编辑器导出插件。
- 输出并校验 `world-map.json`。
- 后端加载地图 Manifest。
- 建立显式 Route Graph、Zone、Portal、Object 和 Slot。

退出条件：编辑器地图、后端地图和 Web 场景具有相同 ID、坐标和哈希。

### Phase 2：权威时间与持续活动

状态：✅ 已完成（2026-08-03）。

- 引入模拟秒和离散事件推进。
- 实现 `ActivityInstance`、步骤、完成和中断。
- 将现有 Move V2 迁移到米/秒路径区间。
- 扩展快照和事件协议。

退出条件：角色能够在刷新、暂停和倍速后正确完成持续活动。

### Phase 3：Affordance、占用与队列

状态：✅ 已完成（2026-08-03）。

- 加载 `object_types.yml` 和 `activities.yml`。
- 实现交互槽位、资源申请、过期和释放。
- 实现咖啡馆柜台、队列、座位和饮用流程。
- Godot 映射对应动画状态。

退出条件：咖啡馆正常路径和资源冲突路径全部通过。

当前实现把活动步骤及其资源租约保存在 Agent 的 `activity` JSON 中，并依赖既有的单 Run Tick 本地锁、
PostgreSQL advisory lock 和 Tick 事务边界保证唯一裁决。资源租约的到期时间就是当前步骤的
`expected_end_world_time`；步骤完成、活动完成或中断都会释放租约并立即推进确定性队首。若未来需要
脱离 Tick 事务并发修改资源，再升级为独立 `resource_claims` 表和部分唯一索引。

### Phase 4：感知与偶遇

状态：🟡 进行中（2026-08-03，已完成确定性候选、低频判断、暂停恢复与 CLI 诊断）。

- [x] 建立服务端空间索引。
- [x] 生成权威偶遇候选。
- [x] 接入 LangGraph 低频社会判断。
- [x] 偶遇交谈时冻结路径、释放资源并在对话关闭后恢复原任务。
- [x] Godot 基础地图几何、居民可读标签和正式舞台活动状态标记。
- [ ] 增加 Portal/听觉感知事件与候选过期清理。
- [ ] 实现同行与加入活动。
- [ ] 在 Godot 中表现偶遇提示、招呼和同行状态。

退出条件：相同 Seed 下偶遇时机和候选可复现，人物回应允许因认知而不同。

### Phase 5：正式视觉与性能

- 替换占位角色和动画。
- 完成 LOD、实例化、阴影和质量档位。
- 完成镜头、标签、气泡和地点聚焦。
- 优化桥接批次、资产体积和内存。

退出条件：达到第 21 节性能门槛。

### Phase 6：受控替换

- [x] 正式世界页增加 `director / stage / 3d` 三视图和 `?view=3d` 深链接。
- [x] 同一场景支持 Stage 和 Godot 双渲染器，并保留 Director DOM 地图。
- [x] Godot 复用正式 `WorldContext` 快照并完成选择状态双向同步。
- [x] 先对开发 Run 和测试 Scenario 开启。
- [ ] 增加场景级默认视图配置与移动端质量策略。
- [ ] 增加隐藏视图暂停、上下文丢失恢复和性能遥测。
- 观察稳定后才设为默认。

退出条件：连续运行、恢复、浏览器矩阵和运营指标达到要求，且 R3F 回退仍可用。

### Phase 7：小镇扩展

- 广场、图书馆、宿舍和街道。
- 公共活动、跑步环线、公交站和长椅。
- 20 至 30 个常驻角色和规则型背景居民。
- 室内外 Portal 和分区加载。

## 19. 测试策略

### 19.1 后端

- Schema 和引用校验单元测试。
- 路线距离、速度和持续时间测试。
- 活动状态机参数化测试。
- 资源唯一占用和事务回滚测试。
- 相同 Seed 的确定性测试。
- 感知范围、Zone 和 Portal 边界测试。
- 偶遇、对话中断和任务恢复测试。
- API 快照与增量事件契约测试。
- PostgreSQL 集成测试覆盖资源约束和并发写入。

### 19.2 Godot Headless

通过命令行运行测试场景：

```bash
godot --headless --path godot/world-client \
  --script res://tests/run_tests.gd
```

覆盖：

- 协议解码和版本拒绝；
- 重复/乱序消息；
- Snapshot Spawn/Despawn；
- 活动到动画状态映射；
- 暂停与恢复；
- 路径采样和位置收敛；
- 资源缺失时的安全占位表现；
- 场景释放后无残留节点。

若后续引入第三方 Godot 测试插件，必须固定版本并通过单独 ADR 决定。

### 19.3 Contract Test

同一批 JSON Fixture 必须被以下三方验证：

- Python Pydantic；
- TypeScript runtime validator；
- Godot `ProtocolCodec`。

协议 Fixture 放在单一目录，不能复制三份后分别维护。

### 19.4 浏览器端到端

- Godot Web 成功加载并发送 ready。
- 快照后出现正确数量的 Agent。
- 点击 Agent 打开正确 React 详情。
- Run pause 冻结世界。
- SSE 断开、重连和快照恢复。
- 不兼容协议显示明确错误并回退。
- R3F fallback 仍可打开同一 Run。

### 19.5 视觉与性能回归

- 固定 Fixture、相机和随机 Seed 截图。
- 桌面 Chromium、Firefox 和 Safari 验证。
- 至少一台目标移动设备验证。
- 连续运行 30 分钟，记录内存增长和断流恢复。

## 20. CI 与构建

建议新增命令：

```text
make godot-test
make godot-export-map
make godot-export-web
make godot-check
```

CI 顺序：

1. 安装固定 Godot Standard 和 Export Templates；
2. Headless 导入资产；
3. 运行地图导出；
4. 检查导出物无 Diff；
5. 运行 Godot Headless 测试；
6. 导出 Web 构建；
7. 将产物复制到 `frontend/public/godot-world/<build_id>/`；
8. 运行 Next.js 类型、Jest、Build 和浏览器冒烟测试。

Godot Web 构建属于生成产物，默认不直接提交大体积 `.wasm` 和 `.pck`；由 CI 构建或制品仓库分发。
如果部署平台必须提交静态产物，需要在 ADR 中记录原因和更新流程。

## 21. 性能预算

以下是进入正式替换阶段的建议门槛，不是当前已达到指标：

| 指标 | 桌面目标 | 移动端目标 |
|------|----------|------------|
| 首次可交互 | ≤ 5 秒 | ≤ 10 秒 |
| 20 Agent 稳态帧率 | 60 FPS 附近 | ≥ 30 FPS |
| 50 Agent 稳态帧率 | ≥ 45 FPS | ≥ 24 FPS |
| 连续 30 分钟内存增长 | ≤ 10% | ≤ 15% |
| 快照到画面校准 | ≤ 500 ms | ≤ 1 s |
| 事件到视觉反馈 | ≤ 1.5 s | ≤ 2 s |
| 完整快照压缩前大小 | ≤ 1 MB | ≤ 1 MB |

优化顺序：

1. 批量 Bridge 消息；
2. Agent LOD 与不可见动画降频；
3. MultiMesh/实例化静态对象；
4. 合并材质和纹理图集；
5. 分区加载室内场景；
6. 降低阴影、粒子和灯光数量；
7. 最后才评估多线程 Web 导出。

禁止每帧向 React 发送 Agent Transform。

## 22. Web、安全与可访问性

### 22.1 Web

- 使用 WebGL 2.0 Compatibility renderer。
- 默认单线程导出，避免强制 COOP/COEP 影响第三方集成。
- 处理标签页隐藏、上下文丢失和音频自动播放限制。
- 资产采用内容哈希路径，避免旧 HTML 加载新 PCK。
- Service Worker 更新必须保证 HTML、WASM、PCK 版本一致。

### 22.2 安全

- Godot 不接收数据库凭据、管理口令或长期访问令牌。
- `postMessage` 校验 origin、source、run_id、协议版本和体积。
- 只允许白名单消息，不执行字符串脚本。
- 地图导出器拒绝绝对路径和目录穿越资源引用。
- 外部 GLB、贴图和音频进入仓库前检查许可证与来源。

### 22.3 可访问性

Godot Canvas 不能成为唯一信息入口：

- Agent、地点和活动保留 DOM 列表；
- 所有世界控制都可通过键盘和控制台完成；
- 选中状态同步到 React 并提供可读详情；
- `prefers-reduced-motion` 切换到低动态表现；
- WebGL 不可用时提供 DOM/R3F 后备；
- 重要事件不能只通过颜色、粒子或空间声音表达。

## 23. 观测性

客户端批量上报：

```text
godot_client_load_seconds
godot_client_ready_total
godot_client_fps
godot_client_memory_bytes       # 平台允许时
godot_bridge_message_total
godot_bridge_decode_error_total
godot_snapshot_resync_total
godot_protocol_mismatch_total
godot_asset_load_error_total
godot_context_lost_total
```

日志上下文至少包含：

```text
run_id
protocol_version
map_id
map_content_hash
client_build_id
last_sequence
browser
quality_profile
```

遥测是 best-effort，失败不能影响世界推进。

## 24. 迁移与回退

### 24.1 双渲染期

Scenario UI 配置允许：

```yaml
stage:
  renderer: voxel   # voxel | godot
  fallback_renderer: voxel
  godot_build_id: world-client-2026-08-01
```

同一个 API 快照必须能驱动两个客户端。Godot 专用视觉字段放在独立 `presentation` 命名空间，不能污染
Agent 业务模型。

### 24.2 回退触发

以下情况自动或人工回退 R3F：

- WebGL/WASM 初始化失败；
- 协议主版本不兼容；
- 地图哈希与快照不匹配；
- Godot 连续崩溃或上下文丢失；
- 目标设备性能低于最低门槛；
- 宿主无法在超时内收到 ready。

回退只更换表现层，不修改 Run 状态。

### 24.3 删除旧舞台的条件

只有满足以下条件才讨论删除 R3F：

- Godot 已作为默认渲染器稳定运行至少一个发布周期；
- 浏览器和移动端矩阵通过；
- DOM 后备视图完整；
- 回放、暂停、恢复和断流经过生产验证；
- 没有仍依赖 Voxel ScenePlan 的 Scenario；
- 删除方案单独经过 ADR 和可恢复提交。

## 25. 代码量与实施量级

预计新增或重构：

| 范围 | 生产代码 | 测试/Fixture |
|------|----------|--------------|
| 后端具身模拟 | 10,000～16,000 | 7,000～11,000 |
| Godot 客户端 | 8,000～15,000 | 2,000～4,000 |
| Next.js Bridge | 1,000～2,500 | 800～1,500 |
| Scenario Schema/Loader | 2,000～3,500 | 1,500～2,500 |
| 合计 | 21,000～37,000 | 11,300～19,000 |

地图场景、GLB、纹理、动画和导出 JSON 不适合用代码行数衡量。第一阶段咖啡馆垂直切片应控制在
约 13,000 至 20,000 行代码与测试内；验证失败时停止扩展整座小镇。

### 25.1 `narrative_world` 当前落地基线

叙事小镇已经复用同一套具身执行协议，而不是另建题材专用执行器。当前完整环境边界为
`64m × 74m`，其中约 `44m × 34m` 为小镇陆地；两横两竖主路构成四街区网格，14 个 RouteNode 和
15 条 RouteEdge 与 Blender 道路使用同一组坐标。地图包含 7 个 Location、11 个
Zone、4 个室内 Portal、7 个 Interactable、12 个 InteractionSlot 和 4 个 CameraAnchor。场景 bundle
通过 `activities.yml` 提供喝咖啡、居家休息、备餐和广场小坐，通过 `object_types.yml` 把这些活动
绑定到点单柜台、座椅、沙发、厨房台和公共长椅。`world.yml` 的 perception/encounter 参数使该场景
进入现有权威偶遇管线。

Blender 中的物件只承担与槽位对齐的视觉表达；资源占用、排队、时长、活动推进仍由 FastAPI 决定。
Godot 根据世界快照把角色放到槽位位置，并在客户端侧仅增加插值、海面微动、昼夜路灯和远景剔除。
导演相机的初始构图由地图中的 `camera:town:overview` 驱动，避免场景坐标继续硬编码在相机脚本中。
Web 嵌入态以容器实际尺寸驱动 3D viewport，不锁定设计分辨率宽高比；相机支持左键环绕、
右键/`Shift + 左键`/中键平移、滚轮缩放、`WASD`/方向键地面移动、`Shift` 加速、`Home`
返回总览和 `F` 返回已选居民，并保留左键单击居民的选中语义。

## 26. 最终验收场景

```gherkin
Feature: Godot 具身世界客户端

  Scenario: 高层咖啡决策被展开为连续活动
    Given Mei 决定去 Studio Cafe 喝咖啡
    When 模拟继续推进
    Then Mei 依次完成导航、排队、点单、落座和饮用
    And LangGraph 不需要为每个低层步骤重新决策

  Scenario: 两名角色不能占用同一座位
    Given 咖啡馆只剩一个空位
    When Mei 和 Chen 同时申请该座位
    Then 只有一人的资源申请成功
    And 另一人进入等待或重新规划

  Scenario: 途中偶遇来自权威空间状态
    Given Mei 和 Chen 正在同一路段相向移动
    When 两人的权威距离进入偶遇范围
    Then 后端产生 encounter candidate
    And Agent 可以选择忽略、招呼、交谈或同行
    And Godot 不能自行创建权威偶遇

  Scenario: 页面刷新恢复进行中的活动
    Given Mei 正在座位上喝咖啡
    When 用户刷新 Godot 世界页面
    Then 客户端从完整快照恢复 Mei 的座位、活动进度和表现状态
    And 不重复写入 activity_started 事件

  Scenario: 断流后使用快照校准
    Given Godot 已应用到 sequence 100
    When 客户端收到 sequence 103
    Then 客户端停止应用增量
    And 请求完整快照
    And 从快照序号继续消费事件

  Scenario: Godot 不可用时回退
    Given 浏览器无法初始化 Godot Web
    When ready 超时
    Then Next.js 显示明确错误
    And 使用 R3F 或 DOM 后备世界
    And Run 继续由 FastAPI 正常推进
```

## 27. 不可违反的工程约束

1. FastAPI 是业务状态唯一权威来源。
2. Godot 不运行 LangGraph，也不直接写数据库。
3. Godot 客户端碰撞和距离不能生成权威社会事实。
4. 地图空间数据只有一个导出源，禁止前后端手写两套坐标。
5. 认知 Tick 与模拟时间分离，不能每秒调用 LLM。
6. 持续活动、占用和事件必须共享现有事务边界。
7. 协议必须版本化、可校验、可幂等和可快照恢复。
8. Godot Canvas 不能成为唯一信息和控制入口。
9. 先完成咖啡馆垂直切片，再扩整座小镇。
10. 在达到量化门槛前，不删除现有 R3F 回退路径。

## 28. 参考资料

- [Godot 4.7.1 下载与版本归档](https://godotengine.org/download/archive/)
- [Godot Web 导出](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html)
- [Godot Dedicated Server](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html)
- [Godot NavigationAgent3D](https://docs.godotengine.org/en/stable/classes/class_navigationagent3d.html)
- [当前系统架构](CURRENT_ARCHITECTURE.md)
- [Godot 3D 客户端技术验证](GODOT_3D_CLIENT_SPIKE.md)
- [Agent 在途状态](../product/FEATURE_AGENT_TRANSIT.md)
- [World Map V1](../product/FEATURE_WORLD_MAP_V1.md)
- [Voxel 2.5D 世界舞台](../product/FEATURE_VOXEL_2_5D_WORLD_STAGE.md)
- [导演控制平面](DIRECTOR_CONTROL_PLANE.md)
