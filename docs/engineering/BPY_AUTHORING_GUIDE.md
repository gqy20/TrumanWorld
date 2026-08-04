# BPY 场景构建规范

- 适用范围：`scripts/assets/blender/` 下由命令行运行的确定性场景构建器
- 基准版本：Blender `5.2.x` 正式版
- 运行方式：后台模式构建 `.blend`，并导出供 Godot 使用的静态 `.glb`
- 最近审计：2026-08-05

本文只约束程序化资产构建，不约束交互式 Blender 插件、面板或艺术家手工编辑流程。

## 1. 当前审计结论

三个构建器的总体方向符合 Blender 官方 API 的使用方式：脚本使用明确入口、米制 Z-up 场景、
Principled BSDF、glTF 官方导出器、自定义属性和后台执行。语义地图与视觉模型之间也保持了正确边界。

| 检查项 | 当前状态 | 结论 |
|---|---|---|
| 固定 Blender 版本 | 已统一检查 `5.2.x` 正式版 | 符合 |
| 命令行隔离 | 使用 `--background --factory-startup --python-exit-code 1` | 符合 |
| 参数边界 | 自定义参数放在 `--` 后，由 `argparse` 解析 | 符合 |
| 场景清理 | 使用 `bpy.data.objects.remove(..., do_unlink=True)` | 已修正为低上下文依赖 |
| 几何创建 | 低模基元使用 `bpy.ops.mesh.primitive_*_add` | 可接受，调用点上下文明确 |
| 合并与转换 | 仍使用 `convert / modifier_apply / join` | 可接受，但必须显式设置选择和 active object |
| GLB 导出 | 固定静态场景参数并检查 `FINISHED` 与输出文件 | 已修正为失败即停 |
| 静态资产 | 显式关闭 animation、skin、morph 导出 | 已修正 |
| 语义元数据 | `export_extras=True`，对象使用稳定自定义属性 | 符合 |
| 确定性 | 无时间、随机数和外部网络输入 | 符合 |
| Python 风格 | 4 空格、显式 import、Ruff 兼容 | 符合仓库规范 |
| 数据块命名 | 名称稳定，但不能把名称当唯一业务主键 | 需持续遵守 |
| 重复代码 | 三个脚本有少量基础函数重复 | 暂时接受，见 8.2 |

当前没有发现需要把整个建模逻辑改写为 BMesh 的理由。现有场景主要由立方体、圆柱、圆锥和低模球体
组成，primitive operator 可读性更好；BMesh 更适合大量拓扑编辑、批量生成单一网格或操作 Edit Mode
数据，不应为了“更原生”而机械替换。

## 2. 官方原则在本项目中的解释

### 2.1 优先数据 API，谨慎使用 Operator

`bpy.data` 和 RNA 属性适合无界面构建，因为对象、材质和网格可以显式传递。`bpy.ops` 面向用户操作，
依赖当前模式、选择、active object、区域等上下文，且返回的是执行状态而不是结果对象。

本项目采用以下边界：

- 数据块删除、属性赋值、材质设置、自定义属性使用数据 API；
- Blender 仅以 operator 暴露的 glTF 导出和保存文件继续使用 operator；
- primitive 创建可以使用 operator，但必须在 factory startup、Object Mode 的确定上下文中立即取得
  `bpy.context.object`，不得跨函数依赖“上一次选中对象”；
- `join`、`convert`、`modifier_apply` 前必须显式设置选择集合和 active object；
- 不允许通过捕获 `RuntimeError` 后静默跳过 operator。

Blender 官方风格指南建议 enum 字符串使用单引号；本仓库由 Ruff 统一使用双引号。这里遵循仓库级
格式规范，因为构建器不是准备合入 Blender 上游的插件，二者在 API 语义上没有差异。

### 2.2 后台构建必须失败即停

统一入口是：

```bash
.tools/blender/blender \
  --background \
  --factory-startup \
  --python-exit-code 1 \
  --python scripts/assets/blender/build_narrative_town.py -- \
  --source art/blender/scenarios/narrative_world/seaside_town.blend \
  --output godot/world-client/assets/scenarios/narrative_world/environment/seaside_town.glb
```

