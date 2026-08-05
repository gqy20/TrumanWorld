# Blender 与 MMX 资产管线

BPY 的代码风格、上下文边界、静态 GLB 导出契约和验证清单见
[BPY_AUTHORING_GUIDE.md](BPY_AUTHORING_GUIDE.md)。

- 状态：第一阶段已实现
- Blender：正式版 `5.2.x`
- Godot：`4.7.1`
- 三维交换格式：glTF 2.0 Binary（`.glb`）
- 二维生成：MMX CLI `image-01`
- 确定性人物贴图：YAML 驱动的透明 SVG

## 1. 所有权边界

Blender 和 `bpy` 负责建筑、家具、道具、碰撞代理、材质槽和 GLB 导出。MMX 负责人物贴图、
头像、招牌和装饰图案。Godot 负责三维放置、`AnimatedSprite3D`、交互、动作状态和最终灯光。

后端语义地图继续拥有 Location、Zone、Portal、Route、InteractionSlot 和稳定 ID。视觉资产不能
反向成为模拟事实来源。

## 2. 提示词管理

提示词不允许散落在 shell、Python 或 Godot 脚本中：

- `art/prompts/style.yml`：全局美术语言、负面约束和任务模板；
- `art/prompts/characters.yml`：角色身份、参考图和调色板；
- `art/pipeline.yml`：任务变量、固定 seed、尺寸、工具版本和输出位置；
- `art/generated/receipts/`：本地生成记录，包含完整解析提示词和 SHA-256，不提交仓库。

生成器按 `全局风格 + 任务模板 + 角色身份 + 负面约束` 组合最终提示词。更改任一层都会改变
`prompt_sha256`，便于审阅和复现。

每个任务默认并行执行三次独立的 `--n 1` 请求，而不是在同一请求中使用 `--n 3`。候选 seed
按照 `seed + candidate_index * seed_stride` 派生，输出前缀固定为
`<job>_candidate_01..03`。这样既保留可复现性，也避免同一批次候选只有编码细节不同。
每个候选发生瞬时服务错误时会独立重试；即使最终仍有候选失败，管线也会先写入完整 receipt，保留
其他候选的结果和逐次错误，再以非零状态退出。

角色任务通过 `art/pipeline.yml` 引用背景契约。契约中的 `requested_rgb` 会同时进入最终提示词和
生成 receipt；生成完成后，管线从图像边框检测实际背景中位色、与请求色的 RGB 距离和边框颜色
95 分位离散度。receipt 会同时保存 `requested_rgb`、`detected_rgb`、`color_matches`、
`uniform` 和最终 `pass/reject`。MMX 输出通常为 JPEG，因此颜色使用容差判断，不假设像素值完全
相等。被拒绝的候选不能直接进入自动抠图和 Godot 发布流程。

## 3. SVG 角色管线

SVG 与 MMX 是并行方案，不替代或删除 MMX。公共文件 `art/svg_pose_sets.yml` 管理画布、描边、
16 个标准动作，以及 `idle / walk / jog` 的多帧动画。每个场景通过
`scenarios/<scenario>/visuals.yml` 选择样式和动作集，每个人物则在同一 Bundle 的
`agents/<id>/appearance.yml` 管理发型、配饰与调色板。这样动作协议可以复用，而人物身份和场景
一起演进。生成器只使用透明背景、平面色块和稳定几何，不依赖模型采样，因此同一配置逐字节可复现。

```bash
make assets-svg-generate
make assets-svg-check
# 只更新一个人物；该操作不会覆盖场景总清单
make assets-svg-generate SVG_SCENARIO=narrative_world SVG_CHARACTER=truman
```

生成结果进入
`godot/world-client/assets/scenarios/<scenario>/characters/<id>/vector/`，属于可提交的正式运行时资产。
`assets-svg-check` 不写文件，只验证已提交 SVG 和 manifest 是否与 YAML 完全一致，适合加入 CI。
每个 SVG 角色必须提供 16 种状态：`idle / walk / jog / queue / sit / drink / talk /
use_object / wave / think / read / phone / carry / celebrate / surprised / sleep`。Godot 优先将它们
显示为面向镜头的 `Sprite3D`，后端快照用 `<scenario>/<agent-config-id>` 格式的
`visual_asset_id` 将运行时 Agent 与视觉身份解耦。根目录的 16 个 SVG 是单帧兼容姿态；动画帧位于
`idle/`、`walk/`、`jog/` 子目录，并由同目录 `manifest.json` 的 `animations` 显式声明。

`idle` 使用低频时间驱动；`walk` 和 `jog` 使用行走距离驱动。Godot 根据角色沿路线累计的米数选择
步态帧，所以暂停不滑步、速度变化不打乱节奏，快照刷新频率也不影响动画速度。动作切换使用
140ms 双 Sprite 淡入淡出，同一动作内部直接换帧以免出现残影。SVG 由 Godot 导入为纹理并随 Web
导出打入资源包，不会在运行中逐帧请求源文件。manifest 或动画帧无效时回退到对应单帧姿态；整个
SVG 角色缺失时继续使用程序化三维居民。

