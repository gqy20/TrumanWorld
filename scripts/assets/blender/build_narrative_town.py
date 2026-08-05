"""Build the authored seaside town for the narrative_world scenario."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import bpy
from mathutils import Matrix

REQUIRED_BLENDER = (5, 2)
ASSET_ID = "narrative_world/seaside_town"
CORE_WIDTH = 44.0
CORE_DEPTH = 34.0
VISUAL_BUFFER_WIDTH = 180.0
VISUAL_BUFFER_DEPTH = 110.0
COAST_INLAND_EDGE_Y = 16.0
OCEAN_NEAR_EDGE_Y = 12.0
HORIZON_OCEAN_WIDTH = 300.0
HORIZON_OCEAN_DEPTH = 240.0
STUDIO_BOUNDARY_Y = OCEAN_NEAR_EDGE_Y + HORIZON_OCEAN_DEPTH - 3.0


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


def tag(
    obj: Any,
    role: str,
    location_id: str | None = None,
    semantic_id: str | None = None,
) -> Any:
    obj["truman_role"] = role
    if location_id:
        obj["location_id"] = location_id
    if semantic_id:
        obj["semantic_id"] = semantic_id
    return obj


def rotate_new_objects(
    existing_names: set[str],
    center: tuple[float, float],
    heading: float,
) -> None:
    """Rotate a generated building as one local assembly around its ground pivot."""
    if math.isclose(heading, 0.0, abs_tol=1e-6):
        return
    pivot = Matrix.Translation((center[0], center[1], 0.0))
    transform = pivot @ Matrix.Rotation(heading, 4, "Z") @ pivot.inverted()
    for obj in bpy.context.scene.objects:
        if obj.name not in existing_names:
            obj.matrix_world = transform @ obj.matrix_world


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
    semantic_id: str | None = None,
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
    return tag(obj, role, location_id, semantic_id)


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


def torus(
    name: str,
    location: tuple[float, float, float],
    major_radius: float,
    minor_radius: float,
    surface: Any,
    *,
    role: str,
    location_id: str | None = None,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Any:
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=20,
        minor_segments=8,
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
    semantic_id: str | None = None,
) -> Any:
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0, location=location)
    obj = prepare_mesh(bpy.context.object, name)
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(surface)
    return tag(obj, role, location_id, semantic_id)


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
    heading: float = 0.0,
) -> None:
    existing_names = set(bpy.data.objects.keys())
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
    rotate_new_objects(existing_names, center, heading)


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
    heading: float = 0.0,
) -> None:
    existing_names = set(bpy.data.objects.keys())
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
        name,
        x,
        facade_y,
        width,
        (1.72, height - 0.62),
        columns,
        s,
        location_id=location_id,
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
    for trim_index, trim_x in enumerate((x - width * 0.43, x + width * 0.43), start=1):
        box(
            f"{name}FacadePilaster{trim_index}",
            (trim_x, facade_y - 0.04, height * 0.48),
            (0.16, 0.15, height * 0.9),
            s["white_trim"],
            role="facade_trim",
            location_id=location_id,
            bevel=0.02,
        )
    for unit_index, unit_x in enumerate((x - width * 0.22, x + width * 0.22), start=1):
        box(
            f"{name}RoofUnit{unit_index}",
            (unit_x, y + depth * 0.12, height + 0.48),
            (0.72, 0.62, 0.52),
            s["appliance"],
            role="rooftop_detail",
            location_id=location_id,
            bevel=0.06,
        )
    text(
        name + "Text",
        sign,
        (x, facade_y - 0.12, height - 0.18),
        s["sign_text"],
        size=min(0.32, width * 0.055),
        location_id=location_id,
    )
    rotate_new_objects(existing_names, center, heading)


def background_house_lod(
    name: str,
    center: tuple[float, float],
    wall: Any,
    s: dict[str, Any],
    *,
    heading: float,
) -> None:
    """Build a low-cost silhouette house for the non-interactive visual buffer."""
    existing_names = set(bpy.data.objects.keys())
    x, y = center
    width, depth, height = (3.3, 2.45, 2.25)
    box(
        name + "Mass",
        (x, y, height * 0.5 + 0.12),
        (width, depth, height),
        wall,
        role="building_lod",
    )
    roof_angle = math.radians(27.0)
    roof_width = width + 0.22
    slab_width = roof_width * 0.58
    roof_rise = math.sin(roof_angle) * slab_width * 0.5
    for side, sign in (("Left", -1.0), ("Right", 1.0)):
        box(
            name + "Roof" + side,
            (x + sign * roof_width * 0.225, y, height + 0.12 + roof_rise * 0.5),
            (slab_width, depth + 0.46, 0.16),
            s["roof_blue"],
            role="roof_lod",
            rotation=(0.0, sign * roof_angle, 0.0),
        )
    facade_y = y - depth * 0.5 - 0.02
    box(
        name + "Door",
        (x, facade_y - 0.025, 0.78),
        (0.68, 0.08, 1.38),
        s["door"],
        role="facade_lod",
    )
    for index, window_x in enumerate((x - 0.95, x + 0.95), start=1):
        box(
            f"{name}Window{index}",
            (window_x, facade_y - 0.03, 1.42),
            (0.58, 0.06, 0.72),
            s["window"],
            role="facade_lod",
        )
    rotate_new_objects(existing_names, center, heading)


def cutaway_home(
    center: tuple[float, float],
    s: dict[str, Any],
) -> None:
    """Build Truman's home as a readable dollhouse instead of an opaque shell."""
    x, y = center
    location_id = "apartment"
    box(
        "TrumanHomeFloor",
        (x, y, 0.1),
        (4.2, 3.2, 0.2),
        s["interior_floor"],
        role="building",
        location_id=location_id,
        bevel=0.04,
    )
    for name, position, dimensions in (
        ("TrumanHomeBackWall", (x, y + 1.52, 1.42), (4.2, 0.16, 2.65)),
        ("TrumanHomeWestWall", (x - 2.02, y, 1.42), (0.16, 3.2, 2.65)),
        ("TrumanHomeEastWall", (x + 2.02, y + 0.25, 1.42), (0.16, 2.7, 2.65)),
        ("TrumanHomeFrontWall", (x + 1.6, y - 1.52, 0.62), (0.85, 0.16, 1.05)),
    ):
        box(
            name,
            position,
            dimensions,
            s["home_wall"],
            role="building",
            location_id=location_id,
            bevel=0.045,
        )
    # A rear roof slice preserves the house silhouette without hiding the activity stage.
    box(
        "TrumanHomeRearRoof",
        (x, y + 1.05, 2.92),
        (4.5, 1.15, 0.18),
        s["roof_blue"],
        role="roof",
        location_id=location_id,
        bevel=0.035,
    )
    box(
        "TrumanHomeDoor",
        (x + 1.2, y - 1.61, 0.86),
        (0.72, 0.1, 1.5),
        s["door"],
        role="entrance",
        location_id=location_id,
        semantic_id="portal:apartment:entry-living",
        bevel=0.025,
    )
    box(
        "TrumanLivingSofaSeat",
        (x + 0.25, y - 0.58, 0.42),
        (1.55, 0.62, 0.34),
        s["sofa"],
        role="interactable_visual",
        location_id=location_id,
        semantic_id="apartment.living-sofa",
        bevel=0.08,
    )
    box(
        "TrumanLivingSofaBack",
        (x + 0.25, y - 0.28, 0.78),
        (1.55, 0.2, 0.75),
        s["sofa"],
        role="interactable_visual",
        location_id=location_id,
        semantic_id="apartment.living-sofa",
        bevel=0.08,
    )
    box(
        "TrumanCoffeeTable",
        (x + 0.25, y - 1.15, 0.42),
        (1.15, 0.55, 0.12),
        s["furniture_wood"],
        role="interior_prop",
        location_id=location_id,
        bevel=0.035,
    )
    box(
        "TrumanLivingRug",
        (x + 0.25, y - 0.72, 0.225),
        (2.2, 1.5, 0.035),
        s["rug"],
        role="interior_prop",
        location_id=location_id,
        bevel=0.025,
    )
    box(
        "TrumanTelevisionCabinet",
        (x + 0.35, y + 1.28, 0.42),
        (1.35, 0.35, 0.58),
        s["furniture_wood"],
        role="interior_prop",
        location_id=location_id,
        bevel=0.035,
    )
    box(
        "TrumanTelevision",
        (x + 0.35, y + 1.05, 1.05),
        (1.05, 0.16, 0.72),
        s["screen"],
        role="story_prop",
        location_id=location_id,
        semantic_id="story:apartment:television",
        bevel=0.055,
    )
    box(
        "TrumanKitchenCounter",
        (x - 1.35, y - 0.45, 0.52),
        (0.58, 1.55, 0.92),
        s["kitchen"],
        role="interactable_visual",
        location_id=location_id,
        semantic_id="apartment.kitchen-counter",
        bevel=0.035,
    )
    box(
        "TrumanKitchenWorktop",
        (x - 1.35, y - 0.45, 1.02),
        (0.68, 1.65, 0.1),
        s["white_trim"],
        role="interior_prop",
        location_id=location_id,
        bevel=0.025,
    )
    box(
        "TrumanRefrigerator",
        (x - 1.55, y + 0.95, 0.98),
        (0.72, 0.62, 1.72),
        s["appliance"],
        role="interior_prop",
        location_id=location_id,
        bevel=0.055,
    )
    box(
        "TrumanStoveTop",
        (x - 1.36, y - 0.72, 1.085),
        (0.48, 0.48, 0.035),
        s["screen"],
        role="interior_prop",
        location_id=location_id,
        bevel=0.018,
    )
    for burner_index, burner_y in enumerate((y - 0.86, y - 0.58), start=1):
        cylinder(
            f"TrumanStoveBurner{burner_index}",
            (x - 1.36, burner_y, 1.115),
            0.1,
            0.025,
            s["metal"],
            role="interior_prop",
            location_id=location_id,
            vertices=16,
        )
    cylinder(
        "TrumanKitchenSink",
        (x - 1.36, y + 0.05, 1.1),
        0.2,
        0.04,
        s["metal"],
        role="interior_prop",
        location_id=location_id,
        vertices=20,
    )
    box(
        "TrumanDiningTable",
        (x + 1.15, y + 0.55, 0.72),
        (1.0, 0.72, 0.1),
        s["furniture_wood"],
        role="interior_prop",
        location_id=location_id,
        bevel=0.035,
    )
    for chair_index, chair_y in enumerate((y + 0.05, y + 1.02), start=1):
        box(
            f"TrumanDiningChair{chair_index}Seat",
            (x + 1.15, chair_y, 0.43),
            (0.48, 0.42, 0.1),
            s["bench_wood"],
            role="interior_prop",
            location_id=location_id,
            bevel=0.025,
        )
        box(
            f"TrumanDiningChair{chair_index}Back",
            (x + 1.15, chair_y + (-0.18 if chair_index == 1 else 0.18), 0.72),
            (0.48, 0.09, 0.56),
            s["bench_wood"],
            role="interior_prop",
            location_id=location_id,
            bevel=0.025,
        )
    for frame_index, frame_x in enumerate((x - 0.45, x + 0.75), start=1):
        box(
            f"TrumanFamilyFrame{frame_index}",
            (frame_x, y + 1.415, 1.75),
            (0.62, 0.045, 0.48),
            s["frame"],
            role="story_prop",
            location_id=location_id,
            bevel=0.018,
        )
    sphere(
        "TrumanHiddenCamera",
        (x + 1.72, y + 1.34, 2.18),
        (0.09, 0.09, 0.09),
        s["screen"],
        role="story_prop",
        location_id=location_id,
        semantic_id="story:apartment:hidden-camera",
    )
    for index, lamp_x in enumerate((x - 0.65, x + 0.8), start=1):
        cylinder(
            f"TrumanPendant{index}",
            (lamp_x, y + 0.55, 1.95),
            0.18,
            0.22,
            s["lamp_glow"],
            role="interior_prop",
            location_id=location_id,
            vertices=16,
        )
    text(
        "TrumanHomeText",
        "LANCASTER HOUSE",
        (x, y + 1.42, 2.28),
        s["sign_text"],
        size=0.22,
        location_id=location_id,
    )


