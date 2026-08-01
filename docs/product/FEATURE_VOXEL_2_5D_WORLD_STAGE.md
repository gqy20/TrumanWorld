# Truman World 2.5D Voxel World Stage Plan

- 类型：`feature`
- 状态：`in_progress`
- 负责人：`frontend`
- 最后更新：`2026-08-01`
- 适用范围：`frontend / world page / stage renderer`

## 1. 背景

### 当前实施状态

截至 2026-08-01，渲染基础已经完成第一轮收口：

- Three.js 保留为底层引擎，并由 React Three Fiber v9 管理 Canvas、相机和事件生命周期
- voxel Canvas 使用 `next/dynamic` 在客户端按需加载，不进入世界页首屏的同步模块图
- `SceneWorld -> VoxelScenePlan` 已拆成纯函数，可独立测试
- Road Graph 已根据 plot entrance 生成确定性道路，支持中心 hub、建筑避让和四向连接元数据
- 类型化 Prefab 已覆盖 home、cafe、office、library、hospital、plaza、green 与 generic，并按入口方向旋转立面
- plaza 已从“通用房屋”改为铺装、喷泉、纪念物和长椅组成的公共空间
- 地面、道路、建筑和角色按材质与阴影属性合并为 `InstancedMesh` 批次
- 选中态独立为 selection layer，不再因选中地点或角色重建 WebGL renderer
- 正交相机根据 ScenePlan bounds 和 viewport aspect 自动取景，移动端舞台高度已单独收敛
- 桌面端已支持滚轮缩放、鼠标拖拽平移、地点/角色点击聚焦和一键重置镜头
- 聚焦与重置使用 220ms 缓动，并尊重 `prefers-reduced-motion`
- 拖拽使用移动阈值并抑制松手后的误点击；窄屏普通滚轮保留给页面滚动
- 视图切换已移入舞台浮层，桌面端支持一键聚焦舞台并用 Escape 恢复信息栏
- 应用外壳在窄屏恢复页面纵向滚动，舞台下方信息不再被 viewport 裁切
- 生产世界页不再依赖 Phaser 导出的视图切换组件，Phaser 仅作为 legacy 实现保留
- scenario UI 配置已将 renderer 从 `pixel` 收口为 `voxel`

Phase 1–3 的空间底座和 Phase 5 的相机交互已经完成。Phase 4 的展示外壳仍在逐步收敛，下一阶段优先进入事件可视化，让静态世界开始表达正在发生的故事。

当前世界页已经从 SVG 地图、Phaser 像素小镇推进到可扩展的 Three.js voxel 舞台。基础结构已经成立，剩余问题主要位于展示和叙事层：

- 右侧信息栏仍长期占据横向空间
- 舞台工具条仍在 Canvas 外部占用垂直空间
- 缺少 hover 信息和选中目标的轻量 DOM 摘要
- move、speech、talk 等事件还没有进入舞台表现层
- 材质仍以统一 Lambert 方块为主，缺少更细的表面与氛围层次

本计划定义下一阶段如何把 `VoxelWorldRenderer` 从“可运行原型”升级为“优雅、可展示、可持续扩展的 2.5D 世界舞台”。

## 2. 产品目标

目标不是做完整游戏，而是让 Truman World 的核心仿真状态能被第一眼看懂：

- 让世界主画面成为页面视觉中心
- 用 2.5D voxel 小镇表达地点、道路、角色和事件
- 保留导演控制台的信息能力，但不让面板抢走主视觉
- 用 hover、选中、镜头和轻量 overlay 解释仿真细节
- 为未来更高质量的建筑、环境和动画资产留出结构

成功效果：

> 用户打开世界页时，首先看到的是一个有空间层次的小镇舞台，而不是控制台中的一块小地图。

## 3. 非目标

本阶段明确不做：

- 不做完整 Minecraft 克隆
- 不做第一人称或自由移动玩家控制
- 不做复杂物理、战斗或采集建造玩法
- 不把业务 UI 全部搬进 WebGL
- 不让 Three.js 直接请求后端 API
- 不删除 SVG 地图或 Phaser 旧实现，除非新实现稳定后再清理

