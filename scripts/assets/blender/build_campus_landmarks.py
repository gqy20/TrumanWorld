"""Build the authored campus landmarks aligned to the semantic Godot map."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import bpy

REQUIRED_BLENDER = (5, 2)
ASSET_ID = "campus_world/campus_landmarks"


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


def box(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    surface: Any,
    *,
    role: str,
    location_id: str | None = None,
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
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
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
    obj = bpy.context.object
    obj.name = name
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
    obj.data.extrude = 0.014
    obj.data.bevel_depth = 0.004
    obj.data.materials.append(surface)
    bpy.ops.object.convert(target="MESH")
    tag(bpy.context.object, "sign", location_id)


def bench(name: str, x: float, y: float, rotation: float, wood: Any, metal: Any) -> None:
    seat = box(name + "Seat", (x, y, 0.42), (1.2, 0.38, 0.11), wood, role="bench", bevel=0.035)
    back = box(
        name + "Back",
        (x, y + 0.16, 0.7),
        (1.2, 0.08, 0.52),
        wood,
        role="bench",
        bevel=0.025,
    )
    seat.rotation_euler.z = rotation
    back.rotation_euler.z = rotation
    for index, offset in enumerate((-0.42, 0.42), start=1):
        leg = box(
            name + f"Leg{index}",
            (x + offset, y, 0.21),
            (0.07, 0.3, 0.42),
            metal,
            role="bench",
        )
        leg.rotation_euler.z = rotation


def chair(name: str, x: float, y: float, wood: Any, metal: Any) -> None:
    box(name + "Seat", (x, y, 0.44), (0.46, 0.46, 0.1), wood, role="chair", bevel=0.025)
    box(
        name + "Back",
        (x, y + 0.19, 0.72),
        (0.46, 0.08, 0.52),
        wood,
        role="chair",
        bevel=0.02,
    )
    for index, (dx, dy) in enumerate(
        ((-0.16, -0.16), (0.16, -0.16), (-0.16, 0.16), (0.16, 0.16)), start=1
    ):
        cylinder(
            name + f"Leg{index}",
            (x + dx, y + dy, 0.21),
            0.022,
            0.42,
            metal,
            role="chair",
            vertices=8,
        )


def tree(name: str, x: float, y: float, s: dict[str, Any], *, scale: float = 1.0) -> None:
    cylinder(
        name + "Trunk",
        (x, y, 0.62 * scale),
        0.13 * scale,
        1.24 * scale,
        s["bark"],
        role="environment_tree",
        vertices=10,
    )
    for index, (dx, dy, dz, canopy_scale) in enumerate(
        (
            (-0.2, 0.0, 1.45, (0.55, 0.48, 0.62)),
            (0.22, 0.04, 1.55, (0.58, 0.5, 0.68)),
            (0.0, -0.14, 1.9, (0.52, 0.48, 0.6)),
        ),
        start=1,
    ):
        sphere(
            name + f"Canopy{index}",
            (x + dx * scale, y + dy * scale, dz * scale),
            tuple(value * scale for value in canopy_scale),
            s["tree_canopy_alt"] if index == 2 else s["tree_canopy"],
            role="environment_tree",
        )


def lamp(name: str, x: float, y: float, s: dict[str, Any]) -> None:
    cylinder(
        name + "Base",
        (x, y, 0.14),
        0.11,
        0.28,
        s["metal"],
        role="environment_lamp",
        vertices=10,
    )
    cylinder(
        name + "Pole",
        (x, y, 1.05),
        0.035,
        1.8,
        s["metal"],
        role="environment_lamp",
        vertices=8,
    )
    cone(
        name + "Shade",
        (x, y, 1.92),
        0.2,
        0.08,
        0.18,
        s["roof"],
        role="environment_lamp",
    )
    sphere(
        name + "Glow",
        (x, y, 1.82),
        (0.11, 0.11, 0.13),
        s["lamp"],
        role="environment_lamp",
    )


def background_building(
    name: str,
    center: tuple[float, float],
    size: tuple[float, float, float],
    wall: Any,
    s: dict[str, Any],
    *,
    window_columns: int,
) -> None:
    x, y = center
    width, depth, height = size
    box(
        name + "Foundation",
        (x, y, 0.12),
        (width + 0.34, depth + 0.34, 0.24),
        s["foundation"],
        role="background_architecture",
        bevel=0.04,
    )
    box(
        name + "Mass",
        (x, y, height * 0.5 + 0.18),
        (width, depth, height),
        wall,
        role="background_architecture",
        bevel=0.08,
    )
    box(
        name + "Roof",
        (x, y, height + 0.3),
        (width + 0.28, depth + 0.28, 0.24),
        s["roof"],
        role="background_architecture",
        bevel=0.055,
    )
    facade_y = y - depth * 0.5 - 0.015
    window_spacing = width / (window_columns + 1)
    for row, z in enumerate((height * 0.42, height * 0.72), start=1):
        for column in range(1, window_columns + 1):
            window_x = x - width * 0.5 + window_spacing * column
            box(
                f"{name}Window{row}_{column}",
                (window_x, facade_y, z),
                (min(0.62, window_spacing * 0.58), 0.045, 0.52),
                s["window_glow"],
                role="background_window",
                bevel=0.025,
            )
    box(
        name + "Door",
        (x, facade_y - 0.02, 0.74),
        (0.78, 0.08, 1.42),
        s["door"],
        role="background_entrance",
        bevel=0.035,
    )
    box(
        name + "Awning",
        (x, facade_y - 0.24, 1.52),
        (1.32, 0.5, 0.12),
        s["roof"],
        role="background_entrance",
        bevel=0.035,
    )


def merge_environment_role(name: str, role: str) -> None:
    objects = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj.get("truman_role") == role
    ]
    if len(objects) < 2:
        return
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        bpy.context.view_layer.objects.active = obj
        for modifier in list(obj.modifiers):
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        obj.select_set(True)
    active = objects[0]
    bpy.context.view_layer.objects.active = active
    bpy.ops.object.join()
    active.name = name
    active["truman_role"] = role


def build_environment(s: dict[str, Any]) -> None:
    box(
        "CampusGround",
        (0.0, 0.0, -0.16),
        (25.5, 17.5, 0.28),
        s["campus_ground"],
        role="environment_ground",
        bevel=0.18,
    )
    box(
        "SouthBoulevard",
        (0.0, -6.55, 0.01),
        (24.0, 1.9, 0.08),
        s["asphalt"],
        role="environment_road",
    )
    for sidewalk_index, sidewalk_y in enumerate((-5.25, -7.78), start=1):
        box(
            f"SouthSidewalk{sidewalk_index}",
            (0.0, sidewalk_y, 0.055),
            (24.0, 0.58, 0.12),
            s["sidewalk"],
            role="environment_sidewalk",
            bevel=0.025,
        )
    for dash_index, dash_x in enumerate(range(-10, 11, 2), start=1):
        box(
            f"BoulevardLaneMark{dash_index}",
            (float(dash_x), -6.55, 0.065),
            (0.92, 0.07, 0.018),
            s["lane_mark"],
            role="road_marking",
            bevel=0.01,
        )
    for path_name, location, dimensions in (
        ("NorthPromenade", (0.0, 2.0, 0.025), (19.8, 0.72, 0.09)),
        ("QuadSpine", (-3.0, -1.75, 0.03), (0.78, 7.1, 0.1)),
        ("CafeWalk", (2.0, 0.0, 0.035), (6.2, 0.68, 0.11)),
        ("EastGardenWalk", (7.5, -1.8, 0.03), (0.72, 6.7, 0.1)),
        ("WestGardenWalk", (-9.1, -1.25, 0.03), (0.7, 7.7, 0.1)),
    ):
        box(
            path_name,
            location,
            dimensions,
            s["path"],
            role="environment_path",
            bevel=0.035,
        )

    background_building(
        "WestResidenceAnnex",
        (-10.55, 2.85),
        (2.3, 4.3, 3.25),
        s["annex_wall"],
        s,
        window_columns=2,
    )
    background_building(
        "ArtsCenter",
        (8.65, 4.8),
        (5.55, 2.3, 3.55),
        s["arts_wall"],
        s,
        window_columns=5,
    )
    background_building(
        "SouthCommons",
        (-7.65, -3.55),
        (4.25, 2.55, 2.65),
        s["commons_wall"],
        s,
        window_columns=4,
    )
    background_building(
        "GardenPavilion",
        (9.45, -3.35),
        (3.55, 2.35, 2.35),
        s["pavilion_wall"],
        s,
        window_columns=3,
    )

    for pillar_index, pillar_x in enumerate((-4.05, -1.95), start=1):
        box(
            f"CampusEntryPillar{pillar_index}",
            (pillar_x, -5.0, 1.08),
            (0.42, 0.48, 2.16),
            s["gate_stone"],
            role="campus_entrance",
            bevel=0.045,
        )
        box(
            f"CampusEntryCap{pillar_index}",
            (pillar_x, -5.0, 2.2),
            (0.56, 0.62, 0.16),
            s["roof"],
            role="campus_entrance",
            bevel=0.035,
        )
    box(
        "CampusEntryBeam",
        (-3.0, -5.0, 2.02),
        (1.85, 0.3, 0.24),
        s["gate_stone"],
        role="campus_entrance",
        bevel=0.035,
    )
    text(
        "CampusEntryText",
        "TRUMAN CAMPUS",
        (-3.0, -5.17, 2.03),
        s["linen"],
        size=0.19,
        location_id="campus-environment",
    )

    tree_positions = (
        (-11.6, -4.6, 0.9),
        (-10.0, -5.0, 0.82),
        (-5.2, -4.7, 0.96),
        (-0.7, -4.45, 0.86),
        (2.0, -4.5, 1.0),
        (5.5, -4.4, 0.88),
        (11.55, -4.8, 0.92),
        (-11.55, -0.5, 1.04),
        (-10.1, -0.1, 0.84),
        (-8.0, -0.6, 0.9),
        (0.6, -1.25, 0.86),
        (9.1, -0.5, 0.92),
        (11.5, 0.25, 1.02),
        (-11.7, 5.8, 0.94),
        (-8.5, 6.1, 1.08),
        (-5.6, 5.9, 0.88),
        (-3.6, 5.85, 1.0),
        (0.2, 5.85, 0.82),
        (4.9, 6.1, 0.94),
        (11.65, 5.9, 1.08),
    )
    for index, (tree_x, tree_y, tree_scale) in enumerate(tree_positions, start=1):
        tree(f"CampusTree{index}", tree_x, tree_y, s, scale=tree_scale)

    for index, (lamp_x, lamp_y) in enumerate(
        (
            (-8.5, 1.45),
            (-5.2, 1.45),
            (0.5, 1.45),
            (4.8, 1.45),
            (-3.55, -1.55),
            (-3.55, -3.85),
            (2.3, -0.55),
            (6.85, -1.4),
            (6.85, -3.7),
            (-9.55, -2.0),
        ),
        start=1,
    ):
        lamp(f"CampusLamp{index}", lamp_x, lamp_y, s)

    for fence_name, location, dimensions in (
        ("NorthFenceWest", (-8.6, 7.7, 0.35), (7.2, 0.12, 0.7)),
        ("NorthFenceEast", (7.8, 7.7, 0.35), (8.8, 0.12, 0.7)),
        ("WestFenceNorth", (-12.1, 5.5, 0.35), (0.12, 4.5, 0.7)),
        ("WestFenceSouth", (-12.1, -2.0, 0.35), (0.12, 5.7, 0.7)),
        ("EastFenceNorth", (12.1, 5.5, 0.35), (0.12, 4.5, 0.7)),
        ("EastFenceSouth", (12.1, -2.0, 0.35), (0.12, 5.7, 0.7)),
    ):
        box(
            fence_name,
            location,
            dimensions,
            s["fence"],
            role="campus_boundary",
            bevel=0.025,
        )

    for merged_name, role in (
        ("CampusTrees", "environment_tree"),
        ("CampusLamps", "environment_lamp"),
        ("CampusArchitecture", "background_architecture"),
        ("CampusWindows", "background_window"),
        ("CampusBackgroundEntrances", "background_entrance"),
        ("CampusPaths", "environment_path"),
        ("CampusRoadMarkings", "road_marking"),
        ("CampusSidewalks", "environment_sidewalk"),
        ("CampusBoundary", "campus_boundary"),
    ):
        merge_environment_role(merged_name, role)


def shell(
    prefix: str,
    center: tuple[float, float],
    size: tuple[float, float, float],
    wall: Any,
    roof: Any,
    floor: Any,
    *,
    location_id: str,
) -> None:
    x, y = center
    width, depth, height = size
    box(
        prefix + "Floor-col",
        (x, y, 0.06),
        (width, depth, 0.12),
        floor,
        role="floor",
        location_id=location_id,
    )
    box(
        prefix + "BackWall-col",
        (x, y + depth * 0.48, height * 0.5),
        (width, 0.12, height),
        wall,
        role="wall",
        location_id=location_id,
    )
    box(
        prefix + "LeftWall-col",
        (x - width * 0.48, y, height * 0.5),
        (0.12, depth, height),
        wall,
        role="wall",
        location_id=location_id,
    )
    box(
        prefix + "RightPier",
        (x + width * 0.48, y + depth * 0.3, height * 0.5),
        (0.12, depth * 0.38, height),
        wall,
        role="wall",
        location_id=location_id,
    )
    box(
        prefix + "Roof",
        (x, y + depth * 0.31, height + 0.08),
        (width + 0.18, depth * 0.38, 0.16),
        roof,
        role="cutaway_roof",
        location_id=location_id,
        bevel=0.035,
    )


def build_quad(s: dict[str, Any]) -> None:
    x, y = -3.0, 0.0
    cylinder(
        "QuadOuterPlaza",
        (x, y, 0.035),
        2.0,
        0.07,
        s["stone"],
        role="plaza",
        location_id="quad",
        vertices=32,
    )
    cylinder(
        "QuadInnerGarden",
        (x, y, 0.09),
        1.42,
        0.1,
        s["grass"],
        role="garden",
        location_id="quad",
        vertices=32,
    )
    cylinder(
        "FountainBasin",
        (x, y, 0.22),
        0.58,
        0.3,
        s["terracotta"],
        role="fountain",
        location_id="quad",
        vertices=24,
    )
    cylinder(
        "FountainWater",
        (x, y, 0.39),
        0.47,
        0.06,
        s["glass"],
        role="water",
        location_id="quad",
        vertices=24,
    )
    cylinder(
        "FountainColumn",
        (x, y, 0.72),
        0.11,
        0.68,
        s["stone"],
        role="fountain",
        location_id="quad",
        vertices=16,
    )
    cylinder(
        "FountainCap",
        (x, y, 1.04),
        0.3,
        0.08,
        s["glass"],
        role="water",
        location_id="quad",
        vertices=20,
    )
    cone(
        "FountainFinial",
        (x, y, 1.19),
        0.09,
        0.025,
        0.26,
        s["stone"],
        role="fountain",
        location_id="quad",
    )
    cylinder(
        "FountainJet",
        (x, y, 1.32),
        0.018,
        0.32,
        s["water"],
        role="water_jet",
        location_id="quad",
        vertices=8,
    )
    for jet_index, angle in enumerate((0.0, math.pi / 2.0, math.pi, math.pi * 1.5), start=1):
        jet_x = x + math.cos(angle) * 0.2
        jet_y = y + math.sin(angle) * 0.2
        cylinder(
            f"FountainSideJet{jet_index}",
            (jet_x, jet_y, 0.68),
            0.012,
            0.4,
            s["water"],
            role="water_jet",
            location_id="quad",
            vertices=8,
        )
    bench("QuadWest", x - 1.45, y, math.pi / 2.0, s["wood"], s["metal"])
    bench("QuadEast", x + 1.45, y, -math.pi / 2.0, s["wood"], s["metal"])
    for path_index, (px, py, width, depth) in enumerate(
        (
            (x, y - 1.68, 0.82, 0.5),
            (x, y + 1.68, 0.82, 0.5),
            (x - 1.68, y, 0.5, 0.82),
            (x + 1.68, y, 0.5, 0.82),
        ),
        start=1,
    ):
        box(
            f"QuadEntryPaving{path_index}",
            (px, py, 0.085),
            (width, depth, 0.035),
            s["paving"],
            role="path_detail",
            location_id="quad",
            bevel=0.015,
        )
    for index, angle in enumerate(
        (math.pi / 4.0, math.pi * 3.0 / 4.0, math.pi * 5.0 / 4.0, math.pi * 7.0 / 4.0),
        start=1,
    ):
        px = x + math.cos(angle) * 1.67
        py = y + math.sin(angle) * 1.67
        cylinder(
            f"QuadPlanter{index}",
            (px, py, 0.24),
            0.24,
            0.48,
            s["terracotta"],
            role="planter",
            vertices=14,
        )
        for cluster, (dx, dy, dz, scale) in enumerate(
            (
                (-0.12, 0.02, 0.65, (0.24, 0.24, 0.3)),
                (0.12, 0.04, 0.69, (0.25, 0.22, 0.34)),
                (0.0, -0.11, 0.75, (0.27, 0.25, 0.36)),
            ),
            start=1,
        ):
            sphere(
                f"QuadShrub{index}_{cluster}",
                (px + dx, py + dy, dz),
                scale,
                s["foliage"],
                role="plant",
                location_id="quad",
            )


def build_dorm(s: dict[str, Any]) -> None:
    x, y = -7.0, 3.0
    shell(
        "Dorm",
        (x, y),
        (3.55, 2.7, 2.45),
        s["dorm"],
        s["roof"],
        s["floor"],
        location_id="dorm",
    )
    box(
        "DormBaseboard",
        (x, y + 1.22, 0.2),
        (3.4, 0.08, 0.26),
        s["roof"],
        role="trim",
        location_id="dorm",
    )
    for index, dx in enumerate((-0.85, 0.85), start=1):
        box(
            f"DormBed{index}",
            (x + dx, y + 0.35, 0.36),
            (1.25, 0.72, 0.36),
            s["wood"],
            role="bed",
            location_id="dorm",
            bevel=0.04,
        )
        box(
            f"DormMattress{index}",
            (x + dx, y + 0.35, 0.59),
            (1.18, 0.66, 0.14),
            s["linen"],
            role="bed",
            location_id="dorm",
            bevel=0.04,
        )
        box(
            f"DormPillow{index}",
            (x + dx + 0.39, y + 0.35, 0.7),
            (0.3, 0.52, 0.1),
            s["pillow"],
            role="bedding",
            location_id="dorm",
            bevel=0.07,
        )
        box(
            f"DormBlanket{index}",
            (x + dx - 0.19, y + 0.35, 0.69),
            (0.64, 0.67, 0.065),
            s["blanket"],
            role="bedding",
            location_id="dorm",
            bevel=0.035,
        )
        box(
            f"DormDesk{index}",
            (x + dx, y - 0.62, 0.72),
            (1.0, 0.48, 0.1),
            s["wood"],
            role="desk",
            location_id="dorm",
            bevel=0.025,
        )
        for leg_index, (leg_dx, leg_dy) in enumerate(
            ((-0.42, -0.17), (0.42, -0.17), (-0.42, 0.17), (0.42, 0.17)), start=1
        ):
            box(
                f"DormDesk{index}Leg{leg_index}",
                (x + dx + leg_dx, y - 0.62 + leg_dy, 0.36),
                (0.055, 0.055, 0.7),
                s["metal"],
                role="desk",
                location_id="dorm",
            )
        chair(f"DormChair{index}", x + dx, y - 1.05, s["blanket"], s["metal"])
        cylinder(
            f"DormLampStem{index}",
            (x + dx + 0.33, y - 0.62, 0.98),
            0.018,
            0.45,
            s["metal"],
            role="reading_lamp",
            location_id="dorm",
            vertices=8,
        )
        cone(
            f"DormLampShade{index}",
            (x + dx + 0.33, y - 0.62, 1.18),
            0.14,
            0.075,
            0.18,
            s["lamp"],
            role="reading_lamp",
            location_id="dorm",
        )
        box(
            f"DormWindow{index}",
            (x + dx, y + 1.27, 1.62),
            (0.92, 0.035, 0.82),
            s["glass"],
            role="window",
            location_id="dorm",
        )
        box(
            f"DormShelf{index}",
            (x + dx, y + 1.18, 1.02),
            (0.95, 0.22, 0.08),
            s["wood"],
            role="shelf",
            location_id="dorm",
        )
        for book_index in range(4):
            box(
                f"DormBook{index}_{book_index + 1}",
                (x + dx - 0.28 + book_index * 0.17, y + 1.04, 1.18),
                (0.1, 0.14, 0.25 + 0.025 * (book_index % 2)),
                s["books"][book_index % len(s["books"])],
                role="book",
                location_id="dorm",
                bevel=0.008,
            )
    box(
        "DormSign",
        (x, y - 1.34, 2.12),
        (2.35, 0.12, 0.48),
        s["roof"],
        role="sign",
        location_id="dorm",
        bevel=0.06,
    )
    text(
        "DormText",
        "MAPLE DORM",
        (x, y - 1.415, 2.12),
        s["linen"],
        size=0.26,
        location_id="dorm",
    )


def build_lecture_hall(s: dict[str, Any]) -> None:
    x, y = -2.0, 3.0
    shell(
        "Lecture",
        (x, y),
        (4.25, 3.0, 2.65),
        s["lecture"],
        s["roof"],
        s["floor"],
        location_id="lecture-hall",
    )
    box(
        "LectureBoard",
        (x, y + 1.43, 1.72),
        (2.7, 0.045, 0.9),
        s["board"],
        role="board",
        location_id="lecture-hall",
        bevel=0.025,
    )
    for mark_index, (mark_x, mark_z, width) in enumerate(
        ((-0.7, 1.86, 0.72), (0.15, 1.63, 0.95), (0.62, 1.96, 0.38)), start=1
    ):
        box(
            f"LectureBoardMark{mark_index}",
            (x + mark_x, y + 1.402, mark_z),
            (width, 0.012, 0.025),
            s["chalk"],
            role="board_content",
            location_id="lecture-hall",
            bevel=0.006,
        )
    for panel_index, panel_x in enumerate((-1.72, 1.72), start=1):
        for panel_z in (0.75, 1.42, 2.09):
            box(
                f"LectureAcousticPanel{panel_index}_{int(panel_z * 100)}",
                (x + panel_x, y + 1.36, panel_z),
                (0.42, 0.12, 0.48),
                s["acoustic"],
                role="acoustic_panel",
                location_id="lecture-hall",
                bevel=0.025,
            )
    for row, row_y in enumerate((2.8, 2.2, 1.58), start=1):
        step_z = 0.12 * (row - 1)
        box(
            f"LectureTier{row}",
            (x, row_y, 0.08 + step_z * 0.5),
            (3.75, 0.55, 0.12 + step_z),
            s["stone"],
            role="tier",
            location_id="lecture-hall",
        )
        for column, dx in enumerate((-1.25, -0.42, 0.42, 1.25), start=1):
            box(
                f"LectureDesk{row}_{column}",
                (x + dx, row_y, 0.67 + step_z),
                (0.68, 0.32, 0.08),
                s["wood"],
                role="desk",
                location_id="lecture-hall",
                bevel=0.018,
            )
            cylinder(
                f"LectureDeskPedestal{row}_{column}",
                (x + dx, row_y, 0.38 + step_z),
                0.035,
                0.52,
                s["metal"],
                role="desk",
                location_id="lecture-hall",
                vertices=8,
            )
            box(
                f"LectureSeat{row}_{column}",
                (x + dx, row_y - 0.28, 0.48 + step_z),
                (0.52, 0.28, 0.1),
                s["upholstery"],
                role="seat",
                location_id="lecture-hall",
                bevel=0.04,
            )
            box(
                f"LectureSeatBack{row}_{column}",
                (x + dx, row_y - 0.42, 0.72 + step_z),
                (0.52, 0.09, 0.48),
                s["upholstery"],
                role="seat",
                location_id="lecture-hall",
                bevel=0.035,
            )
    box(
        "LectureLectern",
        (x - 1.25, y + 0.92, 0.62),
        (0.5, 0.42, 1.02),
        s["wood"],
        role="lectern",
        location_id="lecture-hall",
        bevel=0.035,
    )
    cylinder(
        "LectureMicrophoneStem",
        (x - 1.25, y + 0.83, 1.27),
        0.014,
        0.38,
        s["metal"],
        role="microphone",
        location_id="lecture-hall",
        vertices=8,
    )
    sphere(
        "LectureMicrophoneHead",
        (x - 1.25, y + 0.83, 1.48),
        (0.055, 0.055, 0.07),
        s["metal"],
        role="microphone",
        location_id="lecture-hall",
    )
    box(
        "LectureProjector",
        (x + 0.6, y + 0.62, 2.27),
        (0.52, 0.38, 0.18),
        s["pillow"],
        role="projector",
        location_id="lecture-hall",
        bevel=0.035,
    )
    box(
        "LectureSign",
        (x, y - 1.5, 2.3),
        (2.75, 0.12, 0.48),
        s["roof"],
        role="sign",
        location_id="lecture-hall",
        bevel=0.06,
    )
    text(
        "LectureText",
        "NORTH HALL",
        (x, y - 1.575, 2.3),
        s["linen"],
        size=0.27,
        location_id="lecture-hall",
    )


def build_library(s: dict[str, Any]) -> None:
    x, y = 3.0, 3.0
    shell(
        "Library",
        (x, y),
        (3.75, 2.9, 2.6),
        s["library"],
        s["roof"],
        s["floor"],
        location_id="library",
    )
    for index, dx in enumerate((-1.15, 0.0, 1.15), start=1):
        box(
            f"LibraryGlass{index}",
            (x + dx, y + 1.38, 1.48),
            (1.05, 0.035, 1.72),
            s["glass"],
            role="window",
            location_id="library",
        )
        box(
            f"LibraryMullion{index}",
            (x + dx - 0.55, y + 1.34, 1.48),
            (0.05, 0.06, 1.82),
            s["roof"],
            role="window_frame",
            location_id="library",
        )
    for shelf_index, shelf_x in enumerate((x - 1.25, x + 1.25), start=1):
        box(
            f"LibraryShelf{shelf_index}",
            (shelf_x, y + 0.55, 1.05),
            (0.48, 0.42, 1.9),
            s["wood"],
            role="bookshelf",
            location_id="library",
            bevel=0.025,
        )
        for row, z in enumerate((0.45, 0.85, 1.25, 1.65), start=1):
            for book_index in range(5):
                book_height = 0.2 + 0.035 * ((book_index + row) % 3)
                box(
                    f"LibraryBook{shelf_index}_{row}_{book_index + 1}",
                    (shelf_x - 0.145 + book_index * 0.073, y + 0.31, z),
                    (0.055, 0.13, book_height),
                    s["books"][(book_index + row) % len(s["books"])],
                    role="book",
                    location_id="library",
                    bevel=0.006,
                )
    box(
        "LibraryReadingRug",
        (x, y - 0.36, 0.135),
        (2.25, 1.25, 0.035),
        s["rug"],
        role="rug",
        location_id="library",
        bevel=0.055,
    )
    box(
        "LibraryReadingTable",
        (x, y - 0.35, 0.73),
        (1.65, 0.7, 0.1),
        s["wood"],
        role="table",
        location_id="library",
        bevel=0.035,
    )
    for leg_index, (dx, dy) in enumerate(
        ((-0.68, -0.24), (0.68, -0.24), (-0.68, 0.24), (0.68, 0.24)), start=1
    ):
        box(
            f"LibraryTableLeg{leg_index}",
            (x + dx, y - 0.35 + dy, 0.4),
            (0.07, 0.07, 0.62),
            s["metal"],
            role="table",
            location_id="library",
        )
    for lamp_index, lamp_x in enumerate((x - 0.42, x + 0.42), start=1):
        cylinder(
            f"LibraryLampStem{lamp_index}",
            (lamp_x, y - 0.35, 1.0),
            0.016,
            0.48,
            s["metal"],
            role="reading_lamp",
            location_id="library",
            vertices=8,
        )
        cone(
            f"LibraryLampShade{lamp_index}",
            (lamp_x, y - 0.35, 1.22),
            0.16,
            0.085,
            0.2,
            s["lamp"],
            role="reading_lamp",
            location_id="library",
        )
    for index, (dx, dy) in enumerate(
        ((-0.62, -0.72), (0.62, -0.72), (-0.62, 0.05), (0.62, 0.05)), start=1
    ):
        chair(f"LibraryChair{index}", x + dx, y + dy, s["wood"], s["metal"])
    box(
        "LibrarySign",
        (x, y - 1.45, 2.28),
        (2.45, 0.12, 0.48),
        s["roof"],
        role="sign",
        location_id="library",
        bevel=0.06,
    )
    text(
        "LibraryText",
        "GLASS LIBRARY",
        (x, y - 1.525, 2.28),
        s["linen"],
        size=0.24,
        location_id="library",
    )


def build_landmarks() -> dict[str, int]:
    surfaces: dict[str, Any] = {
        "campus_ground": material("TW_CampusGround", (0.28, 0.39, 0.25, 1.0)),
        "asphalt": material("TW_Asphalt", (0.105, 0.12, 0.12, 1.0)),
        "sidewalk": material("TW_Sidewalk", (0.6, 0.58, 0.51, 1.0)),
        "lane_mark": material("TW_LaneMark", (0.88, 0.77, 0.38, 1.0)),
        "path": material("TW_Path", (0.68, 0.62, 0.5, 1.0)),
        "foundation": material("TW_Foundation", (0.34, 0.35, 0.32, 1.0)),
        "annex_wall": material("TW_AnnexWall", (0.48, 0.36, 0.27, 1.0)),
        "arts_wall": material("TW_ArtsWall", (0.34, 0.43, 0.44, 1.0)),
        "commons_wall": material("TW_CommonsWall", (0.48, 0.49, 0.38, 1.0)),
        "pavilion_wall": material("TW_PavilionWall", (0.35, 0.48, 0.43, 1.0)),
        "window_glow": material("TW_WindowGlow", (0.72, 0.78, 0.68, 1.0), roughness=0.3),
        "door": material("TW_Door", (0.15, 0.2, 0.2, 1.0)),
        "gate_stone": material("TW_GateStone", (0.51, 0.45, 0.36, 1.0)),
        "fence": material("TW_Fence", (0.18, 0.23, 0.22, 1.0), metallic=0.25),
        "bark": material("TW_Bark", (0.29, 0.19, 0.12, 1.0)),
        "tree_canopy": material("TW_TreeCanopy", (0.18, 0.36, 0.2, 1.0)),
        "tree_canopy_alt": material("TW_TreeCanopyAlt", (0.26, 0.43, 0.24, 1.0)),
        "stone": material("TW_Stone", (0.58, 0.55, 0.47, 1.0)),
        "paving": material("TW_Paving", (0.7, 0.65, 0.54, 1.0)),
        "grass": material("TW_Grass", (0.23, 0.42, 0.26, 1.0)),
        "foliage": material("TW_Foliage", (0.16, 0.34, 0.19, 1.0)),
        "terracotta": material("TW_Terracotta", (0.62, 0.25, 0.14, 1.0)),
        "glass": material("TW_Glass", (0.36, 0.62, 0.68, 0.42), roughness=0.18),
        "water": material("TW_Water", (0.3, 0.68, 0.78, 0.66), roughness=0.12),
        "wood": material("TW_Wood", (0.36, 0.21, 0.11, 1.0), roughness=0.72),
        "metal": material("TW_Metal", (0.06, 0.075, 0.08, 1.0), roughness=0.36, metallic=0.55),
        "roof": material("TW_Roof", (0.11, 0.23, 0.22, 1.0)),
        "floor": material("TW_Floor", (0.82, 0.76, 0.63, 1.0)),
        "linen": material("TW_Linen", (0.9, 0.84, 0.72, 1.0)),
        "pillow": material("TW_Pillow", (0.92, 0.9, 0.82, 1.0)),
        "blanket": material("TW_Blanket", (0.22, 0.42, 0.48, 1.0)),
        "lamp": material("TW_Lamp", (0.9, 0.67, 0.24, 1.0), roughness=0.45),
        "dorm": material("TW_Dorm", (0.57, 0.42, 0.29, 1.0)),
        "lecture": material("TW_Lecture", (0.43, 0.52, 0.42, 1.0)),
        "acoustic": material("TW_Acoustic", (0.56, 0.35, 0.24, 1.0)),
        "upholstery": material("TW_Upholstery", (0.24, 0.31, 0.33, 1.0)),
        "chalk": material("TW_Chalk", (0.86, 0.88, 0.75, 1.0)),
        "library": material("TW_Library", (0.42, 0.54, 0.58, 1.0)),
        "rug": material("TW_Rug", (0.56, 0.24, 0.18, 1.0)),
        "board": material("TW_Board", (0.055, 0.14, 0.12, 1.0)),
    }
    surfaces["books"] = [
        material("TW_BooksRed", (0.54, 0.19, 0.15, 1.0)),
        material("TW_BooksBlue", (0.18, 0.31, 0.45, 1.0)),
        material("TW_BooksGold", (0.62, 0.43, 0.16, 1.0)),
    ]
    build_environment(surfaces)
    build_quad(surfaces)
    build_dorm(surfaces)
    build_lecture_hall(surfaces)
    build_library(surfaces)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    meshes = [obj.data for obj in bpy.context.scene.objects if obj.type == "MESH"]
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
    stats = build_landmarks()
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
                    "quad": [-3.0, 0.0, 0.0],
                    "dorm": [-7.0, 0.0, -3.0],
                    "lecture-hall": [-2.0, 0.0, -3.0],
                    "library": [3.0, 0.0, -3.0],
                },
                "environment_bounds_meters": [25.5, 17.5],
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