Blender 按参数出现顺序执行命令，因此 `--background`、`--factory-startup` 和异常退出码必须位于
`--python` 前。`--` 后的内容属于构建脚本，不能再放 Blender 自身参数。

禁止动态过滤“不支持的导出参数”。项目固定 Blender 5.2，API 不匹配代表工具链契约已经破坏，应该
直接失败并更新脚本。导出完成后同时验证 operator 返回 `{"FINISHED"}`、文件存在且非空。

### 2.3 构建必须可复现

同一提交、同一 Blender patch 版本和同一命令应产生语义等价的资产。构建器必须满足：

- 不读取当前时间、用户选择、默认启动文件或未声明环境变量；
- 不在 Blender 主进程中启动未 join 的线程；
- 如需随机布置，必须使用局部 `random.Random(seed)`，seed 写入资产元数据；
- 所有输入路径来自命令行或受版本控制的配置；
- 输出父目录由脚本创建，输入路径使用 `pathlib.Path`；
- 脚本重复运行不得产生 `.001` 材质、残留对象或不断增长的孤立数据块；
- 后台构建进程将 `PreferencesFilePaths.save_version` 设为 `0`，避免生成 `.blend1`；该设置只存在于
  `--factory-startup` 启动的临时进程，不写回艺术家的用户偏好；
- 不依赖对象遍历的偶然顺序；影响最终结构时显式排序。

## 3. 数据与上下文规则

### 3.1 清理场景

删除全部对象时使用：

```python
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
```

随后只删除 `users == 0` 的 mesh、material、curve、camera 和 light 数据块。不要调用
`ID.user_clear()`；官方将其标记为高级接口，误用会造成崩溃。也不要用 `select_all/delete` 作为后台
清理逻辑，因为它把正确性绑定到选择状态。

### 3.2 创建和保存对象引用

创建对象后应立即保存引用并完成设置：

```python
bpy.ops.mesh.primitive_cube_add(location=location)
obj = bpy.context.object
if obj is None:
    raise RuntimeError("cube creation did not produce an active object")
obj.name = name
obj.dimensions = dimensions
```

对象名称可能因冲突或长度限制被 Blender 改写。函数内部应传递对象引用，不能创建后再通过请求名称
反查。名称用于 Outliner 可读性和测试定位；业务身份必须写入 `location_id`、`semantic_id` 或其他
版本化自定义属性。

不要在删除其底层 Blender 数据块后继续保存 Python 包装对象。官方文档明确提醒这类引用会失效，
极端情况下可能访问无效内存。

### 3.3 模式

本项目构建器只在 Object Mode 工作。未来如引入 Edit Mode，离开该模式前不能假设 `obj.data` 已经
同步；应显式退出 Edit Mode，或用 `bmesh.from_edit_mesh()` / `BMesh.to_mesh()` 管理同步。

## 4. 几何和性能

### 4.1 选择正确的建模 API

| 场景 | 推荐 API |
|---|---|
| 少量标准低模基元 | `bpy.ops.mesh.primitive_*_add` |
| 已知全部顶点和面的一次性网格 | `Mesh.from_pydata()` |
| 大量拓扑修改、焊接、切分 | `bmesh` |
| 重复静态装饰 | 共享 mesh、集合实例或导出前按角色合并 |
| 必须保留独立语义节点 | 保留独立 object，不为 draw call 盲目合并 |

批量场景的主要成本通常不是 Python 列表语法，而是创建数百个独立 object、反复触发依赖图更新和
最终 Web draw call。应优先减少不需要独立身份的对象数量。现有树木、路灯、道路和边界按角色合并，
方向正确；门、座位和交互点若需要运行时寻址则不应合并。

### 4.2 Transform 与 Modifier

- 尺寸通过 `obj.dimensions` 设置后，若后续 modifier 依赖真实尺度，应显式 apply scale；
- 不要为了导出统一对所有对象执行 location/rotation apply，这会损失有意义的节点 transform；
- `export_apply=True` 会应用非 Armature modifier，官方同时警告它会阻止 shape key 导出；因此它只适合
  当前静态环境资产，角色或表情模型必须使用独立导出契约；
- 合并前先应用需要保留的 modifier，并明确 active object；合并会改变对象级自定义属性的所有权。

### 4.3 倒角、法线与网格校验