## 4. 当前问题拆解

### 4.1 构图问题

旧世界页是信息面板优先的三列布局。即使渲染器变强，舞台也容易被压成一个组件，而不是主场景。

需要继续推进：

- 舞台区域默认占据主内容宽度
- 右侧面板收敛为一列或可折叠 overlay
- 世界状态、时间线、地点详情不常驻遮挡主舞台

当前代码观察：

- `frontend/components/world-canvas.tsx` 已经开始从三列改为主舞台加右栏，但右栏仍常驻。
- voxel 舞台已区分移动端和桌面端高度，并根据实际 aspect 计算正交相机 frustum。
- `WorldViewToggle` 已移入舞台浮层；下一步应把右栏进一步收敛成按需展开的信息层。

### 4.2 空间结构问题

基础 plot 语义已经落地，location 不再直接映射到渲染坐标。

已具备：

- plot 边界
- building footprint
- entrance anchor
- road anchor
- decoration anchors
- agent anchors
- selection bounds

当前代码观察：

- `plot-layout.ts` 统一提供 size、footprint、入口、角色 anchor 和装饰 anchor。
- 角色使用 plot agent anchors，location/agent block 都携带稳定 hit target metadata。
- 标准 scenario 和同类型地点具备确定性布局；任意规模的全局 collision solver 仍属于后续能力。

### 4.3 道路问题

道路已由 plot entrance 和中心 hub 确定性生成，可随地点集合变化。

当前 Road Graph 已包含：

- 主路 spine
- plot entrance connector
- plaza hub
- road tile type
- curb / pavement details

当前代码观察：

- `road-graph.ts` 使用确定性 A* 将所有入口接入 hub，并避开 building footprint。
- road tile 已包含 main / connector / plaza role 及四向对称连接元数据。
- 当前 renderer 仍以方形 tile 表现连接；转角、路沿开口和更细的铺装图案可在美术阶段继续增强。

### 4.4 重叠问题

重叠来自三类来源：

- 地点坐标过近
- 建筑 footprint 和 agent anchor 没有统一约束
- label、bubble、trail 等解释层常驻在世界里

解决方向：

- plot 层负责空间排布
- renderer 层负责 depth/framing
- DOM overlay 层负责文字信息

### 4.5 美术质量问题

当前已经有体素方向，但视觉仍偏“示意图”。质量提升应转向 block palette 和 prefab，而不是继续临时堆 box。

需要：

- 类型化建筑 prefab
- 屋顶、窗户、门、招牌、柱体、台阶
- 树、花坛、围栏、路灯、水池
- 统一色板、光照、阴影和地面层次

当前代码观察：

- palette 已集中到 `materials.ts`，Prefab 只输出与 Three.js 无关的 block 数据。
- ScenePlan blocks 已按 material/shadow 属性合并为 `InstancedMesh`，不再为每个 block 建立 geometry/material。
- 目前主体仍统一使用 `MeshLambertMaterial`；roughness、emissive、透明水面和夜间灯光仍待扩展。

## 4.6 Current Code Inventory

当前相关文件：

```text
frontend/components/world-canvas.tsx
frontend/components/voxel-world-renderer.tsx
frontend/components/phaser/*
frontend/lib/world-scene-adapter.ts
frontend/components/town-map.tsx
```

当前数据流：

```text
WorldSnapshot
  -> buildSceneWorld(world)
  -> SceneWorld
  -> VoxelWorldRenderer(sceneWorld)
  -> Three.js scene
```

当前交互流：

```text
Three.js raycast
  -> object.userData.kind/id
  -> onLocationClick / onAgentClick
  -> world-canvas query state
  -> LocationDetailModal / AgentDetailModal
```

这个数据流是正确的，应当保留。问题主要在 `SceneWorld -> Three.js scene` 中间缺少 scene planning 层。

## 5. 目标架构

### 5.1 React 负责

- 获取和轮询 `WorldSnapshot`
- 生成 `SceneWorld`
- 持有选中态、弹窗、右侧信息面板
- 向 voxel renderer 传入只读 scene DTO
- 接收 renderer 点击事件

