"""Build the authored seaside town for the narrative_world scenario."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import bpy

REQUIRED_BLENDER = (5, 2)
ASSET_ID = "narrative_world/seaside_town"


def parse_args() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--metadata", type=Path)
    return parser.parse_args(arguments)


def reset_scene() -> None:
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
    bpy.context.preferences.filepaths.save_version = 0


def require_blender_version() -> None:
    if bpy.app.version[:2] != REQUIRED_BLENDER:
        raise RuntimeError(f"Blender 5.2.x required, got {bpy.app.version_string}")
    unstable_markers = ("alpha", "beta", "release candidate")
    if any(marker in bpy.app.version_string.lower() for marker in unstable_markers):
        raise RuntimeError(f"an official Blender release is required: {bpy.app.version_string}")


def material(
    name: str,
    color: tuple[float, float, float, float],
    *,
    roughness: float = 0.82,
    metallic: float = 0.0,
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
    if color[3] < 1.0 and hasattr(result, "surface_render_method"):
        result.surface_render_method = "DITHERED"
    return result


def tag(obj: Any, role: str, location_id: str | None = None) -> Any:
    obj["truman_role"] = role
    if location_id:
        obj["location_id"] = location_id
    return obj


def prepare_mesh(obj: Any, name: str, *, smooth_by_angle: bool = False) -> Any:
    if obj is None or obj.type != "MESH":
        raise RuntimeError(f"mesh creation did not produce a mesh object: {name}")
    obj.name = name
    obj.data.name = name + "Mesh"
    if smooth_by_angle:
        obj.data.shade_smooth()
        obj.data.set_sharp_from_angle(angle=math.radians(45.0))
    return obj


def box(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    surface: Any,
    *,
    role: str,
    location_id: str | None = None,
    bevel: float = 0.0,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Any:
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = prepare_mesh(bpy.context.object, name)
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(surface)
    if bevel > 0.0:
        modifier = obj.modifiers.new(name="SoftEdges", type="BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        modifier.limit_method = "ANGLE"
        modifier.use_clamp_overlap = True
        modifier.harden_normals = True
    return tag(obj, role, location_id)


def cylinder(
    name: str,
    location: tuple[float, float, float],
    radius: float,
    depth: float,
    surface: Any,
    *,
    role: str,
    location_id: str | None = None,
    vertices: int = 12,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Any:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=location,
        rotation=rotation,
    )
    obj = prepare_mesh(bpy.context.object, name, smooth_by_angle=True)
    obj.data.materials.append(surface)
    return tag(obj, role, location_id)


def cone(
    name: str,
    location: tuple[float, float, float],
    radius1: float,
    radius2: float,
    depth: float,
    surface: Any,
    *,
    role: str,
    location_id: str | None = None,
    vertices: int = 12,
) -> Any:
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius1,
        radius2=radius2,
        depth=depth,
        location=location,
    )
    obj = prepare_mesh(bpy.context.object, name, smooth_by_angle=True)
    obj.data.materials.append(surface)
    return tag(obj, role, location_id)


def sphere(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    surface: Any,
    *,
    role: str,
    location_id: str | None = None,
) -> Any:
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0, location=location)
    obj = prepare_mesh(bpy.context.object, name)
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(surface)
    return tag(obj, role, location_id)


def text(
    name: str,
    body: str,
    location: tuple[float, float, float],
    surface: Any,
    *,
    size: float,
    location_id: str,
) -> None:
    bpy.ops.object.text_add(location=location, rotation=(math.pi / 2.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.data.body = body
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = 0.012
    obj.data.bevel_depth = 0.004
    obj.data.materials.append(surface)
    bpy.ops.object.convert(target="MESH")
    converted = prepare_mesh(bpy.context.object, name)
    tag(converted, "location_sign", location_id)


def pitched_roof(
    name: str,
    x: float,
    y: float,
    width: float,
    depth: float,
    height: float,
    surface: Any,
    *,
    role: str,
    location_id: str | None = None,
) -> None:
    angle = math.radians(27.0)
    slab_width = width * 0.58
    rise = math.sin(angle) * slab_width * 0.5
    for side, sign in (("Left", -1.0), ("Right", 1.0)):
        box(
            name + side,
            (x + sign * width * 0.225, y, height + rise * 0.5),
            (slab_width, depth + 0.28, 0.16),
            surface,
            role=role,
            location_id=location_id,
            bevel=0.025,
            rotation=(0.0, sign * angle, 0.0),
        )
    box(
        name + "Ridge",
        (x, y, height + rise + 0.035),
        (0.13, depth + 0.42, 0.13),
        surface,
        role="roof_detail",
        bevel=0.025,
    )


def facade_windows(
    prefix: str,
    x: float,
    facade_y: float,
    width: float,
    rows: tuple[float, ...],
    columns: int,
    s: dict[str, Any],
    *,
    location_id: str,
) -> None:
    spacing = width / (columns + 1)
    for row, z in enumerate(rows, start=1):
        for column in range(1, columns + 1):
            window_x = x - width * 0.5 + spacing * column
            box(
                f"{prefix}Window{row}_{column}",
                (window_x, facade_y, z),
                (min(0.7, spacing * 0.56), 0.045, 0.62),
                s["window"],
                role="window",
                location_id=location_id,
                bevel=0.025,
            )
            box(
                f"{prefix}WindowSill{row}_{column}",
                (window_x, facade_y - 0.035, z - 0.35),
                (min(0.82, spacing * 0.66), 0.1, 0.08),
                s["white_trim"],
                role="facade_trim",
                location_id=location_id,
                bevel=0.012,
            )
            box(
                f"{prefix}WindowMullionV{row}_{column}",
                (window_x, facade_y - 0.03, z),
                (0.035, 0.035, 0.58),
                s["white_trim"],
                role="window_detail",
            )
            box(
                f"{prefix}WindowMullionH{row}_{column}",
                (window_x, facade_y - 0.032, z),
                (min(0.68, spacing * 0.54), 0.035, 0.035),
                s["white_trim"],
                role="window_detail",
            )


def seaside_house(
    name: str,
    center: tuple[float, float],
    size: tuple[float, float, float],
    wall: Any,
    s: dict[str, Any],
    *,
    location_id: str,
    sign: str | None = None,
) -> None:
    x, y = center
    width, depth, height = size
    box(
        name + "Foundation",
        (x, y, 0.12),
        (width + 0.3, depth + 0.3, 0.24),
        s["foundation"],
        role="building",
        location_id=location_id,
        bevel=0.04,
    )
    box(
        name + "Mass",
        (x, y, height * 0.5 + 0.18),
        (width, depth, height),
        wall,
        role="building",
        location_id=location_id,
        bevel=0.06,
    )
    pitched_roof(
        name + "Roof",
        x,
        y,
        width + 0.25,
        depth + 0.18,
        height + 0.18,
        s["roof_blue"],
        role="roof",
        location_id=location_id,
    )
    box(
        name + "Chimney",
        (x + width * 0.24, y + depth * 0.08, height + 0.72),
        (0.34, 0.34, 0.92),
        s["chimney"],
        role="roof_detail",
        bevel=0.025,
    )
    box(
        name + "ChimneyCap",
        (x + width * 0.24, y + depth * 0.08, height + 1.2),
        (0.42, 0.42, 0.08),
        s["foundation"],
        role="roof_detail",
        bevel=0.018,
    )
    facade_y = y - depth * 0.5 - 0.02
    facade_windows(name, x, facade_y, width, (1.08, 2.02), 2, s, location_id=location_id)
    box(
        name + "Door",
        (x, facade_y - 0.03, 0.82),
        (0.78, 0.1, 1.5),
        s["door"],
        role="entrance",
        location_id=location_id,
        bevel=0.035,
    )
    box(
        name + "Porch",
        (x, facade_y - 0.72, 0.18),
        (2.25, 1.25, 0.24),
        s["white_trim"],
        role="porch",
        location_id=location_id,
        bevel=0.035,
    )
    for index, post_x in enumerate((x - 0.86, x + 0.86), start=1):
        cylinder(
            f"{name}PorchPost{index}",
            (post_x, facade_y - 1.05, 1.22),
            0.065,
            2.08,
            s["white_trim"],
            role="porch",
            location_id=location_id,
            vertices=10,
        )
    box(
        name + "PorchRoof",
        (x, facade_y - 0.74, 2.28),
        (2.35, 1.38, 0.16),
        s["roof_blue"],
        role="porch",
        location_id=location_id,
        bevel=0.03,
    )
    if sign:
        text(
            name + "Text",
            sign,
            (x, facade_y - 0.86, 2.42),
            s["sign_text"],
            size=0.22,
            location_id=location_id,
        )


def commercial_building(
    name: str,
    center: tuple[float, float],
    size: tuple[float, float, float],
    wall: Any,
    s: dict[str, Any],
    *,
    location_id: str,
    sign: str,
    columns: int,
) -> None:
    x, y = center
    width, depth, height = size
    box(
        name + "Mass",
        (x, y, height * 0.5 + 0.12),
        (width, depth, height),
        wall,
        role="building",
        location_id=location_id,
        bevel=0.07,
    )
    box(
        name + "Cornice",
        (x, y, height + 0.18),
        (width + 0.3, depth + 0.26, 0.28),
        s["white_trim"],
        role="roof",
        location_id=location_id,
        bevel=0.04,
    )
    facade_y = y - depth * 0.5 - 0.02
    facade_windows(
        name, x, facade_y, width, (1.72, height - 0.62), columns, s, location_id=location_id
    )
    box(
        name + "Storefront",
        (x, facade_y - 0.035, 0.74),
        (width * 0.72, 0.08, 1.28),
        s["storefront_glass"],
        role="storefront",
        location_id=location_id,
        bevel=0.035,
    )
    storefront_width = width * 0.72
    for side, frame_x in (
        ("Left", x - storefront_width * 0.5),
        ("Right", x + storefront_width * 0.5),
    ):
        box(
            name + "StorefrontFrame" + side,
            (frame_x, facade_y - 0.085, 0.74),
            (0.07, 0.06, 1.4),
            s["white_trim"],
            role="storefront_detail",
            bevel=0.012,
        )
    box(
        name + "StorefrontDoor",
        (x, facade_y - 0.09, 0.66),
        (0.68, 0.07, 1.32),
        s["door"],
        role="storefront_detail",
        bevel=0.025,
    )
    box(
        name + "Awning",
        (x, facade_y - 0.38, 1.5),
        (width * 0.8, 0.7, 0.14),
        s["awning"],
        role="awning",
        location_id=location_id,
        bevel=0.035,
    )
    text(
        name + "Text",
        sign,
        (x, facade_y - 0.12, height - 0.18),
        s["sign_text"],
        size=min(0.32, width * 0.055),
        location_id=location_id,
    )


def tree(name: str, x: float, y: float, s: dict[str, Any], scale: float = 1.0) -> None:
    cylinder(
        name + "Trunk",
        (x, y, 0.68 * scale),
        0.13 * scale,
        1.36 * scale,
        s["bark"],
        role="environment_tree",
        vertices=10,
    )
    for index, (dx, dy, dz) in enumerate(
        ((-0.22, 0.0, 1.55), (0.22, 0.04, 1.66), (0.0, -0.14, 2.02)), start=1
    ):
        sphere(
            name + f"Canopy{index}",
            (x + dx * scale, y + dy * scale, dz * scale),
            (0.58 * scale, 0.52 * scale, 0.64 * scale),
            s["foliage_alt"] if index == 2 else s["foliage"],
            role="environment_tree",
        )


def street_lamp(name: str, x: float, y: float, s: dict[str, Any]) -> None:
    cylinder(name + "Pole", (x, y, 1.15), 0.04, 2.3, s["metal"], role="street_lamp", vertices=8)
    box(
        name + "Lantern",
        (x, y, 2.3),
        (0.28, 0.28, 0.42),
        s["lamp_glow"],
        role="street_lamp",
        bevel=0.035,
    )


def street_bench(name: str, x: float, y: float, rotation: float, s: dict[str, Any]) -> None:
    for suffix, location, dimensions, surface in (
        ("Seat", (x, y, 0.48), (1.25, 0.42, 0.11), s["bench_wood"]),
        ("Back", (x, y + 0.16, 0.78), (1.25, 0.09, 0.52), s["bench_wood"]),
        ("LeftLeg", (x - 0.43, y, 0.24), (0.08, 0.32, 0.48), s["metal"]),
        ("RightLeg", (x + 0.43, y, 0.24), (0.08, 0.32, 0.48), s["metal"]),
    ):
        item = box(
            name + suffix,
            location,
            dimensions,
            surface,
            role="street_furniture",
            bevel=0.025,
        )
        item.rotation_euler.z = rotation
    box(
        name + "Cap",
        (x, y, 2.56),
        (0.38, 0.38, 0.1),
        s["metal"],
        role="street_lamp",
        bevel=0.025,
    )


def merge_objects(
    name: str,
    role: str,
    objects: list[Any],
    *,
    location_id: str | None = None,
) -> None:
    if len(objects) < 2:
        return
    ordered_objects = sorted(objects, key=lambda candidate: candidate.name)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in ordered_objects:
        bpy.context.view_layer.objects.active = obj
        for modifier in list(obj.modifiers):
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        obj.select_set(True)
    active = ordered_objects[0]
    bpy.context.view_layer.objects.active = active
    bpy.ops.object.join()
    active.name = name
    active.data.name = name + "Mesh"
    active["truman_role"] = role
    if location_id:
        active["location_id"] = location_id
    elif "location_id" in active:
        del active["location_id"]


def merge_role(name: str, role: str) -> None:
    objects = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj.get("truman_role") == role
    ]
    merge_objects(name, role, objects)


def merge_location_role(role: str) -> None:
    groups: dict[str, list[Any]] = {}
    for obj in bpy.context.scene.objects:
        location_id = obj.get("location_id")
        if obj.type == "MESH" and obj.get("truman_role") == role and location_id:
            groups.setdefault(str(location_id), []).append(obj)
    for location_id, objects in sorted(groups.items()):
        location_name = "".join(part.title() for part in location_id.replace("_", "-").split("-"))
        role_name = "".join(part.title() for part in role.split("_"))
        merge_objects(
            f"Town{location_name}{role_name}",
            role,
            objects,
            location_id=location_id,
        )


def build_plaza(s: dict[str, Any]) -> None:
    cylinder(
        "TownPlazaPaving",
        (0.0, 0.0, 0.04),
        2.45,
        0.08,
        s["plaza"],
        role="plaza",
        location_id="plaza",
        vertices=32,
    )
    cylinder(
        "TownGazeboFloor",
        (0.0, 0.0, 0.22),
        1.02,
        0.28,
        s["white_trim"],
        role="gazebo",
        location_id="plaza",
        vertices=20,
    )
    for index, angle in enumerate((0.0, math.pi / 2.0, math.pi, math.pi * 1.5), start=1):
        x = math.cos(angle) * 0.78
        y = math.sin(angle) * 0.78
        cylinder(
            f"GazeboPost{index}",
            (x, y, 1.35),
            0.055,
            2.25,
            s["white_trim"],
            role="gazebo",
            location_id="plaza",
            vertices=10,
        )
    cone(
        "GazeboRoof",
        (0.0, 0.0, 2.65),
        1.26,
        0.28,
        0.58,
        s["roof_blue"],
        role="gazebo",
        location_id="plaza",
        vertices=12,
    )
    cylinder(
        "ClockTower",
        (0.0, 0.0, 3.25),
        0.28,
        1.25,
        s["white_trim"],
        role="clock_tower",
        location_id="plaza",
        vertices=12,
    )
    for side, (x, y, rotation) in enumerate(
        (
            (0.0, -0.295, (math.pi / 2.0, 0.0, 0.0)),
            (0.295, 0.0, (0.0, math.pi / 2.0, 0.0)),
        ),
        start=1,
    ):
        cylinder(
            f"ClockFace{side}",
            (x, y, 3.45),
            0.19,
            0.035,
            s["clock"],
            role="clock_tower",
            location_id="plaza",
            vertices=20,
            rotation=rotation,
        )
    for hand_name, hand_rotation, hand_height in (
        ("Minute", math.radians(-32.0), 0.24),
        ("Hour", math.radians(58.0), 0.16),
    ):
        box(
            "ClockFront" + hand_name,
            (0.0, -0.322, 3.45),
            (0.025, 0.025, hand_height),
            s["metal"],
            role="clock_tower",
            location_id="plaza",
            bevel=0.008,
            rotation=(0.0, hand_rotation, 0.0),
        )
        box(
            "ClockSide" + hand_name,
            (0.322, 0.0, 3.45),
            (0.025, 0.025, hand_height),
            s["metal"],
            role="clock_tower",
            location_id="plaza",
            bevel=0.008,
            rotation=(hand_rotation, 0.0, 0.0),
        )
    sphere(
        "ClockFinial",
        (0.0, 0.0, 4.0),
        (0.12, 0.12, 0.16),
        s["gold"],
        role="clock_tower",
        location_id="plaza",
    )


def build_town(s: dict[str, Any]) -> None:
    box("TownGround", (0.0, 0.0, -0.18), (29.0, 21.0, 0.3), s["ground"], role="ground", bevel=0.22)
    box("BacklotOcean", (0.0, 9.0, -0.04), (29.0, 3.0, 0.08), s["ocean"], role="ocean", bevel=0.08)
    box("Seawall", (0.0, 7.42, 0.34), (28.2, 0.34, 0.68), s["seawall"], role="seawall", bevel=0.06)
    for road_name, location, dimensions in (
        ("MainStreet", (0.0, 0.0, 0.01), (25.0, 1.45, 0.09)),
        ("WestResidentialRoad", (-4.5, 0.0, 0.015), (1.35, 14.0, 0.1)),
        ("EastHarborRoad", (3.0, 0.0, 0.015), (1.35, 14.0, 0.1)),
        ("MarketStreet", (0.0, 3.0, 0.02), (19.0, 1.25, 0.11)),
        ("BayAvenue", (0.0, -5.0, 0.02), (19.0, 1.25, 0.11)),
    ):
        box(road_name, location, dimensions, s["road"], role="road", bevel=0.025)
    for index, x in enumerate(range(-11, 12, 2), start=1):
        box(
            f"MainStreetDash{index}",
            (float(x), 0.0, 0.072),
            (0.85, 0.055, 0.022),
            s["road_marking"],
            role="road_marking",
            bevel=0.008,
        )
    for crossing, crossing_x in enumerate((-4.5, 3.0), start=1):
        for stripe, offset in enumerate((-0.42, -0.14, 0.14, 0.42), start=1):
            box(
                f"Crosswalk{crossing}Stripe{stripe}",
                (crossing_x + offset, 0.0, 0.074),
                (0.14, 1.08, 0.025),
                s["road_marking"],
                role="road_marking",
                bevel=0.006,
            )
    for walk_name, location, dimensions in (
        ("MainWalkNorth", (0.0, 1.0, 0.07), (25.0, 0.48, 0.13)),
        ("MainWalkSouth", (0.0, -1.0, 0.07), (25.0, 0.48, 0.13)),
        ("MarketWalkNorth", (0.0, 3.9, 0.07), (19.0, 0.45, 0.13)),
        ("MarketWalkSouth", (0.0, 2.1, 0.07), (19.0, 0.45, 0.13)),
        ("Promenade", (0.0, 6.9, 0.08), (27.0, 0.7, 0.15)),
    ):
        box(walk_name, location, dimensions, s["sidewalk"], role="sidewalk", bevel=0.025)

    build_plaza(s)
    seaside_house(
        "TrumanHome",
        (-7.0, -3.0),
        (4.2, 3.2, 2.7),
        s["home_wall"],
        s,
        location_id="apartment",
        sign="LANCASTER HOUSE",
    )
    seaside_house(
        "BachelorHouse",
        (-7.0, 2.0),
        (3.8, 3.0, 2.55),
        s["bachelor_wall"],
        s,
        location_id="bachelor-apt",
        sign="BACHELOR COURT",
    )
    commercial_building(
        "CornerCafe",
        (-2.0, 3.0),
        (3.8, 2.7, 2.8),
        s["cafe_wall"],
        s,
        location_id="cafe",
        sign="CORNER CAFE",
        columns=3,
    )
    commercial_building(
        "HarborMall",
        (4.0, 3.0),
        (5.6, 3.1, 3.5),
        s["mall_wall"],
        s,
        location_id="mall",
        sign="HARBOR MALL",
        columns=4,
    )
    commercial_building(
        "HarborOffice",
        (6.0, -2.0),
        (4.2, 3.0, 3.2),
        s["office_wall"],
        s,
        location_id="office",
        sign="HARBOR OFFICE",
        columns=3,
    )
    commercial_building(
        "BayHospital",
        (3.0, -5.0),
        (5.4, 3.2, 3.45),
        s["hospital_wall"],
        s,
        location_id="hospital",
        sign="BAY HOSPITAL",
        columns=4,
    )
    box(
        "HospitalCrossVertical",
        (3.0, -6.64, 2.18),
        (0.18, 0.08, 0.82),
        s["hospital_cross"],
        role="location_sign",
        location_id="hospital",
        bevel=0.02,
    )
    box(
        "HospitalCrossHorizontal",
        (3.0, -6.68, 2.18),
        (0.64, 0.08, 0.18),
        s["hospital_cross"],
        role="location_sign",
        location_id="hospital",
        bevel=0.02,
    )

    background_houses = (
        ("NorthHouse1", -11.5, 5.4, s["pastel_yellow"]),
        ("NorthHouse2", -7.5, 5.5, s["pastel_blue"]),
        ("NorthHouse3", 9.6, 5.4, s["pastel_pink"]),
        ("SouthHouse1", -11.6, -5.0, s["pastel_blue"]),
        ("SouthHouse2", -8.0, -6.0, s["pastel_yellow"]),
        ("EastHouse", 11.4, -1.8, s["pastel_pink"]),
    )
    for house_name, house_x, house_y, wall in background_houses:
        seaside_house(
            house_name, (house_x, house_y), (3.0, 2.5, 2.25), wall, s, location_id="town-background"
        )

    tree_positions = (
        (-13.0, -2.2),
        (-12.7, 1.8),
        (-10.2, -1.5),
        (-9.5, 1.0),
        (-5.8, -6.8),
        (-2.5, -6.8),
        (0.0, -6.9),
        (7.0, -6.7),
        (10.0, -5.5),
        (12.4, -4.5),
        (12.6, 2.2),
        (11.6, 6.0),
        (7.0, 6.1),
        (0.0, 6.1),
        (-3.5, 6.0),
        (-12.0, 6.2),
        (-2.8, 1.4),
        (1.8, 1.6),
        (7.8, 1.3),
    )
    for index, (tree_x, tree_y) in enumerate(tree_positions, start=1):
        tree(f"TownTree{index}", tree_x, tree_y, s, 0.82 + 0.08 * (index % 3))
    for index, (lamp_x, lamp_y) in enumerate(
        (
            (-9.0, 0.9),
            (-6.0, 0.9),
            (-2.0, 1.0),
            (2.0, 1.0),
            (6.0, 0.9),
            (9.0, 0.9),
            (-3.5, 4.0),
            (1.0, 4.0),
            (6.8, 4.0),
            (0.0, 6.6),
        ),
        start=1,
    ):
        street_lamp(f"TownLamp{index}", lamp_x, lamp_y, s)

    for index, (bench_x, bench_y, rotation) in enumerate(
        (
            (-1.75, -1.75, 0.0),
            (1.75, 1.75, math.pi),
            (-5.8, 1.35, 0.0),
            (8.1, 1.35, 0.0),
        ),
        start=1,
    ):
        street_bench(f"TownBench{index}", bench_x, bench_y, rotation, s)

    for index, rail_x in enumerate(range(-12, 13, 2), start=1):
        box(
            f"PromenadeRailPost{index}",
            (float(rail_x), 7.17, 0.67),
            (0.075, 0.075, 1.02),
            s["metal"],
            role="promenade_detail",
            bevel=0.018,
        )
    for level, rail_z in enumerate((0.52, 1.03), start=1):
        box(
            f"PromenadeRail{level}",
            (0.0, 7.17, rail_z),
            (25.0, 0.07, 0.07),
            s["metal"],
            role="promenade_detail",
            bevel=0.018,
        )

    box(
        "StudioBoundaryNorth",
        (0.0, 10.25, 1.35),
        (29.0, 0.14, 2.7),
        s["dome_wall"],
        role="studio_boundary",
        bevel=0.08,
    )
    for index, x in enumerate(range(-12, 13, 3), start=1):
        box(
            f"BoundarySeam{index}",
            (float(x), 10.17, 1.35),
            (0.035, 0.03, 2.7),
            s["boundary_seam"],
            role="studio_boundary",
        )

    for merged_name, role in (
        ("TownTrees", "environment_tree"),
        ("TownStreetLamps", "street_lamp"),
        ("TownRoads", "road"),
        ("TownSidewalks", "sidewalk"),
        ("TownRoadMarkings", "road_marking"),
        ("TownWindowDetails", "window_detail"),
        ("TownStorefrontDetails", "storefront_detail"),
        ("TownRoofDetails", "roof_detail"),
        ("TownStreetFurniture", "street_furniture"),
        ("TownPromenadeDetails", "promenade_detail"),
        ("TownBackgroundBoundary", "studio_boundary"),
    ):
        merge_role(merged_name, role)
    for role in ("building", "roof", "window", "facade_trim", "porch"):
        merge_location_role(role)


def validate_scene() -> None:
    invalid_meshes: list[str] = []
    empty_meshes: list[str] = []
    seen_meshes: set[int] = set()
    for obj in bpy.context.scene.objects:
        if not all(math.isfinite(value) for row in obj.matrix_world for value in row):
            raise RuntimeError(f"object has a non-finite transform: {obj.name}")
        if obj.type != "MESH" or obj.data.as_pointer() in seen_meshes:
            continue
        seen_meshes.add(obj.data.as_pointer())
        if not obj.data.polygons:
            empty_meshes.append(obj.data.name)
        if obj.data.validate(verbose=True) or obj.data.validate_material_indices():
            invalid_meshes.append(obj.data.name)
    if empty_meshes or invalid_meshes:
        raise RuntimeError(
            "scene mesh validation failed: "
            f"empty={sorted(empty_meshes)}, repaired={sorted(invalid_meshes)}"
        )


def evaluated_scene_stats() -> dict[str, int]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    vertices = 0
    polygons = 0
    triangles = 0
    for obj in mesh_objects:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            vertices += len(mesh.vertices)
            polygons += len(mesh.polygons)
            triangles += len(mesh.loop_triangles)
        finally:
            evaluated.to_mesh_clear()
    return {
        "objects": len(bpy.context.scene.objects),
        "meshes": len(mesh_objects),
        "materials": len(bpy.data.materials),
        "vertices": vertices,
        "polygons": polygons,
        "triangles": triangles,
    }


def build_scene() -> dict[str, int]:
    s: dict[str, Any] = {
        "ground": material("TW_TownGround", (0.32, 0.46, 0.3, 1.0)),
        "road": material("TW_TownRoad", (0.14, 0.18, 0.18, 1.0)),
        "sidewalk": material("TW_TownSidewalk", (0.73, 0.69, 0.59, 1.0)),
        "ocean": material("TW_Ocean", (0.22, 0.54, 0.64, 0.72), roughness=0.2),
        "seawall": material("TW_Seawall", (0.57, 0.55, 0.49, 1.0)),
        "plaza": material("TW_Plaza", (0.67, 0.56, 0.43, 1.0)),
        "foundation": material("TW_Foundation", (0.4, 0.39, 0.34, 1.0)),
        "white_trim": material("TW_WhiteTrim", (0.88, 0.86, 0.76, 1.0)),
        "roof_blue": material("TW_RoofBlue", (0.13, 0.31, 0.35, 1.0)),
        "home_wall": material("TW_HomeWall", (0.7, 0.57, 0.39, 1.0)),
        "bachelor_wall": material("TW_BachelorWall", (0.51, 0.65, 0.61, 1.0)),
        "cafe_wall": material("TW_CafeWall", (0.75, 0.45, 0.34, 1.0)),
        "mall_wall": material("TW_MallWall", (0.55, 0.66, 0.62, 1.0)),
        "office_wall": material("TW_OfficeWall", (0.45, 0.58, 0.62, 1.0)),
        "hospital_wall": material("TW_HospitalWall", (0.78, 0.8, 0.73, 1.0)),
        "pastel_yellow": material("TW_PastelYellow", (0.72, 0.62, 0.42, 1.0)),
        "pastel_blue": material("TW_PastelBlue", (0.43, 0.61, 0.65, 1.0)),
        "pastel_pink": material("TW_PastelPink", (0.73, 0.48, 0.46, 1.0)),
        "window": material("TW_Window", (0.42, 0.66, 0.68, 0.62), roughness=0.18),
        "storefront_glass": material("TW_StorefrontGlass", (0.3, 0.58, 0.61, 0.5), roughness=0.14),
        "door": material("TW_Door", (0.17, 0.3, 0.3, 1.0)),
        "awning": material("TW_Awning", (0.66, 0.2, 0.16, 1.0)),
        "sign_text": material("TW_SignText", (0.9, 0.84, 0.67, 1.0)),
        "hospital_cross": material("TW_HospitalCross", (0.68, 0.12, 0.12, 1.0)),
        "bark": material("TW_Bark", (0.3, 0.2, 0.12, 1.0)),
        "foliage": material("TW_Foliage", (0.18, 0.39, 0.21, 1.0)),
        "foliage_alt": material("TW_FoliageAlt", (0.3, 0.48, 0.25, 1.0)),
        "metal": material("TW_Metal", (0.07, 0.1, 0.11, 1.0), metallic=0.45),
        "lamp_glow": material("TW_LampGlow", (0.92, 0.72, 0.31, 1.0), roughness=0.32),
        "clock": material("TW_Clock", (0.92, 0.88, 0.68, 1.0)),
        "gold": material("TW_Gold", (0.72, 0.47, 0.12, 1.0), metallic=0.4),
        "dome_wall": material("TW_DomeWall", (0.45, 0.62, 0.69, 0.38), roughness=0.28),
        "boundary_seam": material("TW_BoundarySeam", (0.25, 0.4, 0.45, 0.65)),
        "chimney": material("TW_Chimney", (0.48, 0.24, 0.18, 1.0)),
        "road_marking": material("TW_RoadMarking", (0.88, 0.82, 0.59, 1.0), roughness=0.7),
        "bench_wood": material("TW_BenchWood", (0.43, 0.25, 0.13, 1.0), roughness=0.72),
    }
    build_town(s)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    validate_scene()
    return evaluated_scene_stats()


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
    stats = build_scene()
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
                "semantic_alignment": {
                    "plaza": [0.0, 0.0, 0.0],
                    "apartment": [-7.0, 0.0, 3.0],
                    "bachelor-apt": [-7.0, 0.0, -2.0],
                    "cafe": [-2.0, 0.0, -3.0],
                    "mall": [4.0, 0.0, -3.0],
                    "office": [6.0, 0.0, 2.0],
                    "hospital": [3.0, 0.0, 5.0],
                },
                "environment_bounds_meters": [29.0, 21.0],
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