新增或调整步态时，只修改 `art/svg_pose_sets.yml`：

- `driver: time` 必须提供 `fps`；适合呼吸、眨眼等非位移动画。
- `driver: distance` 必须提供 `cycle_distance_m`；适合走、跑等接触地面的动作。
- 每帧完整声明身体偏移和四肢角度，表情与道具继承对应标准姿态，避免身份细节跨帧漂移。

运行 `make assets-svg-generate` 后必须执行 `make assets-svg-check` 与 `make godot-test`。前者保证所有
角色、帧和 manifest 可逐字节复现，后者会验证资源可导入以及时间/距离两类取帧逻辑。

角色参考图只约束身份和服装，不直接充当最终贴图。MMX 的输出一律先进入候选区；二维风格、肢体、
身份连续性通过人工验收后，才允许由确定性处理器发布到 Godot 资产目录。生成失败或意外变成 3D
玩偶风格时，不应通过后处理掩盖问题，而应调整版本化提示词并重新生成。

## 4. 常用命令

```bash
make assets-validate
make assets-plan
make assets-mmx-dry-run MMX_JOB=mei_idle_front
make assets-mmx-generate MMX_JOB=mei_idle_front
```

MMX 必须使用 `--non-interactive --quiet --output json`。调用命令中不得出现 API Key，凭据只由
MMX 自己的配置读取。dry-run 可能回显参考图的 Base64，管线会在写日志和终端输出前将其替换为
字符数与 SHA-256 摘要。

处理选中的单帧源图：

```bash
make assets-process-sprite \
  SPRITE_SOURCE=art/generated/raw/mei_idle_front.png \
  SPRITE_OUTPUT=godot/world-client/assets/characters/mei/idle_front.png
```

处理器会从四角估算纯色背景，只删除与画布边界连通的背景区域，裁切可见内容，对齐脚底，使用
无振铃的 BOX 缩放到 `64×96`，并仅使用前景像素建立 24 色调色板。透明像素下方会向外扩展人物
边缘颜色，避免 Godot 纹理过滤产生洋红或黑色描边。MMX 最低生成尺寸较大，因此像素化必须是
确定性的后处理步骤。

项目固定使用官方 Blender `5.2.0 LTS` Linux x64 构建。安装器会下载到被 Git 忽略的 `.tools/`，
校验官方 SHA-256，并建立稳定入口 `.tools/blender/blender`：

角色三维资产使用独立于静态建筑的 animated export profile。叙事世界六位居民均已进入该链路：

```bash
make assets-blender-character
# 后续角色可显式选择场景与身份
make assets-blender-character CHARACTER_SCENARIO=narrative_world CHARACTER_ID=truman
# 批量构建场景中所有启用 model_3d 的居民
make assets-blender-characters CHARACTER_SCENARIO=narrative_world
# 重建后渲染指定动作帧，用于检查蒙皮和肢体姿态
make assets-blender-character-preview CHARACTER_ANIMATION=walk CHARACTER_FRAME=7
```

`appearance.yml` 的 `model_3d.builder` 决定角色是否进入 3D 构建链路；发型、配饰和调色板继续复用
同一个 appearance 配置，不维护第二份 Blender 专用身份数据。构建结果包括可编辑 `.blend`、运行时
`character.glb` 和 `manifest.json`。Godot 优先加载 GLB，按实际移动距离定位 walk/jog 时间轴，并在
静止转向时播放左右转身、交谈时约束头部注视、坐下时平滑修正模型高度、喝咖啡时显示随右手
蒙皮的杯子。walk/jog 的轻微身体起伏仍按累计路程驱动，celebrate 的跳跃仅是客户端表现偏移，均不
修改后端权威坐标。模型、骨骼或动画加载失败时自动回退到同一身份的 SVG 多帧角色。

```bash
make assets-blender-install
make assets-blender-cafe
make assets-blender-campus
make assets-blender-town
# 重建小镇并渲染四个固定验收视角到 art/generated/
make assets-blender-town-previews
# 同时重建当前全部 Blender 场景
make assets-blender-all
```

脚本会拒绝非 `5.2.x` 版本，并生成：

- `art/blender/characters/narrative_world/*.blend`：六位居民的统一骨骼角色源文件；
- `godot/world-client/assets/scenarios/narrative_world/characters/*/model/character.glb`：
  携带 14 骨骼 skin、18 组动作和角色身份外观的运行时模型；
- `art/blender/scenarios/campus_world/studio_cafe.blend`：可编辑源文件；
- `godot/world-client/assets/scenarios/campus_world/locations/studio_cafe/studio_cafe.glb`：运行时资产；
- `art/blender/scenarios/campus_world/campus_landmarks.blend`：校园公共地标源文件；
- `godot/world-client/assets/scenarios/campus_world/environment/campus_landmarks.glb`：广场、宿舍、
  教学楼与图书馆的统一运行时资产；
- `art/blender/scenarios/narrative_world/seaside_town.blend`：楚门海滨小镇源文件；
- `godot/world-client/assets/scenarios/narrative_world/environment/seaside_town.glb`：楚门小镇运行时资产；
- 同目录 `.asset.json`：版本和网格统计。