### 5.2 Voxel Renderer 负责

- Three.js scene/camera/lighting 生命周期
- 根据 scene DTO 构建 2.5D voxel world
- 根据 selection 更新高亮
- 提供 location/agent hit testing
- 不直接依赖后端 API

### 5.3 Scene Planning 层负责

建议新增独立模块，例如：

```text
frontend/components/voxel/
  scene-plan.ts
  plot-layout.ts
  road-graph.ts
  prefabs.ts
  materials.ts
  VoxelWorldRenderer.tsx
```

职责：

- `plot-layout.ts`：把 locations 分配到 plot
- `road-graph.ts`：根据 plot entrance 生成道路
- `prefabs.ts`：根据 location type 生成建筑/环境 prefab
- `materials.ts`：统一颜色、材质和光照参数
- `scene-plan.ts`：输出 renderer 可消费的 plan

### 5.4 Renderer 分层

建议渲染器内部按层组织：

```text
WorldRoot
  GroundLayer
  RoadLayer
  PlotLayer
  BuildingLayer
  PropLayer
  AgentLayer
  SelectionLayer
```

原则：

- 地面和道路优先可批量/实例化
- 建筑和道具可以先用 prefab group
- agent 保持独立对象，便于动画
- selection ring、hover outline 与主体 mesh 分开
- 文字、气泡、详情提示优先 DOM overlay，不放入 3D 世界

### 5.5 DOM Overlay 分层

建议在 renderer 容器中增加 overlay root：

```text
<div className="voxel-stage">
  <canvas />
  <div className="voxel-stage-overlay">
    hover card
    event bubble
    controls
  </div>
</div>
```

overlay 内容：

- hover location card
- selected location mini status
- speech/talk bubble
- camera controls
- renderer debug toggle

避免：

- 常驻地点名称
- 常驻 agent 名称
- 长文本气泡堆叠在世界里

## 6. 数据模型

### 6.1 Plot

```ts
type VoxelPlot = {
  id: string;
  locationId: string;
  type: string;
  center: { x: number; z: number };
  size: { width: number; depth: number };
  footprint: { width: number; depth: number };
  entrance: { x: number; z: number };
  agentAnchors: Array<{ x: number; z: number }>;
  decorationAnchors: Array<{ x: number; z: number; kind: string }>;
};
```

补充字段：

```ts
type VoxelPlot = {
  elevation: number;
  district: "home" | "commerce" | "civic" | "green" | "center";
  entranceDirection: "north" | "east" | "south" | "west";
  clickableBounds: {
    center: { x: number; y: number; z: number };
    size: { width: number; height: number; depth: number };
  };
};
```

约束：

- `center` 使用世界网格坐标，不使用屏幕坐标
- `footprint` 必须小于等于 `size`
- `entrance` 必须在 plot 边缘或边缘外一格
- `agentAnchors` 不应落入 building footprint
- `decorationAnchors` 不应落入 road graph

### 6.2 Road Graph

```ts
type VoxelRoadTile = {
  x: number;
  z: number;
  connections: {
    north: boolean;
    east: boolean;
    south: boolean;
    west: boolean;
  };
  role: "main" | "connector" | "plaza";
};
```

生成规则：

- 所有 plot entrance 必须可达中心 plaza
- connector 优先走曼哈顿路径
- pathfinding 避开 occupied footprint
- 若 connector 与主路重叠，合并为同一个 tile
- road role 影响材质和高度

### 6.3 Prefab

```ts
type VoxelPrefab = {
  id: string;
  blocks: VoxelBlock[];
  hitTarget: "location" | "agent" | "none";
};

type VoxelBlock = {
  position: { x: number; y: number; z: number };
  size: { width: number; height: number; depth: number };
  material: string;
  castShadow?: boolean;
  receiveShadow?: boolean;
};
```

建议补充：

```ts
type VoxelHitTarget = {
  kind: "location" | "agent" | "event";
  id: string;
};

type VoxelScenePlan = {
  bounds: {
    minX: number;
    maxX: number;
    minZ: number;
    maxZ: number;
  };
  plots: VoxelPlot[];
  roads: VoxelRoadTile[];
  prefabs: VoxelPrefab[];
  agents: VoxelPrefab[];
};
```

