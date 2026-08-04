"""Build the Truman World cafe modular kit with Blender 5.2 and export a GLB."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

REQUIRED_BLENDER = (5, 2)


def parse_args() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--metadata", type=Path)
    return parser.parse_args(arguments)


def require_blender_version() -> None:
    if bpy.app.version[:2] != REQUIRED_BLENDER:
        expected = ".".join(map(str, REQUIRED_BLENDER))
        raise RuntimeError(f"Blender {expected}.x required, got {bpy.app.version_string}")
    unstable_markers = ("alpha", "beta", "release candidate")
    if any(marker in bpy.app.version_string.lower() for marker in unstable_markers):
        raise RuntimeError(f"an official Blender release is required: {bpy.app.version_string}")


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for data_collection in (bpy.data.meshes, bpy.data.materials, bpy.data.curves):
        for block in list(data_collection):
            if block.users == 0:
                data_collection.remove(block)


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.82):
    result = bpy.data.materials.new(name)
    result.diffuse_color = color
    result.use_nodes = True
    principled = result.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = roughness
    return result


def add_box(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    surface,
    *,
    role: str,
):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(surface)
    obj["truman_role"] = role
    return obj


def add_cylinder(
    name: str,
    location: tuple[float, float, float],
    radius: float,
    depth: float,
    surface,
    *,
    role: str,
    vertices: int = 16,
):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(surface)
    obj["truman_role"] = role
    return obj


def build_cafe_kit() -> dict[str, int]:
    cream = material("TW_Cream", (0.83, 0.75, 0.59, 1.0))
    terracotta = material("TW_Terracotta", (0.72, 0.31, 0.19, 1.0))
    green = material("TW_DeepGreen", (0.12, 0.25, 0.21, 1.0))
    wood = material("TW_Wood", (0.39, 0.24, 0.14, 1.0))
    glass = material("TW_Window", (0.52, 0.72, 0.75, 1.0), roughness=0.28)

    add_box("CafeFloor", (0.0, 0.05, 0.0), (6.0, 0.1, 4.5), cream, role="floor")
    add_box("CafeBackWall-col", (0.0, 1.4, -2.2), (6.0, 2.8, 0.12), cream, role="wall")
    add_box("CafeLeftWall-col", (-2.94, 1.4, 0.0), (0.12, 2.8, 4.5), cream, role="wall")
    add_box("CafeRoof", (0.0, 2.94, -1.35), (6.2, 0.18, 1.75), green, role="cutaway_roof")
    add_box("FrontAwning", (0.0, 2.25, 2.35), (4.2, 0.16, 0.9), terracotta, role="awning")
    add_box("Window", (1.2, 1.45, -2.125), (2.0, 1.15, 0.04), glass, role="window")
    add_box("CoffeeCounter-col", (-0.9, 0.52, -0.75), (2.7, 1.04, 0.72), wood, role="interactable")

    for index, x in enumerate((-1.4, 1.35), start=1):
        add_cylinder(f"CafeTable{index}", (x, 0.72, 0.65), 0.62, 0.1, wood, role="table")
        add_cylinder(f"CafeTableLeg{index}", (x, 0.36, 0.65), 0.09, 0.72, green, role="table")
        for chair_index, z_offset in enumerate((-0.85, 0.85), start=1):
            add_box(
                f"Chair{index}_{chair_index}-convcol",
                (x, 0.42, 0.65 + z_offset),
                (0.55, 0.84, 0.55),
                terracotta,
                role="seat",
            )

    add_cylinder("Planter", (2.35, 0.42, -1.25), 0.42, 0.84, terracotta, role="prop")
    add_cylinder("Plant", (2.35, 1.1, -1.25), 0.58, 0.7, green, role="prop", vertices=12)
    return {
        "objects": len(bpy.context.scene.objects),
        "meshes": len(bpy.data.meshes),
        "materials": len(bpy.data.materials),
    }


def export_glb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    desired = {
        "filepath": str(path),
        "export_format": "GLB",
        "use_selection": False,
        "export_yup": True,
        "export_apply": True,
        "export_materials": "EXPORT",
        "export_cameras": False,
        "export_lights": False,
        "export_extras": True,
    }
    supported = set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys())
    bpy.ops.export_scene.gltf(**{key: value for key, value in desired.items() if key in supported})


def main() -> None:
    args = parse_args()
    require_blender_version()
    reset_scene()
    stats = build_cafe_kit()
    export_glb(args.output.resolve())
    if args.source:
        args.source.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.source.resolve()))
    metadata_path = args.metadata or args.output.with_suffix(".asset.json")
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "asset_id": "studio_cafe_kit",
                "blender_version": bpy.app.version_string,
                "output": str(args.output),
                "stats": stats,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "output": str(args.output), "stats": stats}))


if __name__ == "__main__":
    main()
