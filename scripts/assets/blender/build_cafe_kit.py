"""Build the campus Studio Cafe cutaway with Blender 5.2 and export a Godot GLB."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import bpy

REQUIRED_BLENDER = (5, 2)
ASSET_ID = "campus_world/studio_cafe"


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
    # Prefer the data API for cleanup: object deletion operators depend on
    # selection and the active editor context, which do not belong in a
    # deterministic background build.
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for data_collection in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.curves,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for block in list(data_collection):
            if block.users == 0:
                data_collection.remove(block)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "BLENDER_EEVEE"
    bpy.context.preferences.filepaths.save_version = 0


def material(
    name: str,
    color: tuple[float, float, float, float],
    *,
    roughness: float = 0.82,
    metallic: float = 0.0,
    emission_strength: float = 0.0,
    transmission: float = 0.0,
) -> Any:
    result = bpy.data.materials.new(name)
    result.diffuse_color = color
    result.use_backface_culling = True
    if result.node_tree is None:
        raise RuntimeError(f"material has no node tree: {name}")
    principled = result.node_tree.nodes.get("Principled BSDF")
    if principled is None:
        raise RuntimeError(f"material has no Principled BSDF node: {name}")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Metallic"].default_value = metallic
    principled.inputs["Alpha"].default_value = color[3]
    principled.inputs["Transmission Weight"].default_value = transmission
    if color[3] < 1.0 and hasattr(result, "surface_render_method"):
        result.surface_render_method = "DITHERED"
    if emission_strength > 0.0:
        principled.inputs["Emission Color"].default_value = color
        principled.inputs["Emission Strength"].default_value = emission_strength
    return result


def tag(obj: Any, *, role: str, semantic_id: str | None = None) -> Any:
    obj["truman_role"] = role
    if semantic_id:
        obj["semantic_id"] = semantic_id
    return obj


def add_box(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    surface: Any,
    *,
    role: str,
    semantic_id: str | None = None,
    bevel: float = 0.0,
) -> Any:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(surface)
    if bevel > 0.0:
        modifier = obj.modifiers.new(name="SoftEdges", type="BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    return tag(obj, role=role, semantic_id=semantic_id)


def add_cylinder(
    name: str,
    location: tuple[float, float, float],
    radius: float,
    depth: float,
    surface: Any,
    *,
    role: str,
    semantic_id: str | None = None,
    vertices: int = 16,
) -> Any:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(surface)
    return tag(obj, role=role, semantic_id=semantic_id)


def add_torus(
    name: str,
    location: tuple[float, float, float],
    major_radius: float,
    minor_radius: float,
    surface: Any,
    *,
    role: str,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Any:
    bpy.ops.mesh.primitive_torus_add(
        major_segments=12,
        minor_segments=6,
        location=location,
        rotation=rotation,
        major_radius=major_radius,
        minor_radius=minor_radius,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(surface)
    return tag(obj, role=role)


def add_sphere(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    surface: Any,
    *,
    role: str,
) -> Any:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(surface)
    return tag(obj, role=role)


def add_text(
    name: str,
    body: str,
    location: tuple[float, float, float],
    surface: Any,
    *,
    size: float,
    role: str,
) -> Any:
    bpy.ops.object.text_add(location=location, rotation=(math.pi / 2.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.data.body = body
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = 0.018
    obj.data.bevel_depth = 0.005
    obj.data.bevel_resolution = 1
    obj.data.materials.append(surface)
    bpy.ops.object.convert(target="MESH")
    return tag(bpy.context.object, role=role)


def add_table(index: int, x: float, y: float, wood: Any, green: Any) -> None:
    add_cylinder(f"Table{index}Top", (x, y, 0.74), 0.52, 0.09, wood, role="table")
    add_cylinder(f"Table{index}Stem", (x, y, 0.39), 0.075, 0.7, green, role="table")
    add_cylinder(f"Table{index}Foot", (x, y, 0.05), 0.3, 0.06, green, role="table")


def add_chair(index: int, x: float, y: float, rotation: float, wood: Any, metal: Any) -> None:
    seat = add_box(
        f"Chair{index}Seat",
        (x, y, 0.46),
        (0.48, 0.48, 0.11),
        wood,
        role="seat",
        semantic_id="cafe.window-chair-1" if index == 1 else None,
        bevel=0.04,
    )
    seat.rotation_euler.z = rotation
    direction = (math.sin(rotation) * 0.18, -math.cos(rotation) * 0.18)
    back = add_box(
        f"Chair{index}Back",
        (x + direction[0], y + direction[1], 0.78),
        (0.48, 0.09, 0.58),
        wood,
        role="seat_back",
        bevel=0.035,
    )
    back.rotation_euler.z = rotation
    for leg_index, (dx, dy) in enumerate(
        ((-0.17, -0.17), (0.17, -0.17), (-0.17, 0.17), (0.17, 0.17)), start=1
    ):
        add_cylinder(
            f"Chair{index}Leg{leg_index}",
            (x + dx, y + dy, 0.22),
            0.025,
            0.44,
            metal,
            role="seat_leg",
            vertices=8,
        )


def build_cafe_kit() -> dict[str, int]:
    cream = material("TW_CreamPlaster", (0.78, 0.69, 0.55, 1.0))
    light_cream = material("TW_WarmInterior", (0.92, 0.84, 0.68, 1.0))
    terracotta = material("TW_Terracotta", (0.64, 0.22, 0.12, 1.0))
    green = material("TW_DeepGreen", (0.07, 0.20, 0.16, 1.0))
    leaf = material("TW_Leaf", (0.18, 0.38, 0.23, 1.0))
    wood = material("TW_Walnut", (0.30, 0.15, 0.075, 1.0), roughness=0.7)
    pale_wood = material("TW_Oak", (0.58, 0.38, 0.20, 1.0), roughness=0.74)
    glass = material(
        "TW_WindowGlass",
        (0.36, 0.63, 0.68, 0.42),
        roughness=0.18,
        transmission=0.18,
    )
    dark_glass = material(
        "TW_DisplayGlass",
        (0.20, 0.38, 0.40, 0.34),
        roughness=0.14,
        transmission=0.24,
    )
    metal = material("TW_BlackMetal", (0.045, 0.055, 0.055, 1.0), roughness=0.38, metallic=0.55)
    porcelain = material("TW_Porcelain", (0.87, 0.83, 0.72, 1.0), roughness=0.42)
    pastry = material("TW_Pastry", (0.72, 0.39, 0.14, 1.0), roughness=0.68)
    warm_light = material(
        "TW_WarmLight",
        (1.0, 0.62, 0.22, 1.0),
        roughness=0.25,
        emission_strength=1.8,
    )

    # Blender is Z-up. glTF's Y-up conversion produces correctly oriented Godot geometry.
    add_box("CafeFloor-col", (0.0, 0.0, 0.06), (5.6, 4.4, 0.12), light_cream, role="floor")
    add_box("CafeBackWall-col", (0.0, 2.14, 1.48), (5.6, 0.12, 2.96), cream, role="wall")
    add_box("CafeLeftWall-col", (-2.74, 0.0, 1.48), (0.12, 4.4, 2.96), cream, role="wall")
    add_box("CafeRightPier", (2.74, 1.5, 1.48), (0.12, 1.3, 2.96), cream, role="wall")
    add_box(
        "BackBaseboard",
        (0.0, 2.055, 0.18),
        (5.46, 0.08, 0.24),
        green,
        role="wall_trim",
        bevel=0.018,
    )
    add_box(
        "LeftBaseboard",
        (-2.655, 0.0, 0.18),
        (0.08, 4.25, 0.24),
        green,
        role="wall_trim",
        bevel=0.018,
    )
    add_box(
        "BackPictureRail",
        (0.0, 2.045, 2.68),
        (5.45, 0.07, 0.08),
        pale_wood,
        role="wall_trim",
    )
    add_box(
        "CafeRoof",
        (0.0, 1.43, 3.02),
        (5.82, 1.55, 0.16),
        green,
        role="cutaway_roof",
        bevel=0.04,
    )
    add_box(
        "FrontAwning",
        (0.15, -2.15, 2.34),
        (4.45, 0.92, 0.13),
        terracotta,
        role="awning",
        bevel=0.035,
    )
    add_box(
        "CafeSignBoard",
        (0.2, -2.17, 2.76),
        (3.05, 0.12, 0.55),
        green,
        role="sign",
        bevel=0.08,
    )
    add_text(
        "CafeSignText",
        "STUDIO CAFE",
        (0.2, -2.245, 2.76),
        light_cream,
        size=0.31,
        role="sign_detail",
    )
    add_box(
        "AwningStripeA",
        (-1.0, -2.62, 2.25),
        (0.48, 0.08, 0.3),
        light_cream,
        role="awning",
    )
    add_box(
        "AwningStripeB",
        (0.15, -2.62, 2.25),
        (0.48, 0.08, 0.3),
        light_cream,
        role="awning",
    )
    add_box(
        "AwningStripeC",
        (1.3, -2.62, 2.25),
        (0.48, 0.08, 0.3),
        light_cream,
        role="awning",
    )

    add_box(
        "BackWindow",
        (1.25, 2.07, 1.56),
        (2.05, 0.035, 1.22),
        glass,
        role="window",
        bevel=0.025,
    )
    for x in (0.25, 1.25, 2.25):
        add_box(
            f"WindowMullion{x}",
            (x, 2.035, 1.56),
            (0.045, 0.05, 1.26),
            green,
            role="window_frame",
        )
    add_box(
        "WindowSill",
        (1.25, 2.0, 0.91),
        (2.22, 0.2, 0.12),
        pale_wood,
        role="window_frame",
        bevel=0.025,
    )
    add_box(
        "EntranceFrameLeft",
        (-1.92, -2.12, 1.25),
        (0.14, 0.15, 2.5),
        green,
        role="door_frame",
    )
    add_box(
        "EntranceFrameRight",
        (-0.68, -2.12, 1.25),
        (0.14, 0.15, 2.5),
        green,
        role="door_frame",
    )
    add_box(
        "EntranceFrameTop",
        (-1.3, -2.12, 2.45),
        (1.38, 0.15, 0.14),
        green,
        role="door_frame",
    )
    add_box("EntranceGlass", (-1.3, -2.09, 1.28), (1.08, 0.035, 2.18), glass, role="door")
    add_cylinder(
        "DoorHandle",
        (-0.82, -2.02, 1.18),
        0.035,
        0.42,
        metal,
        role="door_handle",
        vertices=10,
    )

    add_box(
        "CoffeeCounter-col",
        (-0.65, 1.02, 0.53),
        (2.75, 0.72, 1.06),
        wood,
        role="interactable",
        semantic_id="cafe.coffee-counter",
        bevel=0.055,
    )
    add_box(
        "CounterTop",
        (-0.65, 1.02, 1.09),
        (2.92, 0.86, 0.12),
        pale_wood,
        role="counter",
        bevel=0.04,
    )
    add_box(
        "CounterFrontInset",
        (-0.65, 0.65, 0.55),
        (2.3, 0.04, 0.62),
        green,
        role="counter_detail",
        bevel=0.02,
    )
    add_box(
        "PastryCaseBase",
        (1.2, 1.02, 0.36),
        (0.72, 0.72, 0.72),
        wood,
        role="display_case",
        bevel=0.035,
    )
    add_box(
        "PastryCaseGlass",
        (1.2, 1.02, 0.9),
        (0.72, 0.68, 0.38),
        dark_glass,
        role="display_case",
        bevel=0.035,
    )
    for index, x in enumerate((0.98, 1.2, 1.42), start=1):
        add_sphere(
            f"Pastry{index}",
            (x, 0.68, 0.82),
            (0.1, 0.075, 0.055),
            pastry,
            role="food_display",
        )

    add_box(
        "EspressoMachine",
        (-0.95, 1.0, 1.34),
        (0.88, 0.52, 0.48),
        metal,
        role="appliance",
        bevel=0.07,
    )
    add_cylinder(
        "EspressoBoiler",
        (-0.95, 1.0, 1.58),
        0.22,
        0.46,
        porcelain,
        role="appliance",
        vertices=16,
    )
    for index, x in enumerate((-1.16, -0.75), start=1):
        add_cylinder(
            f"GroupHead{index}",
            (x, 0.7, 1.24),
            0.07,
            0.18,
            metal,
            role="appliance",
            vertices=12,
        )
    for index, x in enumerate((-1.22, -0.92, -0.62), start=1):
        add_cylinder(
            f"MachineCup{index}",
            (x, 0.73, 1.67),
            0.075,
            0.13,
            porcelain,
            role="cup",
            vertices=12,
        )
        add_torus(
            f"MachineCupHandle{index}",
            (x + 0.075, 0.73, 1.68),
            0.045,
            0.012,
            porcelain,
            role="cup_handle",
            rotation=(math.pi / 2.0, 0.0, 0.0),
        )
    add_box(
        "MenuBoard",
        (-1.05, 2.04, 2.15),
        (2.0, 0.045, 0.7),
        green,
        role="sign",
        bevel=0.025,
    )
    for index, z in enumerate((2.32, 2.14, 1.96), start=1):
        add_box(
            f"MenuLine{index}",
            (-1.05, 1.995, z),
            (1.5 - index * 0.12, 0.02, 0.035),
            porcelain,
            role="sign_detail",
        )

    add_table(1, 1.42, -0.5, wood, green)
    add_table(2, -0.75, -0.72, wood, green)
    add_cylinder(
        "TableCup",
        (1.42, -0.5, 0.86),
        0.075,
        0.18,
        porcelain,
        role="cup",
        vertices=12,
    )
    add_torus(
        "TableCupHandle",
        (1.5, -0.5, 0.88),
        0.048,
        0.012,
        porcelain,
        role="cup_handle",
        rotation=(math.pi / 2.0, 0.0, 0.0),
    )
    add_chair(1, 1.42, -1.3, 0.0, terracotta, metal)
    add_chair(2, 1.42, 0.28, math.pi, terracotta, metal)
    add_chair(3, -1.55, -0.72, math.pi / 2.0, pale_wood, metal)
    add_chair(4, 0.05, -0.72, -math.pi / 2.0, pale_wood, metal)

    add_box("BackShelf", (2.35, 2.0, 1.5), (0.72, 0.28, 1.8), wood, role="shelf", bevel=0.03)
    for row, z in enumerate((1.05, 1.45, 1.85), start=1):
        add_box(
            f"ShelfBoard{row}",
            (2.35, 1.8, z),
            (0.85, 0.42, 0.06),
            pale_wood,
            role="shelf",
        )
        for column, x in enumerate((2.13, 2.35, 2.57), start=1):
            add_cylinder(
                f"ShelfCup{row}_{column}",
                (x, 1.72, z + 0.11),
                0.07,
                0.18,
                porcelain,
                role="cup",
                vertices=12,
            )

    for index, (x, z, print_surface) in enumerate(
        ((-2.2, 2.08, terracotta), (-1.65, 2.08, pale_wood)), start=1
    ):
        add_box(
            f"WallArtFrame{index}",
            (x, 2.035, z),
            (0.42, 0.06, 0.54),
            wood,
            role="wall_art",
            bevel=0.025,
        )
        add_box(
            f"WallArtPrint{index}",
            (x, 1.998, z),
            (0.32, 0.018, 0.42),
            print_surface,
            role="wall_art",
        )

    add_cylinder(
        "PlanterPot",
        (2.25, -1.55, 0.34),
        0.34,
        0.68,
        terracotta,
        role="prop",
        vertices=16,
    )
    add_cylinder("PlantStem", (2.25, -1.55, 0.86), 0.06, 0.55, green, role="prop", vertices=10)
    for index, (dx, dy, z) in enumerate(
        ((-0.25, 0.0, 1.0), (0.22, 0.05, 1.15), (0.0, -0.18, 1.32)), start=1
    ):
        leaf_obj = add_cylinder(
            f"PlantLeaf{index}",
            (2.25 + dx, -1.55 + dy, z),
            0.22,
            0.48,
            leaf,
            role="prop",
            vertices=10,
        )
        leaf_obj.scale = (0.45, 1.0, 1.0)

    for index, x in enumerate((-0.75, 0.85), start=1):
        add_cylinder(
            f"PendantCable{index}",
            (x, -0.15, 2.62),
            0.012,
            0.58,
            metal,
            role="light",
            vertices=8,
        )
        add_cylinder(
            f"PendantShade{index}",
            (x, -0.15, 2.31),
            0.2,
            0.18,
            green,
            role="light",
            vertices=16,
        )
        add_cylinder(
            f"PendantGlow{index}",
            (x, -0.15, 2.2),
            0.09,
            0.12,
            warm_light,
            role="light",
            vertices=12,
        )

    meshes = list(bpy.data.meshes)
    return {
        "objects": len(bpy.context.scene.objects),
        "meshes": len(meshes),
        "materials": len(bpy.data.materials),
        "vertices": sum(len(mesh.vertices) for mesh in meshes),
        "polygons": sum(len(mesh.polygons) for mesh in meshes),
    }


def export_glb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    if result != {"FINISHED"} or not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"glTF export did not produce a non-empty file: {path}")


def main() -> None:
    args = parse_args()
    require_blender_version()
    reset_scene()
    stats = build_cafe_kit()
    if args.source:
        args.source.parent.mkdir(parents=True, exist_ok=True)
        result = bpy.ops.wm.save_as_mainfile(
            filepath=str(args.source.resolve()),
            check_existing=False,
        )
        if result != {"FINISHED"}:
            raise RuntimeError(f"failed to save Blender source: {args.source}")
    export_glb(args.output.resolve())
    metadata_path = args.metadata or args.output.with_suffix(".asset.json")
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "asset_id": ASSET_ID,
                "blender_version": bpy.app.version_string,
                "coordinate_system": {
                    "authoring_up": "Z",
                    "runtime_up": "Y",
                    "unit": "meter",
                },
                "output": str(args.output),
                "source": str(args.source) if args.source else None,
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
