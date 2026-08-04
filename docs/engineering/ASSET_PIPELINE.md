# Blender 与 MMX 资产管线

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

SVG 与 MMX 是并行方案，不替代或删除 MMX。公共文件 `art/svg_pose_sets.yml` 管理画布、描边和
16 个标准动作的身体偏移、手臂角度、腿部角度、表情及道具。每个场景通过
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
`visual_asset_id` 将运行时 Agent 与视觉身份解耦。Godot 通过共享纹理、微幅呼吸/弹跳/摇摆和 140ms 双 Sprite 淡入淡出
获得接近 Codex 宠物的节奏感。SVG 缺失或角色尚未配置时继续使用原有程序化三维居民作为 fallback。

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

```bash
make assets-blender-install
make assets-blender-cafe
make assets-blender-campus
# 同时重建当前全部 Blender 场景
make assets-blender-all
```

脚本会拒绝非 `5.2.x` 版本，并生成：

- `art/blender/scenarios/campus_world/studio_cafe.blend`：可编辑源文件；
- `godot/world-client/assets/scenarios/campus_world/locations/studio_cafe/studio_cafe.glb`：运行时资产；
- `art/blender/scenarios/campus_world/campus_landmarks.blend`：校园公共地标源文件；
- `godot/world-client/assets/scenarios/campus_world/environment/campus_landmarks.glb`：广场、宿舍、
  教学楼与图书馆的统一运行时资产；
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

## 5. 提交规则

`art/generated/` 是候选素材区，也是可丢弃的本地产物。只有经过人工验收和确定性后处理的 PNG、GLB、资产元数据
以及必要的 `.blend` 源文件才能提交。大规模引入二进制资产前应启用 Git LFS。

正式资产接入后，当前程序化居民和建筑继续作为加载失败时的 fallback。