`VoxelWorldRenderer` 只负责把 `VoxelScenePlan` 渲染出来。这样 scene planning 能用纯函数测试。

## 6.4 Coordinate System

建议统一坐标约定：

- `x`：左右方向，向右为正
- `z`：前后方向，向屏幕后方为负或正需固定
- `y`：高度
- 一个 ground tile = `1 x 1`
- 角色高度约 `0.8`
- 普通建筑占地约 `1.4 x 1.4`
- 大建筑占地约 `2 x 2`
- plot 建议至少 `2.5 x 2.5`

相机：

- 使用 orthographic camera
- 默认角度：`position = (8, 7, 8)`，`lookAt = (0, 0, 0)`
- 根据 scene bounds 自动调整 zoom/frustum

## 6.5 Material System

建议 material key：

```ts
type VoxelMaterialKey =
  | "grass"
  | "grassAlt"
  | "road"
  | "curb"
  | "plot"
  | "wallWarm"
  | "wallCool"
  | "wallStone"
  | "roofRed"
  | "roofBlue"
  | "roofGreen"
  | "glass"
  | "wood"
  | "leaf"
  | "highlight";
```

材质策略：

- 第一阶段继续 `MeshLambertMaterial`
- 同色材质复用，不要每个 block 创建新 material
- 高频 block 可共用 `BoxGeometry`
- 后续可按 material key 做 instanced mesh

## 7. Implementation Phases

### Phase 1: Plot / Parcel System

状态：`complete`

目标：解决重叠和空间语义。

任务：

- 新增 `plot-layout.ts`
- 每个 location 分配一个 plot
- 每个 plot 定义 building footprint、entrance、agent anchors
- renderer 不再直接用 location slot 放建筑
- agent 站位改用 plot agent anchors

验收：

- 地点之间不互相压叠
- 角色默认站在入口附近
- 每个地点有明确地块边界
- 点击区域和建筑绑定稳定

详细任务：

1. 建立 `frontend/components/voxel/` 目录。
2. 将 `frontend/components/voxel-world-renderer.tsx` 迁移为 `voxel/VoxelWorldRenderer.tsx`。
3. 新增 `plot-layout.ts`。
4. 将当前 `LOCATION_SLOTS` 迁入 `plot-layout.ts`，并升级为 plot definitions。
5. 为每个 plot 生成：
   - center
   - size
   - footprint
   - entrance
   - agent anchors
   - decoration anchors
6. `buildAgents` 改为使用 plot agent anchors。
7. `buildLocations` 改为使用 plot prefab placement。
8. 为 duplicate location 实现全局 collision check。

建议测试：

- same input produces same plots
- every location gets exactly one plot
- duplicate locations do not share identical centers
- agent anchors are outside building footprint
- plot bounds do not overlap for standard scenario

### Phase 2: Road Graph

状态：`complete`

目标：让道路服务空间结构，而不是静态装饰。

任务：

- 新增 `road-graph.ts`
- 根据 plot entrance 生成 connector
- 中心 plaza 作为主路 hub
- road tile 根据连接关系生成边缘/转角/交叉
- 道路 mesh 与地块 mesh 分层

验收：

- 每个地点入口连到道路
- 道路不穿过建筑 footprint
- 主路、支路、广场视觉上可区分

详细任务：

1. 新增 `road-graph.ts`。
2. 输入 `VoxelPlot[]`，输出 `VoxelRoadTile[]`。
3. 固定中心 plaza/hub。
4. 每个 plot entrance 用 Manhattan path 连接到 hub。
5. 使用 `Set<string>` 合并重复 road tiles。
6. 根据邻接关系生成 connections。
7. renderer 根据 connections 决定 road block、curb、corner detail。

建议测试：

- every plot entrance is connected
- no road tile sits inside building footprint
- road connections are symmetrical
- road graph is deterministic

### Phase 3: Voxel Prefab Library

状态：`complete`

