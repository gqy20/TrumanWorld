# Blender 与 MMX 资产管线

- 状态：第一阶段已实现
- Blender：正式版 `5.2.x`
- Godot：`4.7.1`
- 三维交换格式：glTF 2.0 Binary（`.glb`）
- 二维生成：MMX CLI `image-01`

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

角色参考图只约束身份和服装，不直接充当最终贴图。MMX 的输出一律先进入候选区；二维风格、肢体、
身份连续性通过人工验收后，才允许由确定性处理器发布到 Godot 资产目录。生成失败或意外变成 3D
玩偶风格时，不应通过后处理掩盖问题，而应调整版本化提示词并重新生成。

## 3. 常用命令

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

Blender 5.2 安装后运行：

```bash
make assets-blender-cafe BLENDER=/path/to/blender
```

脚本会拒绝非 `5.2.x` 版本，并生成：

- `art/blender/studio_cafe_kit.blend`：可编辑源文件；
- `godot/world-client/assets/locations/studio_cafe_kit.glb`：运行时资产；
- 同目录 `.asset.json`：版本和网格统计。

## 4. 提交规则

`art/generated/` 是候选素材区，也是可丢弃的本地产物。只有经过人工验收和确定性后处理的 PNG、GLB、资产元数据
以及必要的 `.blend` 源文件才能提交。大规模引入二进制资产前应启用 Git LFS。

正式资产接入后，当前程序化居民和建筑继续作为加载失败时的 fallback。
