from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render stable narrative-town acceptance views"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument(
        "--view",
        action="append",
        choices=("town-overview", "clock-plaza", "truman-home", "cafe-waterfront"),
        help="Render only the selected view; repeat to render multiple views",
    )
    return parser.parse_args(
        sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    )


def look_at(camera: Any, target: tuple[float, float, float]) -> None:
    camera.rotation_euler = (
        (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
    )


def add_area_light(
    name: str,
    location: tuple[float, float, float],
    energy: float,
    size: float,
) -> None:
    light_data = bpy.data.lights.new(name + "Data", type="AREA")
    light_data.energy = energy
    light_data.shape = "DISK"
    light_data.size = size
    light = bpy.data.objects.new(name, light_data)
    light.location = location
    bpy.context.scene.collection.objects.link(light)
    look_at(light, (0.0, 0.0, 0.0))


def configure_scene(width: int, height: int) -> Any:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "AgX - Medium High Contrast"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("PreviewWorld")
    scene.world.color = (0.055, 0.08, 0.1)
    camera_data = bpy.data.cameras.new("AcceptanceCameraData")
    camera_data.lens = 52.0
    camera = bpy.data.objects.new("AcceptanceCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    add_area_light("PreviewKey", (-8.0, -10.0, 18.0), 1900.0, 9.0)
    add_area_light("PreviewFill", (12.0, 4.0, 10.0), 1050.0, 7.0)
    return camera


def configure_detail_visibility(view_name: str) -> None:
    for obj in bpy.context.scene.objects:
        obj.hide_render = False
    if view_name not in {"03-truman-home", "04-cafe-waterfront"}:
        return
    for obj in bpy.context.scene.objects:
        role = obj.get("truman_role", "")
        location_id = obj.get("location_id", "")
        obj.hide_render = (
            role in {"environment_tree", "street_lamp", "street_micro_scene"}
            or location_id == "town-background"
            or (view_name == "04-cafe-waterfront" and location_id == "plaza")
        )


def main() -> None:
    args = parse_args()
    if bpy.app.version < (5, 2, 0):
        raise RuntimeError(f"Blender 5.2+ is required, found {bpy.app.version_string}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    camera = configure_scene(args.width, args.height)
    views = {
        "01-town-overview": ((-31.0, -35.0, 31.0), (0.0, 1.0, 1.2), 54.0),
        "02-clock-plaza": ((8.5, -11.5, 8.0), (0.0, 0.0, 1.25), 56.0),
        "03-truman-home": ((-5.0, -10.5, 8.0), (-12.0, -2.6, 0.9), 48.0),
        "04-cafe-waterfront": ((-2.8, -0.5, 5.5), (-2.8, 7.0, 1.0), 44.0),
    }
    selected = set(args.view or ())
    for name, (location, target, lens) in views.items():
        if selected and name[3:] not in selected:
            continue
        configure_detail_visibility(name)
        camera.location = location
        camera.data.lens = lens
        look_at(camera, target)
        bpy.context.scene.render.filepath = str(
            (args.output_dir / f"{name}.png").resolve()
        )
        bpy.ops.render.render(write_still=True)
    rendered_count = len(selected) if selected else len(views)
    print(f"Rendered {rendered_count} acceptance views to {args.output_dir}")


if __name__ == "__main__":
    main()