目标：从“方块堆”变成类型化建筑。

任务：

- 新增 `prefabs.ts`
- 为 `home/cafe/office/library/plaza/park` 定义 prefab
- 每类建筑有独立 silhouette
- 增加 roof、door、window、sign、stairs、fence 等子组件
- park 使用树、花坛、长椅、水池，而不是建筑

验收：

- 不看文字也能区分地点类型
- 建筑有清晰前后左右和高度层次
- 缩小时仍能读出主要形状

详细任务：

1. 新增 `prefabs.ts`。
2. 定义 `createHomePrefab`、`createCafePrefab`、`createOfficePrefab`、`createLibraryPrefab`、`createParkPrefab`。
3. prefab 只输出 block 数据，不直接创建 Three mesh。
4. renderer 统一将 block 转为 mesh。
5. 建筑类型差异必须体现在 silhouette，而不只是颜色。

Prefab 质量标准：

- home：低矮、红/绿屋顶、烟囱
- cafe：遮阳棚、招牌、外摆桌椅
- office：高一点，多层窗户，平屋顶
- library：柱子、台阶、石材色
- park：树、长椅、花坛、小路
- plaza：中心广场、水池或雕塑

### Phase 4: Presentation Shell

状态：`in_progress`

已完成第一步：舞台工具从 Canvas 外部移入 overlay，桌面端信息栏可折叠，窄屏保留纵向信息流，并针对 3D / SVG 两种视图处理控制层避让。

目标：让世界成为页面主屏。

任务：

- 右侧信息面板支持折叠
- 默认舞台占据更大 viewport
- 选中地点时右侧面板更新，而不是世界里常驻文字
- hover 信息用 DOM overlay 展示
- 支持一键 theater mode / focus mode

验收：

- 主舞台默认占据页面主要视觉区域
- 没有蓝色控制台背景
- 文字信息不遮挡小镇

详细任务：

1. 世界页提供 compact/full stage mode。
2. 右侧栏在窄屏默认折叠。
3. 舞台右上角提供切换按钮和 debug 控制。
4. DOM overlay 使用 screen projection 定位 hover card。
5. 移除所有常驻世界内 label。

### Phase 5: Camera / Interaction

状态：`complete`

当前实现位于 `camera-controller.ts` 和 `voxel-canvas.tsx`：相机数学保持为可测试纯函数，Three.js 生命周期和原生指针事件由 CameraRig 管理。

目标：提高可观看性和可控性。

任务：

- 默认相机 framing 根据 world bounds 计算
- 支持滚轮 zoom
- 支持拖拽 pan
- 点击 location 时平滑聚焦
- 点击 agent 时聚焦到 agent anchor
- selection ring / hover outline 使用 3D mesh 或 DOM overlay

验收：

- 不同地点数量下主体都居中
- 选中目标时镜头反馈自然
- 鼠标操作不会打断页面滚动体验

详细任务：

1. 新增 `camera-controller.ts`。
2. 沿用 React Three Fiber 的实例 raycast hit testing。
3. 新增 camera controller：
   - wheel zoom
   - pointer drag pan
   - focus selected target
   - reset camera
4. 根据 `VoxelScenePlan.bounds` 计算初始 orthographic frustum。
5. 支持 reduced motion，禁用或缩短动画。

### Phase 6: Event Visualization

目标：把仿真事件变成可观察的舞台变化。

任务：

- speech/talk 事件变成短暂 DOM bubble
- move 事件变成 3D route highlight
- heat 影响地点灯光或地块色温
- warning/拒绝动作等高优事件可短暂 pulse

验收：

- 用户不用打开时间线也能看到“哪里正在发生事”
- 事件视觉不长期遮挡场景
- 事件层可关闭或降噪

详细任务：

1. `SceneBubble` 投影到 agent anchor 或 location entrance。
2. speech/talk bubble 作为 DOM overlay，而不是 3D text。
3. move trail 使用 road graph 上的高亮 tile 或 line。
4. location heat 映射到 plot glow/emissive 或 selection pulse。
5. 事件层可根据 recency 自动淡出。

## 7.7 Phase 7: Performance and Cleanup