硬表面低模不能只依靠增加多边形。当前 `narrative_world` 环境模型使用两段 Bevel，并显式启用：

- `limit_method = "ANGLE"`：只处理足够锐利的边；
- `use_clamp_overlap = True`：防止门框、窗框等小物件因倒角宽度产生自相交；
- `harden_normals = True`：保持墙面和屋顶大平面的平整明暗，让倒角承担高光过渡。

圆柱、圆锥等建筑构件使用 `Mesh.shade_smooth()`，再通过
`Mesh.set_sharp_from_angle(math.radians(45))` 恢复端盖和大折角的硬边。树冠等刻意保留低多边形切面的
对象不做平滑。每个 mesh 数据块使用稳定的 `<ObjectName>Mesh` 名称，避免 `.blend` 和 glTF 中只剩
`Cube.042` 之类无法审查的名称。

保存和导出前必须调用 `Mesh.validate()` 与 `Mesh.validate_material_indices()`。如果 Blender 修复了任何
无效几何或材质索引，构建应失败，而不是把自动修复后的未知结果发布到 Godot。还要检查所有对象
`matrix_world` 都是有限数值、没有空 mesh。

### 4.4 统计评估

含 modifier 的模型不能直接用源 `obj.data` 统计最终顶点和面数。应从
`bpy.context.evaluated_depsgraph_get()` 获取依赖图，对每个对象使用 `evaluated_get()` 和 `to_mesh()`，
统计 modifier 后网格，并在 `finally` 中调用 `to_mesh_clear()`。三角形数量在临时网格上调用
`calc_loop_triangles()` 后计算。

这种统计更接近 glTF/Godot 实际负担，但仍不保证与 exporter 内部优化后的字节级结果完全一致。

## 5. 坐标、单位和颜色

- Blender 源场景固定 Z-up、米制、`scale_length = 1.0`；
- glTF 固定 `export_yup=True`，不在模型脚本里手工交换轴；
- 语义地图坐标映射写入 `.asset.json`，视觉模型不能成为导航事实来源；
- 透明材质必须同时设置 Principled Alpha 和 Blender 5.2 的 surface render method；
- 当前环境几何均为封闭实体，材质必须设置 `use_backface_culling = True`；Blender 官方 glTF exporter
  会把关闭背面剔除的材质导出为 `doubleSided`，增加 Godot/Web 不必要的背面片元处理。未来只有树叶
  卡片、布片等真正单面资源才能显式选择双面材质；
- Blender 5.2 新建材质已经默认使用节点，不再赋值已弃用的 `Material.use_nodes`；取得
  `node_tree` 和 `Principled BSDF` 失败时应立即报错，不能生成无意的 fallback 材质；
- 当前 Python RGBA 常量按 scene-linear 数值解释。若调色板来源是 CSS、SVG、十六进制或设计稿 sRGB，
  必须先用 `mathutils.Color.from_srgb_to_scene_linear()` 转换，不能直接除以 255 后当作线性值使用；
- 材质名称使用稳定 `TW_` 前缀，避免从外部 `.blend` 合并时难以辨认。

## 6. 静态 GLB 导出契约

环境构建器必须显式设置以下关键参数：

```python
result = bpy.ops.export_scene.gltf(
    filepath=str(path),
    check_existing=False,
    export_format="GLB",
    use_selection=False,
    export_yup=True,
    export_apply=True,
    export_materials="EXPORT",
    export_cameras=False,
    export_lights=False,
    export_extras=True,
    export_animations=False,
    export_skins=False,
    export_morph=False,
)
```

`export_extras=True` 是运行时语义标签能够进入 glTF 的契约，不得随意关闭。静态环境不导出 camera、
light、animation、skin 和 morph，Godot 拥有最终相机、灯光和交互状态。角色模型不能直接复用该
契约，应新增明确命名的 animated export profile。

## 7. 元数据与可观测性

每次构建至少输出：

- `schema_version`、`asset_id`、完整 Blender 版本；
- authoring/runtime up axis 与单位；
- source、output 路径；
- object、mesh、material、vertex、polygon 统计；复杂场景同时记录 modifier 后 triangle 数量；
- 场景资产的语义位置映射和环境边界；
- 最终一行机器可读 JSON，成功时包含 `ok: true`。