BPY 源文件严格使用 Blender 原生 Z-up、米制单位；glTF 导出器负责转换为 Godot 使用的 Y-up。
Studio Cafe 是面向导演相机的切面建筑，包含门窗、遮阳棚、吧台、咖啡机、糕点展柜、菜单、桌椅、
货架、杯具、糕点、植物、吊灯和三维店招。透明玻璃、墙面线脚与小型陈设提供近景层次，同时模型
维持低多边形预算。Godot 优先实例化 GLB；资源缺失或加载失败时仍由程序化场景提供 fallback。

校园地标资产以现有语义地图原点建模，Blender 坐标会显式映射到 Godot 的 `quad / dorm /
lecture-hall / library` 位置。模型只负责可视层，语义地图继续拥有路线、Zone、容量与稳定 ID。
四个地点分别使用喷泉广场、双床宿舍、阶梯讲堂和玻璃阅读室的空间语法，避免仅靠墙体换色区分地点。
近景道具同样保持地点特异性：广场包含水柱、铺装和植物簇；宿舍包含床品、书桌、座椅、台灯与
个人书架；讲堂包含阶梯座席、声学板、板书、讲台、麦克风和投影机；图书馆包含独立书脊、阅读灯、
地毯与桌椅。

环境资产覆盖语义地图完整的 `25.5m × 17.5m` 可视范围，而不是只包围主要地点。外围由南侧道路与
人行道、入口校门、主步道网络、四座非交互背景建筑、校园边界、树带和路灯构成。背景建筑仅提供
空间围合和远景层次，不会注册为 `WorldLocation3D`，因此不会进入智能体路径规划。Godot 加载完整
Blender 环境后不再叠加程序化树木和路灯，资源缺失时仍恢复程序化 fallback。当前统一资产约 3.8 万
面，细节仍由可复现的 BPY 低模基元构成。树木、路灯、背景窗户、步道和边界等不可交互重复物件会
在导出前按环境角色合并，避免以数百个独立 MeshInstance 增加 Web draw call。

`narrative_world` 使用完全独立的海滨小镇资产，不复用校园模型。首版覆盖钟塔广场、楚门住宅、
镇中公寓、街角咖啡馆、港湾商场、港务办公室、海湾医院、外围粉彩住宅、林荫道路、海滨步道、
海面和远端摄影棚边界。模型以 `narrative-world-v1` 的语义坐标直接建模；Godot 只有在当前
`scenario_id` 为 `narrative_world` 时才会加载该 GLB，并停止叠加程序化道路与环境装饰。
当前展示版的陆地区域约为 `44m × 34m`，包含贯穿小镇的 Bay Avenue、Market Street 两条横路与
Lancaster Avenue、Seahaven Avenue 两条纵路，另有沿海的 Ocean Boulevard；包含海面的完整环境
边界为 `64m × 74m`。七个权威地点均迁移到临街地块，路线图使用 14 个节点、15 条边沿道路连接，
避免角色穿过草地或建筑。楚门住宅和街角咖啡馆采用面向导演相机的玩偶屋剖切结构；住宅
包含电视、地毯、厨房电器、餐桌、照片、隐藏摄像头、自行车和邮箱，咖啡馆包含咖啡机、收银机、
菜单、货架、报刊亭和两个权威座位。街道增加公交站、车辆、消防栓、花盆和自行车，海滨增加
望远镜与救生圈；海岸由连续海面、沙滩、海堤、全宽步道、伸入海面的木码头和三艘船组成，远端
摄影棚边界保留维修门、警告牌和监控设备。公共建筑增加立柱、屋顶设备、医院急诊雨棚、商场
入口塔和港务信号桅杆。外围填充扩展为 19 栋住宅和 6 栋商铺/公共背景建筑，只承担街区围合与
视差，不注册为智能体地点。

模型内的可交互物件通过 glTF extras 保留语义 ID，并与地图中的 InteractionSlot 对齐。模型保存前
执行无效几何、材质索引和非有限 Transform 校验；当前语义合批后为 166 个 Mesh 节点、约 14.1 万
顶点、25.2 万三角形。

行为和空间不由 Blender 文件反向推断：`activities.yml` 管活动步骤与时长，`object_types.yml` 管
affordance 和执行器，`narrative_world.tscn` 管 Zone、Portal、对象及槽位的准确位置，GLB 只负责视觉。
Godot 运行时为海面添加微动、为路灯注入受昼夜系统控制的 OmniLight3D，并对远景边界、树带和小型
街具设置可见距离。`make assets-blender-town-previews` 固定渲染全镇、钟塔广场、楚门住宅和咖啡馆
四个视角，输出属于可丢弃的 `art/generated/`，用于模型修改前后的截图对比。

## 5. 提交规则

`art/generated/` 是候选素材区，也是可丢弃的本地产物。只有经过人工验收和确定性后处理的 PNG、GLB、资产元数据
以及必要的 `.blend` 源文件才能提交。大规模引入二进制资产前应启用 Git LFS。

正式资产接入后，当前程序化居民和建筑继续作为加载失败时的 fallback。