目标：让实现可长期维护。

任务：

- 复用 material 和 geometry
- 将 ground/road 大量 block 改为 instanced mesh
- memoize scene plan
- renderer 只在 sceneWorld/selection 改变时重建必要层
- Phaser 旧实现标记为 legacy 或后续删除

验收：

- 标准 demo world 保持稳定交互
- renderer unmount 无 WebGL context 泄漏
- 多次切换 SVG/Voxel 不残留 canvas

## 8. File-Level Plan

建议新增：

```text
frontend/components/voxel/
  VoxelWorldRenderer.tsx
  scene-plan.ts
  plot-layout.ts
  road-graph.ts
  prefabs.ts
  materials.ts
  interaction.ts
```

建议迁移：

```text
frontend/components/voxel-world-renderer.tsx
```

迁移为：

```text
frontend/components/voxel/VoxelWorldRenderer.tsx
```

保留：

- `frontend/components/phaser/*` 暂不删除，用作旧实现和测试参考
- `frontend/components/town-map.tsx` 继续作为 SVG fallback

建议最终结构：

```text
frontend/components/voxel/
  VoxelWorldRenderer.tsx
  __tests__/
    plot-layout.test.ts
    road-graph.test.ts
    prefabs.test.ts
    scene-plan.test.ts
  camera-controller.ts
  geometry.ts
  interaction.ts
  materials.ts
  plot-layout.ts
  prefabs.ts
  road-graph.ts
  scene-plan.ts
  types.ts
```

`types.ts` 放所有 voxel 内部类型，避免每个模块重复定义。

## 8.1 Public Component API

`VoxelWorldRenderer` 保持小 API：

```ts
type VoxelWorldRendererProps = {
  sceneWorld: SceneWorld;
  highlightedLocationId?: string | null;
  highlightedAgentId?: string | null;
  cameraFocusRequest?: VoxelCameraFocusRequest | null;
  onLocationClick?: (locationId: string) => void;
  onAgentClick?: (agentId: string) => void;
};
```

不要把 renderer 内部 camera、material、debug 状态暴露给页面。若需要 debug，可用内部 query/local state。

## 8.2 Scene Plan API

```ts
function buildVoxelScenePlan(sceneWorld: SceneWorld): VoxelScenePlan;
```

输入只有 `SceneWorld`。不要输入 React state、DOM size 或 Three.js 对象。

好处：

- 易测
- 可缓存
- 可在 Storybook 或离线脚本里预览

## 9. Testing Plan

### Unit Tests

- plot layout deterministic
- duplicate location spreading
- road graph connects every entrance
- prefab block count and hit target metadata
- material palette returns stable values

### Component Tests

- world page renders voxel stage by default
- location click opens location modal
- agent click opens agent modal
- switching to SVG map still works

### Visual Verification

至少检查：

- desktop 1280x720
- desktop 1440x900
- narrow layout 390x844

验收重点：

- 主体不空
- 主体居中
- 无明显蓝色背景残留
- 建筑不互相压叠
- 文字不遮挡主场景

### Regression Tests

需要防止以下回归：

- 新 location type 导致 renderer crash
- 空世界导致 blank/exception
- duplicate location 全部堆叠
- SVG fallback 切换失效
- click target 指向错误 id
- unmount 后仍有 canvas 或事件监听残留

### Manual QA Script

1. 打开 world page。
2. 确认默认是 voxel stage。
3. 点击一个建筑，确认 location modal 打开。
4. 点击一个角色，确认 agent modal 打开。
5. 切换到 SVG map，再切回 voxel stage。
6. 在桌面端验证滚轮缩放、拖拽平移和重置镜头，确认拖拽不会误开地点弹窗。
7. 改变窗口宽度，确认 stage 不空、不拉伸。
8. 在 390x844 下从舞台区域滚动，确认页面能进入健康面板和地点列表。
9. 检查右侧面板不遮挡主场景。

## 10. Risk / Tradeoffs

### Risk: Three.js 复杂度上升

缓解：

- renderer 只消费 `SceneWorld`
- 业务状态仍在 React
- voxel scene planning 拆成纯函数测试