未来如果资产构建进入 CI，应再增加输出文件 SHA-256、构建耗时和预算阈值，但不要承诺 GLB 二进制
逐字节稳定；Blender/glTF patch 版本变化可能改变序列化结果，运行时结构和统计才是主要回归契约。

## 8. 代码组织

### 8.1 函数边界

构建器保持以下顺序：参数解析、版本验证、场景重置、材质/基元 helper、领域组合函数、统计、导出、
metadata。领域函数接收材质表和明确坐标，不读取隐藏全局选择状态。

大型场景优先以“地点/街区/系统”拆函数，例如 `build_plaza()`、`seaside_house()`、`tree()`；不要把
所有对象创建堆入 `main()`。常量重复且具业务含义时再提升为配置，不要把每个尺寸都 YAML 化。

### 8.2 为什么暂不抽公共 Python 包

当前三个脚本的 primitive/material helper 有重复，但 Blender 的隔离 Python 路径默认不包含仓库根目录
或脚本目录。直接抽取共享模块会让 Makefile 入口依赖额外 `PYTHONPATH` 或隐式修改 `sys.path`，反而
增加环境差异。现阶段保留少量自包含重复，并用本文和测试维持一致契约。

当 helper 继续增长时，应一次性完成以下迁移：

1. 将构建器安装为 Blender 可发现的包，或由统一 bootstrap 显式加入经过解析的仓库路径；
2. 为公共层添加不启动 Blender 的纯 Python 单测，以及 Blender 后台 smoke test；
3. 禁止各构建器覆盖公共导出策略；
4. 不通过 `--python-use-system-env` 无限制继承用户 `PYTHONPATH`。

## 9. 验证清单

修改 BPY 后至少运行：

```bash
make assets-blender-cafe
make assets-blender-campus
make assets-blender-town
make godot-test
git diff --check
```

审阅生成结果时检查：

- Blender 输出中没有 Python traceback 或 operator poll failure；
- Blender 输出中没有尚未评估的 `DeprecationWarning`；
- `.blend`、`.glb` 和 `.asset.json` 均更新；
- GLB 能被 Godot 无错误导入；
- 自定义 `location_id` / `semantic_id` 仍存在；
- 统计没有无解释地激增；
- 透明材质、法线、轴向和实际一米尺度正确；
- 重复执行不会出现 `.001` 数据块或多余对象。

## 10. 官方参考

- [Blender 5.2 Python API：Best Practice](https://docs.blender.org/api/5.2/info_best_practice.html)
- [Blender 5.2 Python API：Using Operators](https://docs.blender.org/api/5.2/info_gotchas_operators.html)
- [Blender 5.2 Python API：Internal Data and Python Objects](https://docs.blender.org/api/5.2/info_gotchas_internal_data_and_python_objects.html)
- [Blender 5.2 Python API：Modes and Mesh Access](https://docs.blender.org/api/5.2/info_gotchas_meshes.html)
- [Blender 5.2 Python API：Python Threads are Not Supported](https://docs.blender.org/api/5.2/info_gotchas_threading.html)
- [Blender 5.2 Python API：glTF Export Operator](https://docs.blender.org/api/5.2/bpy.ops.export_scene.html#bpy.ops.export_scene.gltf)
- [Blender 5.2 Python API：Color Space Conversion](https://docs.blender.org/api/5.2/mathutils.html#mathutils.Color.from_srgb_to_scene_linear)
- [Blender 5.2 Manual：Bevel Modifier](https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/bevel.html)
- [Blender 5.2 Python API：BevelModifier](https://docs.blender.org/api/5.2/bpy.types.BevelModifier.html)
- [Blender 5.2 Python API：Mesh](https://docs.blender.org/api/5.2/bpy.types.Mesh.html)
- [Blender 5.2 Python API：Material](https://docs.blender.org/api/5.2/bpy.types.Material.html)
- [Blender 5.2 Python API：Object Evaluation](https://docs.blender.org/api/5.2/bpy.types.Object.html#bpy.types.Object.evaluated_get)
- [Blender 5.2 Manual：Command Line Arguments](https://docs.blender.org/manual/en/5.2/advanced/command_line/arguments.html)