def cutaway_cafe(center: tuple[float, float], s: dict[str, Any]) -> None:
    """Build a visible service counter, queue and seating stage for embodied activities."""
    x, y = center
    location_id = "cafe"
    box(
        "CornerCafeFloor",
        (x, y, 0.1),
        (3.8, 2.7, 0.2),
        s["cafe_floor"],
        role="building",
        location_id=location_id,
        bevel=0.04,
    )
    for name, position, dimensions in (
        ("CornerCafeBackWall", (x, y + 1.27, 1.45), (3.8, 0.16, 2.7)),
        ("CornerCafeWestWall", (x - 1.82, y, 1.45), (0.16, 2.7, 2.7)),
        ("CornerCafeEastWall", (x + 1.82, y + 0.2, 1.45), (0.16, 2.3, 2.7)),
        ("CornerCafeFrontWall", (x + 1.5, y - 1.27, 0.58), (0.62, 0.16, 0.95)),
    ):
        box(
            name,
            position,
            dimensions,
            s["cafe_wall"],
            role="building",
            location_id=location_id,
            bevel=0.045,
        )
    box(
        "CornerCafeRearRoof",
        (x, y + 0.92, 2.9),
        (4.1, 0.9, 0.2),
        s["white_trim"],
        role="roof",
        location_id=location_id,
        bevel=0.04,
    )
    box(
        "CornerCafeAwning",
        (x, y - 1.4, 2.72),
        (2.65, 0.42, 0.14),
        s["awning"],
        role="awning",
        location_id=location_id,
        bevel=0.04,
    )
    box(
        "CornerCafeCounter",
        (x + 1.0, y + 0.15, 0.55),
        (0.58, 1.65, 0.95),
        s["furniture_wood"],
        role="interactable_visual",
        location_id=location_id,
        semantic_id="cafe.coffee-counter",
        bevel=0.045,
    )
    box(
        "CornerCafeCounterTop",
        (x + 1.0, y + 0.15, 1.07),
        (0.7, 1.78, 0.1),
        s["white_trim"],
        role="interior_prop",
        location_id=location_id,
        bevel=0.025,
    )
    box(
        "CornerCafeCoffeeMachine",
        (x + 0.98, y + 0.45, 1.32),
        (0.42, 0.46, 0.42),
        s["appliance"],
        role="interior_prop",
        location_id=location_id,
        bevel=0.045,
    )
    for spout_index, spout_y in enumerate((y + 0.34, y + 0.56), start=1):
        cylinder(
            f"CornerCafeMachineSpout{spout_index}",
            (x + 0.72, spout_y, 1.24),
            0.025,
            0.22,
            s["metal"],
            role="interior_prop",
            location_id=location_id,
            vertices=10,
            rotation=(0.0, math.pi / 2.0, 0.0),
        )
    box(
        "CornerCafeRegister",
        (x + 0.96, y - 0.48, 1.24),
        (0.34, 0.3, 0.28),
        s["screen"],
        role="interior_prop",
        location_id=location_id,
        bevel=0.04,
    )
    box(
        "CornerCafeMenuBoard",
        (x - 0.25, y + 1.17, 1.78),
        (1.55, 0.06, 0.82),
        s["menu_board"],
        role="story_prop",
        location_id=location_id,
        semantic_id="story:cafe:menu-board",
        bevel=0.025,
    )
    for shelf_index, shelf_z in enumerate((1.02, 1.52), start=1):
        box(
            f"CornerCafeShelf{shelf_index}",
            (x - 1.28, y + 1.12, shelf_z),
            (0.82, 0.22, 0.08),
            s["furniture_wood"],
            role="interior_prop",
            location_id=location_id,
            bevel=0.018,
        )
    cylinder(
        "CornerCafeTable",
        (x - 0.8, y + 0.15, 0.7),
        0.55,
        0.1,
        s["furniture_wood"],
        role="interior_prop",
        location_id=location_id,
        vertices=20,
    )
    box(
        "CornerCafeWindowChair",
        (x - 1.05, y + 0.55, 0.38),
        (0.52, 0.52, 0.52),
        s["bench_wood"],
        role="interactable_visual",
        location_id=location_id,
        semantic_id="cafe.window-chair",
        bevel=0.06,
    )
    box(
        "CornerCafeCenterChair",
        (x - 0.25, y - 0.15, 0.38),
        (0.52, 0.52, 0.52),
        s["bench_wood"],
        role="interactable_visual",
        location_id=location_id,
        semantic_id="cafe.center-chair",
        bevel=0.06,
    )
    for index, jar_y in enumerate((y - 0.42, y, y + 0.42), start=1):
        cylinder(
            f"CornerCafeCounterJar{index}",
            (x + 0.95, jar_y, 1.22),
            0.09,
            0.22,
            s["lamp_glow"],
            role="interior_prop",
            location_id=location_id,
            vertices=12,
        )
    text(
        "CornerCafeText",
        "CORNER CAFE",
        (x, y - 1.63, 2.72),
        s["sign_text"],
        size=0.24,
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
    cylinder(
        name + "Pole",
        (x, y, 1.15),
        0.04,
        2.3,
        s["metal"],
        role="street_lamp",
        vertices=8,
    )
    box(
        name + "Lantern",
        (x, y, 2.3),
        (0.28, 0.28, 0.42),
        s["lamp_glow"],
        role="street_lamp",
        bevel=0.035,
    )
    box(
        name + "Cap",
        (x, y, 2.56),
        (0.38, 0.38, 0.1),
        s["metal"],
        role="street_lamp",
        bevel=0.025,
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


def planter(name: str, x: float, y: float, s: dict[str, Any]) -> None:
    cylinder(
        name + "Pot",
        (x, y, 0.28),
        0.28,
        0.5,
        s["terracotta"],
        role="street_micro_scene",
        vertices=12,
    )
    for index, (dx, dy, z) in enumerate(((-0.12, 0.0, 0.72), (0.12, 0.03, 0.78)), start=1):
        sphere(
            f"{name}Plant{index}",
            (x + dx, y + dy, z),
            (0.3, 0.27, 0.34),
            s["foliage_alt"],
            role="street_micro_scene",
        )


def fire_hydrant(name: str, x: float, y: float, s: dict[str, Any]) -> None:
    cylinder(
        name + "Body",
        (x, y, 0.38),
        0.16,
        0.6,
        s["signal_red"],
        role="street_micro_scene",
    )
    cylinder(
        name + "Top",
        (x, y, 0.72),
        0.21,
        0.12,
        s["signal_red"],
        role="street_micro_scene",
    )
    cylinder(
        name + "SideValve",
        (x + 0.18, y, 0.44),
        0.09,
        0.22,
        s["metal"],
        role="street_micro_scene",
        vertices=12,
        rotation=(0.0, math.pi / 2.0, 0.0),
    )


def bicycle(name: str, x: float, y: float, s: dict[str, Any]) -> None:
    for suffix, wheel_x in (("Rear", x - 0.42), ("Front", x + 0.42)):
        cylinder(
            name + suffix + "Wheel",
            (wheel_x, y, 0.36),
            0.32,
            0.045,
            s["metal"],
            role="street_micro_scene",
            vertices=20,
            rotation=(math.pi / 2.0, 0.0, 0.0),
        )
    for suffix, location, dimensions, rotation_y in (
        ("FrameLow", (x, y, 0.43), (0.72, 0.055, 0.055), 0.0),
        ("FrameRear", (x - 0.18, y, 0.58), (0.055, 0.055, 0.55), -0.55),
        ("FrameFront", (x + 0.22, y, 0.6), (0.055, 0.055, 0.62), 0.52),
    ):
        box(
            name + suffix,
            location,
            dimensions,
            s["bicycle"],
            role="street_micro_scene",
            bevel=0.012,
            rotation=(0.0, rotation_y, 0.0),
        )
    box(
        name + "Handlebar",
        (x + 0.42, y, 0.88),
        (0.35, 0.055, 0.055),
        s["metal"],
        role="street_micro_scene",
        bevel=0.012,
    )


def parked_car(name: str, x: float, y: float, surface: Any, s: dict[str, Any]) -> None:
    box(
        name + "Body",
        (x, y, 0.48),
        (2.25, 1.05, 0.58),
        surface,
        role="street_micro_scene",
        bevel=0.18,
    )
    box(
        name + "Cabin",
        (x + 0.1, y, 0.9),
        (1.25, 0.92, 0.55),
        s["storefront_glass"],
        role="street_micro_scene",
        bevel=0.16,
    )
    for wheel_index, (wheel_x, wheel_y) in enumerate(
        (
            (x - 0.7, y - 0.5),
            (x + 0.7, y - 0.5),
            (x - 0.7, y + 0.5),
            (x + 0.7, y + 0.5),
        ),
        start=1,
    ):
        cylinder(
            f"{name}Wheel{wheel_index}",
            (wheel_x, wheel_y, 0.32),
            0.24,
            0.12,
            s["tire"],
            role="street_micro_scene",
            vertices=16,
            rotation=(math.pi / 2.0, 0.0, 0.0),
        )


def bus_stop(name: str, x: float, y: float, s: dict[str, Any]) -> None:
    for post_x in (x - 0.85, x + 0.85):
        cylinder(
            name + f"Post{post_x:+.2f}",
            (post_x, y, 1.05),
            0.045,
            2.1,
            s["metal"],
            role="street_micro_scene",
            vertices=8,
        )
    box(
        name + "Roof",
        (x, y, 2.12),
        (2.1, 0.9, 0.12),
        s["roof_blue"],
        role="street_micro_scene",
        bevel=0.04,
    )
    box(
        name + "Timetable",
        (x + 0.72, y - 0.03, 1.25),
        (0.42, 0.08, 0.72),
        s["sign_text"],
        role="story_prop",
        semantic_id="story:town:bus-timetable",
        bevel=0.02,
    )
    street_bench(name + "Bench", x - 0.12, y, 0.0, s)


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
    # The semantic core remains a compact four-block grid, while the authored surface extends
    # well beyond it. The buffer prevents the director camera from exposing a diorama edge.
    # Blender Y maps to negative Godot Z, so core coordinates stay in sync with the route graph.
    box(
        "TownGround",
        (0.0, COAST_INLAND_EDGE_Y - VISUAL_BUFFER_DEPTH * 0.5, -0.18),
        (VISUAL_BUFFER_WIDTH, VISUAL_BUFFER_DEPTH, 0.3),
        s["ground"],
        role="ground",
        bevel=0.35,
    )
    box(
        "BacklotOcean",
        (0.0, OCEAN_NEAR_EDGE_Y + HORIZON_OCEAN_DEPTH * 0.5, -0.08),
        (HORIZON_OCEAN_WIDTH, HORIZON_OCEAN_DEPTH, 0.12),
        s["ocean"],
        role="ocean",
        bevel=0.12,
    )
    box(
        "SeahavenBeach",
        (0.0, 14.25, -0.01),
        (VISUAL_BUFFER_WIDTH, 3.4, 0.12),
        s["sand"],
        role="coast",
        bevel=0.08,
    )
    box(
        "Seawall",
        (0.0, 12.35, 0.34),
        (VISUAL_BUFFER_WIDTH, 0.34, 0.68),
        s["seawall"],
        role="seawall",
        bevel=0.06,
    )
    for road_name, location, dimensions in (
        ("BayAvenue", (0.0, -5.5, 0.01), (VISUAL_BUFFER_WIDTH, 1.7, 0.1)),
        ("MarketStreet", (0.0, 3.2, 0.015), (VISUAL_BUFFER_WIDTH, 1.7, 0.1)),
        (
            "LancasterAvenue",
            (-7.0, COAST_INLAND_EDGE_Y - VISUAL_BUFFER_DEPTH * 0.5, 0.02),
            (1.7, VISUAL_BUFFER_DEPTH, 0.11),
        ),
        (
            "SeahavenAvenue",
            (6.0, COAST_INLAND_EDGE_Y - VISUAL_BUFFER_DEPTH * 0.5, 0.02),
            (1.7, VISUAL_BUFFER_DEPTH, 0.11),
        ),
        ("OceanBoulevard", (0.0, 10.1, 0.02), (VISUAL_BUFFER_WIDTH, 1.5, 0.11)),
        ("PineStreet", (0.0, -15.0, 0.012), (VISUAL_BUFFER_WIDTH, 1.55, 0.1)),
        ("CypressStreet", (0.0, -25.0, 0.012), (VISUAL_BUFFER_WIDTH, 1.55, 0.1)),
    ):
        box(road_name, location, dimensions, s["road"], role="road", bevel=0.025)
    for street_name, street_y in (
        ("Bay", -5.5),
        ("Market", 3.2),
        ("Ocean", 10.1),
        ("Pine", -15.0),
        ("Cypress", -25.0),
    ):
        for index, x in enumerate(range(-58, 59, 3), start=1):
            box(
                f"{street_name}StreetDash{index}",
                (float(x), street_y, 0.078),
                (1.15, 0.055, 0.022),
                s["road_marking"],
                role="road_marking",
            )
    for avenue_name, avenue_x in (("Lancaster", -7.0), ("Seahaven", 6.0)):
        for index, y in enumerate(range(-44, 13, 3), start=1):
            box(
                f"{avenue_name}AvenueDash{index}",
                (avenue_x, float(y), 0.079),
                (0.055, 1.15, 0.022),
                s["road_marking"],
                role="road_marking",
            )
    for crossing, (crossing_x, crossing_y) in enumerate(
        (
            (-7.0, -25.0),
            (6.0, -25.0),
            (-7.0, -15.0),
            (6.0, -15.0),
            (-7.0, -5.5),
            (6.0, -5.5),
            (-7.0, 3.2),
            (6.0, 3.2),
            (-7.0, 10.1),
            (6.0, 10.1),
        ),
        start=1,
    ):
        for stripe, offset in enumerate((-0.42, -0.14, 0.14, 0.42), start=1):
            box(
                f"Crosswalk{crossing}Stripe{stripe}",
                (crossing_x + offset, crossing_y, 0.082),
                (0.14, 1.22, 0.025),
                s["road_marking"],
                role="road_marking",
            )
    for walk_name, location, dimensions in (
        ("BayWalkNorth", (0.0, -4.35, 0.07), (VISUAL_BUFFER_WIDTH, 0.5, 0.13)),
        ("BayWalkSouth", (0.0, -6.65, 0.07), (VISUAL_BUFFER_WIDTH, 0.5, 0.13)),
        ("MarketWalkNorth", (0.0, 4.35, 0.07), (VISUAL_BUFFER_WIDTH, 0.5, 0.13)),
        ("MarketWalkSouth", (0.0, 2.05, 0.07), (VISUAL_BUFFER_WIDTH, 0.5, 0.13)),
        ("PineWalkNorth", (0.0, -13.95, 0.07), (VISUAL_BUFFER_WIDTH, 0.46, 0.13)),
        ("PineWalkSouth", (0.0, -16.05, 0.07), (VISUAL_BUFFER_WIDTH, 0.46, 0.13)),
        ("CypressWalkNorth", (0.0, -23.95, 0.07), (VISUAL_BUFFER_WIDTH, 0.46, 0.13)),
        ("CypressWalkSouth", (0.0, -26.05, 0.07), (VISUAL_BUFFER_WIDTH, 0.46, 0.13)),
        (
            "LancasterWalkWest",
            (-8.15, COAST_INLAND_EDGE_Y - VISUAL_BUFFER_DEPTH * 0.5, 0.07),
            (0.5, VISUAL_BUFFER_DEPTH, 0.13),
        ),
        (
            "LancasterWalkEast",
            (-5.85, COAST_INLAND_EDGE_Y - VISUAL_BUFFER_DEPTH * 0.5, 0.07),
            (0.5, VISUAL_BUFFER_DEPTH, 0.13),
        ),
        (
            "SeahavenWalkWest",
            (4.85, COAST_INLAND_EDGE_Y - VISUAL_BUFFER_DEPTH * 0.5, 0.07),
            (0.5, VISUAL_BUFFER_DEPTH, 0.13),
        ),
        (
            "SeahavenWalkEast",
            (7.15, COAST_INLAND_EDGE_Y - VISUAL_BUFFER_DEPTH * 0.5, 0.07),
            (0.5, VISUAL_BUFFER_DEPTH, 0.13),
        ),
        ("OceanWalkSouth", (0.0, 8.95, 0.07), (VISUAL_BUFFER_WIDTH, 0.48, 0.13)),
        ("Promenade", (0.0, 11.55, 0.08), (VISUAL_BUFFER_WIDTH, 1.15, 0.15)),
    ):
        box(walk_name, location, dimensions, s["sidewalk"], role="sidewalk", bevel=0.025)

    build_plaza(s)
    cutaway_home((-12.0, -2.6), s)
    seaside_house(
        "BachelorHouse",
        (-12.0, 6.2),
        (3.8, 3.0, 2.55),
        s["bachelor_wall"],
        s,
        location_id="bachelor-apt",
        sign="BACHELOR COURT",
    )
    cutaway_cafe((-2.8, 6.2), s)
    commercial_building(
        "HarborMall",
        (10.2, 6.2),
        (5.6, 3.1, 3.5),
        s["mall_wall"],
        s,
        location_id="mall",
        sign="HARBOR MALL",
        columns=4,
    )
    box(
        "HarborMallEntryTower",
        (10.2, 4.54, 2.15),
        (1.35, 0.72, 4.0),
        s["mall_wall"],
        role="building_accent",
        location_id="mall",
        bevel=0.08,
    )
    box(
        "HarborMallMarquee",
        (10.2, 4.05, 3.25),
        (2.15, 0.22, 0.72),
        s["awning"],
        role="building_accent",
        location_id="mall",
        bevel=0.05,
    )
    commercial_building(
        "HarborOffice",
        (10.5, 11.8),
        (4.2, 3.0, 3.2),
        s["office_wall"],
        s,
        location_id="office",
        sign="HARBOR OFFICE",
        columns=3,
    )
    cylinder(
        "HarborOfficeSignalMast",
        (10.5, 12.35, 4.55),
        0.055,
        2.2,
        s["metal"],
        role="building_accent",
        location_id="office",
        vertices=10,
    )
    for signal_index, signal_z in enumerate((4.0, 4.55, 5.1), start=1):
        sphere(
            f"HarborOfficeSignal{signal_index}",
            (10.5, 12.35, signal_z),
            (0.13, 0.13, 0.13),
            s["signal_red"] if signal_index == 1 else s["lamp_glow"],
            role="building_accent",
            location_id="office",
        )
    commercial_building(
        "BayHospital",
        (11.0, -2.5),
        (5.4, 3.2, 3.45),
        s["hospital_wall"],
        s,
        location_id="hospital",
        sign="BAY HOSPITAL",
        columns=4,
    )
    box(
        "BayHospitalEmergencyCanopy",
        (11.0, -4.65, 1.55),
        (3.3, 1.15, 0.18),
        s["white_trim"],
        role="building_accent",
        location_id="hospital",
        bevel=0.045,
    )
    for canopy_index, canopy_x in enumerate((9.65, 12.35), start=1):
        cylinder(
            f"BayHospitalCanopyPost{canopy_index}",
            (canopy_x, -4.85, 0.78),
            0.055,
            1.55,
            s["metal"],
            role="building_accent",
            location_id="hospital",
            vertices=10,
        )
    box(
        "HospitalCrossVertical",
        (11.0, -4.14, 2.18),
        (0.18, 0.08, 0.82),
        s["hospital_cross"],
        role="location_sign",
        location_id="hospital",
        bevel=0.02,
    )
    box(
        "HospitalCrossHorizontal",
        (11.0, -4.18, 2.18),
        (0.64, 0.08, 0.18),
        s["hospital_cross"],
        role="location_sign",
        location_id="hospital",
        bevel=0.02,
    )

    # Dense perimeter and block-edge housing provides parallax and makes every road lead
    # somewhere. These are visual buildings only; the seven authored locations remain the
    # semantic destinations used by agents.
    background_houses = (
        # heading rotates the default south-facing facade toward its adjoining street.
        ("SouthHouse01", -19.0, -13.2, s["pastel_blue"], math.pi),
        ("SouthHouse02", -14.8, -13.0, s["pastel_yellow"], math.pi),
        ("SouthHouse03", -10.4, -13.3, s["pastel_pink"], math.pi),
        ("SouthHouse04", -4.2, -13.0, s["pastel_blue"], math.pi),
        ("SouthHouse05", 0.2, -13.3, s["pastel_yellow"], math.pi),
        ("SouthHouse06", 10.3, -13.0, s["pastel_pink"], math.pi),
        ("SouthHouse07", 14.7, -13.3, s["pastel_blue"], math.pi),
        ("SouthHouse08", 19.0, -13.0, s["pastel_yellow"], math.pi),
        ("WestBlockHouse01", -19.0, -8.4, s["pastel_pink"], math.pi / 2.0),
        ("WestBlockHouse02", -18.8, -1.0, s["pastel_blue"], math.pi / 2.0),
        ("WestBlockHouse03", -18.9, 6.5, s["pastel_yellow"], math.pi / 2.0),
        ("CentralBlockHouse01", -3.1, -8.8, s["pastel_pink"], math.pi),
        ("CentralBlockHouse02", 1.1, -8.9, s["pastel_blue"], math.pi),
        ("EastBlockHouse01", 10.6, -8.8, s["pastel_yellow"], math.pi),
        ("EastBlockHouse02", 15.0, -8.9, s["pastel_pink"], math.pi),
        ("EastBlockHouse03", 19.1, -8.6, s["pastel_blue"], math.pi),
        ("NorthWestHouse", -18.7, 11.1, s["pastel_blue"], 0.0),
        ("NorthCenterHouse", -5.0, 11.2, s["pastel_yellow"], 0.0),
        ("NorthEastHouse", 18.4, 11.1, s["pastel_pink"], 0.0),
    )
    for house_name, house_x, house_y, wall, heading in background_houses:
        seaside_house(
            house_name,
            (house_x, house_y),
            (3.25, 2.45, 2.35),
            wall,
            s,
            location_id="town-background",
            heading=heading,
        )

    buffer_houses = (
        # Outer visual blocks continue the street grammar with a cheaper silhouette LOD.
        ("PineSouthHouse01", -20.0, -18.2, s["pastel_pink"], 0.0),
        ("PineSouthHouse02", -14.8, -18.4, s["pastel_blue"], 0.0),
        ("PineSouthHouse03", -2.7, -18.3, s["pastel_yellow"], 0.0),
        ("PineSouthHouse04", 11.0, -18.3, s["pastel_pink"], 0.0),
        ("PineSouthHouse05", 16.0, -18.4, s["pastel_blue"], 0.0),
        ("PineNorthHouse01", -19.6, -11.7, s["pastel_yellow"], math.pi),
        ("PineNorthHouse02", -14.5, -11.8, s["pastel_pink"], math.pi),
        ("PineNorthHouse03", 10.8, -11.7, s["pastel_blue"], math.pi),
        ("PineNorthHouse04", 16.0, -11.8, s["pastel_yellow"], math.pi),
        ("CypressSouthHouse01", -20.0, -28.6, s["pastel_blue"], 0.0),
        ("CypressSouthHouse02", -14.8, -28.4, s["pastel_yellow"], 0.0),
        ("CypressSouthHouse03", -2.8, -28.5, s["pastel_pink"], 0.0),
        ("CypressSouthHouse04", 11.0, -28.4, s["pastel_blue"], 0.0),
        ("CypressSouthHouse05", 16.2, -28.6, s["pastel_yellow"], 0.0),
        ("CypressNorthHouse01", -19.8, -21.8, s["pastel_pink"], math.pi),
        ("CypressNorthHouse02", -14.6, -21.7, s["pastel_blue"], math.pi),
        ("CypressNorthHouse03", -2.8, -21.8, s["pastel_yellow"], math.pi),
        ("CypressNorthHouse04", 11.0, -21.7, s["pastel_pink"], math.pi),
        ("CypressNorthHouse05", 16.2, -21.8, s["pastel_blue"], math.pi),
        ("WestBufferHouse01", -29.0, -9.0, s["pastel_yellow"], math.pi / 2.0),
        ("WestBufferHouse02", -29.2, -1.5, s["pastel_pink"], math.pi / 2.0),
        ("WestBufferHouse03", -29.0, 6.0, s["pastel_blue"], math.pi / 2.0),
        ("EastBufferHouse01", 29.0, -9.0, s["pastel_blue"], -math.pi / 2.0),
        ("EastBufferHouse02", 29.2, -1.5, s["pastel_yellow"], -math.pi / 2.0),
        ("EastBufferHouse03", 29.0, 6.0, s["pastel_pink"], -math.pi / 2.0),
    )
    for house_name, house_x, house_y, wall, heading in buffer_houses:
        background_house_lod(
            house_name,
            (house_x, house_y),
            wall,
            s,
            heading=heading,
        )

    for shop_name, shop_x, shop_y, wall, label in (
        ("MarketBakery", -17.1, 0.2, s["pastel_yellow"], "BAKERY"),
        ("MarketBooks", -11.2, 0.2, s["pastel_blue"], "BOOKS"),
        ("MarketFlorist", 10.0, 0.2, s["pastel_pink"], "FLORIST"),
        ("MarketCinema", 16.8, 0.1, s["office_wall"], "SEAHAVEN CINEMA"),
        ("HarborDiner", 3.0, 6.2, s["pastel_yellow"], "HARBOR DINER"),
        ("HarborHotel", 17.1, 6.4, s["pastel_blue"], "SEAHAVEN HOTEL"),
    ):
        commercial_building(
            shop_name,
            (shop_x, shop_y),
            (4.2 if shop_name != "MarketCinema" else 5.2, 2.7, 2.8),
            wall,
            s,
            location_id="town-background",
            sign=label,
            columns=3,
            heading=math.pi if shop_y < 3.2 else 0.0,
        )

    tree_positions = (
        (-21.0, -10.0),
        (-21.0, -3.0),
        (-21.0, 4.0),
        (-21.0, 9.0),
        (-16.7, -5.0),
        (-13.8, -5.0),
        (-9.5, -8.4),
        (-8.4, -1.2),
        (-5.1, -3.6),
        (-3.7, 1.4),
        (1.5, 1.4),
        (3.9, -3.5),
        (8.2, -8.5),
        (8.4, 1.4),
        (14.0, -4.0),
        (18.8, -4.0),
        (21.0, -10.0),
        (21.0, -3.0),
        (21.0, 4.0),
        (21.0, 9.0),
        (-15.0, 9.0),
        (-10.0, 9.0),
        (-1.0, 9.0),
        (4.0, 9.0),
        (14.5, 9.0),
        (-24.0, -26.0),
        (-10.5, -27.5),
        (2.5, -27.5),
        (22.5, -26.0),
        (-24.0, -20.0),
        (-10.5, -19.5),
        (2.5, -19.5),
        (22.5, -20.0),
        (-25.0, -14.0),
        (24.5, -14.0),
        (-31.5, -4.8),
        (31.5, -4.8),
        (-31.5, 3.8),
        (31.5, 3.8),
        (-25.0, 9.0),
        (25.0, 9.0),
    )
    for index, (tree_x, tree_y) in enumerate(tree_positions, start=1):
        tree(f"TownTree{index}", tree_x, tree_y, s, 0.82 + 0.08 * (index % 3))
    for index, (lamp_x, lamp_y) in enumerate(
        (
            (-17.0, -4.35),
            (-11.5, -4.35),
            (-3.0, -4.35),
            (3.0, -4.35),
            (10.0, -4.35),
            (17.0, -4.35),
            (-17.0, 4.35),
            (-11.5, 4.35),
            (-3.0, 4.35),
            (3.0, 4.35),
            (10.0, 4.35),
            (17.0, 4.35),
            (-8.15, -1.0),
            (-8.15, 7.0),
            (7.15, -1.0),
            (7.15, 7.0),
            (-14.0, 11.55),
            (-5.0, 11.55),
            (5.0, 11.55),
            (15.0, 11.55),
        ),
        start=1,
    ):
        street_lamp(f"TownLamp{index}", lamp_x, lamp_y, s)

    for index, (bench_x, bench_y, rotation) in enumerate(
        (
            (-1.75, -1.75, 0.0),
            (1.75, 1.75, math.pi),
            (-5.2, 1.6, 0.0),
            (8.0, 1.6, 0.0),
            (-10.0, 11.45, math.pi),
            (10.0, 11.45, math.pi),
        ),
        start=1,
    ):
        street_bench(f"TownBench{index}", bench_x, bench_y, rotation, s)

    # Small authored scenes make the town read as inhabited even before agents arrive.
    for index, (planter_x, planter_y) in enumerate(
        ((-2.2, -2.0), (2.2, 1.7), (-5.0, 4.45), (-2.0, 4.45), (8.2, 4.45)),
        start=1,
    ):
        planter(f"TownPlanter{index}", planter_x, planter_y, s)
    fire_hydrant("BayAvenueHydrant", -5.2, -4.3, s)
    fire_hydrant("HospitalHydrant", 14.2, -4.3, s)
    bicycle("TrumanBicycle", -10.7, -4.25, s)
    bicycle("CafeBicycle", -4.5, 4.4, s)
    bus_stop("SeahavenBusStop", 0.0, -6.65, s)
    parked_car("HospitalVisitorCar", 15.5, -5.5, s["car_blue"], s)
    parked_car("BayAvenueCar", -1.8, -5.5, s["car_yellow"], s)
    parked_car("MarketStreetCar", -15.2, 3.2, s["car_blue"], s)
    box(
        "TrumanMailbox",
        (-13.75, -4.3, 0.72),
        (0.48, 0.38, 0.72),
        s["mailbox"],
        role="story_prop",
        location_id="apartment",
        semantic_id="story:apartment:mailbox",
        bevel=0.08,
    )
    cylinder(
        "TrumanMailboxPost",
        (-13.75, -4.3, 0.35),
        0.055,
        0.7,
        s["metal"],
        role="street_micro_scene",
        vertices=8,
    )
    box(
        "CafeNewspaperStand",
        (-1.2, 4.45, 0.58),
        (0.58, 0.42, 1.05),
        s["signal_red"],
        role="story_prop",
        location_id="cafe",
        semantic_id="story:cafe:newspaper-stand",
        bevel=0.08,
    )
    box(
        "CafeHeadline",
        (-1.2, 4.2, 0.68),
        (0.42, 0.03, 0.5),
        s["sign_text"],
        role="story_prop",
        location_id="cafe",
        semantic_id="story:cafe:newspaper-headline",
        bevel=0.01,
    )

    # Waterfront props form a separate destination and foreshadow the artificial boundary.
    torus(
        "PromenadeLifeRing",
        (-4.0, 12.02, 1.15),
        0.28,
        0.065,
        s["signal_red"],
        role="story_prop",
        location_id="plaza",
        rotation=(math.pi / 2.0, 0.0, 0.0),
    )
    cylinder(
        "PromenadeTelescopeStand",
        (5.8, 11.45, 0.72),
        0.08,
        1.25,
        s["metal"],
        role="promenade_detail",
        vertices=10,
    )
    cylinder(
        "PromenadeTelescope",
        (5.8, 11.53, 1.45),
        0.13,
        0.72,
        s["gold"],
        role="story_prop",
        location_id="plaza",
        vertices=16,
        rotation=(math.pi / 2.0, 0.0, 0.0),
    )

    for index, rail_x in enumerate(range(-59, 60, 2), start=1):
        box(
            f"PromenadeRailPost{index}",
            (float(rail_x), 12.08, 0.67),
            (0.075, 0.075, 1.02),
            s["metal"],
            role="promenade_detail",
            bevel=0.018,
        )
    for level, rail_z in enumerate((0.52, 1.03), start=1):
        box(
            f"PromenadeRail{level}",
            (0.0, 12.08, rail_z),
            (VISUAL_BUFFER_WIDTH, 0.07, 0.07),
            s["metal"],
            role="promenade_detail",
            bevel=0.018,
        )

    # The timber pier and boats make the water a real spatial destination rather than a
    # decorative blue border. The central rail gap is intentional and aligns with the pier.
    box(
        "SeahavenPierDeck",
        (-8.0, 18.4, 0.38),
        (2.4, 12.6, 0.32),
        s["furniture_wood"],
        role="waterfront_detail",
        bevel=0.045,
    )
    for piling_index, (piling_x, piling_y) in enumerate(
        (
            (-8.9, 13.2),
            (-7.1, 13.2),
            (-8.9, 16.8),
            (-7.1, 16.8),
            (-8.9, 20.4),
            (-7.1, 20.4),
            (-8.9, 24.0),
            (-7.1, 24.0),
        ),
        start=1,
    ):
        cylinder(
            f"PierPiling{piling_index}",
            (piling_x, piling_y, 0.05),
            0.12,
            1.35,
            s["furniture_wood"],
            role="waterfront_detail",
            vertices=10,
        )
    box(
        "PierShelter",
        (-8.0, 22.8, 1.65),
        (2.0, 2.1, 0.16),
        s["roof_blue"],
        role="waterfront_detail",
        bevel=0.035,
    )
    for post_index, post_x in enumerate((-8.75, -7.25), start=1):
        cylinder(
            f"PierShelterPost{post_index}",
            (post_x, 22.8, 0.95),
            0.055,
            1.5,
            s["white_trim"],
            role="waterfront_detail",
            vertices=8,
        )
    for boat_index, (boat_x, boat_y, boat_color) in enumerate(
        (
            (-13.5, 20.0, s["car_yellow"]),
            (2.5, 18.0, s["white_trim"]),
            (13.5, 25.0, s["car_blue"]),
        ),
        start=1,
    ):
        box(
            f"HarborBoat{boat_index}Hull",
            (boat_x, boat_y, 0.18),
            (2.7, 1.05, 0.55),
            boat_color,
            role="waterfront_detail",
            bevel=0.24,
        )
        box(
            f"HarborBoat{boat_index}Cabin",
            (boat_x + 0.25, boat_y, 0.72),
            (1.0, 0.82, 0.72),
            s["white_trim"],
            role="waterfront_detail",
            bevel=0.12,
        )
        cylinder(
            f"HarborBoat{boat_index}Mast",
            (boat_x, boat_y, 1.55),
            0.035,
            2.2,
            s["metal"],
            role="waterfront_detail",
            vertices=8,
        )
    for foam_index, foam_y in enumerate((13.0, 14.0, 15.2), start=1):
        box(
            f"ShoreFoam{foam_index}",
            (2.0 if foam_index % 2 else -3.0, foam_y, 0.025),
            (100.0 - foam_index * 5.0, 0.12, 0.035),
            s["white_trim"],
            role="waterfront_detail",
            bevel=0.05,
        )

    box(
        "StudioBoundaryNorth",
        (0.0, STUDIO_BOUNDARY_Y, 2.0),
        (HORIZON_OCEAN_WIDTH, 0.14, 4.0),
        s["dome_wall"],
        role="studio_boundary",
        bevel=0.08,
    )
    box(
        "StudioBoundaryServiceDoor",
        (18.0, STUDIO_BOUNDARY_Y - 0.12, 1.05),
        (1.45, 0.12, 2.05),
        s["door"],
        role="story_prop",
        semantic_id="story:boundary:service-door",
        bevel=0.045,
    )
    box(
        "StudioBoundaryWarningSign",
        (18.0, STUDIO_BOUNDARY_Y - 0.21, 1.35),
        (0.72, 0.04, 0.5),
        s["signal_red"],
        role="story_prop",
        semantic_id="story:boundary:warning-sign",
        bevel=0.018,
    )
    for camera_index, camera_x in enumerate((-18.0, 0.0, 18.0), start=1):
        cylinder(
            f"BoundaryCameraArm{camera_index}",
            (camera_x, STUDIO_BOUNDARY_Y - 0.25, 3.1),
            0.035,
            0.42,
            s["metal"],
            role="story_prop",
            vertices=8,
            rotation=(math.pi / 2.0, 0.0, 0.0),
        )
        box(
            f"BoundaryCamera{camera_index}",
            (camera_x, STUDIO_BOUNDARY_Y - 0.52, 3.05),
            (0.32, 0.5, 0.24),
            s["screen"],
            role="story_prop",
            semantic_id=f"story:boundary:camera-{camera_index}",
            bevel=0.04,
        )
    for index, x in enumerate(range(-148, 149, 4), start=1):
        box(
            f"BoundarySeam{index}",
            (float(x), STUDIO_BOUNDARY_Y - 0.08, 2.0),
            (0.035, 0.03, 4.0),
            s["boundary_seam"],
            role="studio_boundary",
        )

    print(
        f"Built narrative town source geometry: {len(bpy.context.scene.objects)} objects",
        flush=True,
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
        ("TownStreetMicroScenes", "street_micro_scene"),
        ("TownPromenadeDetails", "promenade_detail"),
        ("TownWaterfrontDetails", "waterfront_detail"),
        ("TownRooftopDetails", "rooftop_detail"),
        ("TownBuildingAccents", "building_accent"),
        ("TownBufferBuildings", "building_lod"),
        ("TownBufferFacades", "facade_lod"),
        ("TownBufferRoofs", "roof_lod"),
        ("TownBackgroundBoundary", "studio_boundary"),
    ):
        merge_role(merged_name, role)
        print(f"Merged role {role} -> {merged_name}", flush=True)
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
        "sand": material("TW_BeachSand", (0.78, 0.68, 0.47, 1.0), roughness=0.9),
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
        "interior_floor": material("TW_InteriorFloor", (0.57, 0.42, 0.27, 1.0), roughness=0.75),
        "cafe_floor": material("TW_CafeFloor", (0.48, 0.31, 0.23, 1.0), roughness=0.72),
        "furniture_wood": material("TW_FurnitureWood", (0.3, 0.16, 0.09, 1.0), roughness=0.66),
        "sofa": material("TW_Sofa", (0.31, 0.49, 0.43, 1.0), roughness=0.82),
        "kitchen": material("TW_Kitchen", (0.68, 0.65, 0.55, 1.0), roughness=0.7),
        "rug": material("TW_Rug", (0.58, 0.22, 0.18, 1.0), roughness=0.92),
        "screen": material("TW_Screen", (0.035, 0.06, 0.065, 1.0), roughness=0.25),
        "appliance": material("TW_Appliance", (0.7, 0.73, 0.69, 1.0), metallic=0.08),
        "frame": material("TW_Frame", (0.72, 0.48, 0.18, 1.0), roughness=0.58),
        "menu_board": material("TW_MenuBoard", (0.08, 0.16, 0.14, 1.0), roughness=0.86),
        "terracotta": material("TW_Terracotta", (0.56, 0.28, 0.17, 1.0), roughness=0.88),
        "signal_red": material("TW_SignalRed", (0.68, 0.08, 0.06, 1.0), roughness=0.58),
        "bicycle": material("TW_Bicycle", (0.13, 0.39, 0.5, 1.0), metallic=0.18),
        "tire": material("TW_Tire", (0.025, 0.03, 0.03, 1.0), roughness=0.94),
        "car_blue": material("TW_CarBlue", (0.12, 0.34, 0.48, 1.0), metallic=0.22),
        "car_yellow": material("TW_CarYellow", (0.72, 0.5, 0.12, 1.0), metallic=0.18),
        "mailbox": material("TW_Mailbox", (0.16, 0.32, 0.35, 1.0), metallic=0.16),
    }
    build_town(s)
    print("Finished semantic batching; validating scene", flush=True)
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
                    "apartment": [-12.0, 0.0, 2.6],
                    "bachelor-apt": [-12.0, 0.0, -6.2],
                    "cafe": [-2.8, 0.0, -6.2],
                    "mall": [10.2, 0.0, -6.2],
                    "office": [10.5, 0.0, -11.8],
                    "hospital": [11.0, 0.0, 2.5],
                },
                "semantic_core_bounds_meters": [CORE_WIDTH, CORE_DEPTH],
                "visual_buffer_bounds_meters": [
                    VISUAL_BUFFER_WIDTH,
                    VISUAL_BUFFER_DEPTH,
                ],
                "environment_bounds_meters": [
                    HORIZON_OCEAN_WIDTH,
                    HORIZON_OCEAN_DEPTH + VISUAL_BUFFER_DEPTH - 4.0,
                ],
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