### Risk: 性能问题

缓解：

- 第一阶段世界规模小，可用普通 mesh
- 后续道路/地面可改 instanced mesh
- prefab 生成结果可 memoize

### Risk: 美术仍不够好

缓解：

- 先定 block palette 和 prefab 规则
- 避免临时手写每个建筑
- 后续可接外部 block asset 或生成式资产流程

### Risk: Renderer 和 React 状态耦合

缓解：

- React 只传 DTO 和 callbacks
- renderer 内部不读取 URL/search params
- scene planning 保持纯函数

### Risk: 页面布局变化影响控制台效率

缓解：

- 保留右侧信息栏
- 提供 compact/full stage toggle
- 不移除现有弹窗入口

### Risk: Mobile / Narrow Layout

缓解：

- 窄屏默认单列
- 右侧面板下移或折叠
- camera 初始 framing 按容器 aspect 计算

## 11. Milestones

### M1: Spatial Foundation

- Plot system
- Road graph
- Agent anchors
- No major overlap

### M2: Visual Identity

- Typed building prefabs
- Environment props
- Better lighting and shadows
- Main stage framing

### M3: Interaction Quality

- Hover overlay
- Selection focus
- Camera zoom/pan
- Event bubbles and route highlights

### M4: Production Readiness

- Renderer module split
- Tests for scene planning
- Performance pass
- Remove or demote old Phaser path if no longer needed

## 11.1 Suggested Work Breakdown

### PR 1: Extract Voxel Modules

- Move renderer into `components/voxel/`
- Add `types.ts`
- Add `materials.ts`
- No visual behavior change

### PR 2: Plot Layout

- Add `plot-layout.ts`
- Use plot output in renderer
- Add unit tests

### PR 3: Road Graph

- Add `road-graph.ts`
- Generate roads from plot entrances
- Add unit tests

### PR 4: Prefabs

- Add `prefabs.ts`
- Replace inline `buildBuilding` with prefab system
- Add unit tests for block output

### PR 5: Overlay and Camera

- Add hover card
- Add camera focus/zoom/pan
- Add interaction tests where practical

### PR 6: Event Visualization

- Add speech/talk bubble overlay
- Add move route highlight
- Add heat pulse

## 11.2 Engineering Acceptance Checklist

- `pnpm jest --runInBand components/voxel app/__tests__/world-page.test.tsx`
- `pnpm lint:types`
- `pnpm lint:eslint`
- no new package-lock
- no generated files outside intended asset/runtime outputs
- no direct backend fetch in renderer
- no direct DOM reads outside renderer lifecycle/effects
- renderer dispose cleans up WebGL renderer and event listeners

## 11.3 Product Acceptance Checklist

- World stage is first visual focus.
- No blue console frame around the world.
- Buildings do not heavily overlap in default demo data.
- Roads visibly connect major places.
- A non-technical viewer can distinguish home/cafe/office/library/park.
- Text labels do not permanently cover the world.
- Clicking a place or person still opens existing details.

## 12. Recommended Next Task

下一步建议直接做：

> Phase 4: Presentation Shell

原因：

- Road Graph 与 Prefab 已让场景本身具备稳定空间结构和类型辨识度
- 当前最大体验瓶颈已经从“场景不像一个世界”转为“页面仍像带 3D 组件的控制台”
- 先收敛舞台与右栏关系，后续镜头聚焦、hover card 和事件动画才有正确的信息层级

建议实现顺序：

1. 将视图切换、重置镜头和 focus mode 控件移入舞台右上角 overlay。
2. 桌面端让右栏支持 compact / collapsed，focus mode 让舞台占满主内容区。
3. 窄屏保持信息卡纵向排列，但避免为舞台保留桌面高度。
4. 选中地点时只更新右栏或轻量 DOM overlay，不在 WebGL 中常驻文字。
5. 为布局模式、键盘可达性和移动端尺寸补充组件测试与真实浏览器截图验收。

这一步完成后，世界页才会从“控制台中的 3D 组件”真正转变为“以世界舞台为主、控制信息为辅”的产品界面。
