"""Render a deterministic review image for a generated character blend file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--animation", default="idle")
    parser.add_argument("--frame", type=int, default=1)
    return parser.parse_args(arguments)


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_light(name: str, location: tuple[float, float, float], energy: float, size: float) -> None:
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    light = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(light)
    light.location = location
    look_at(light, (0, 0, 1.0))


def configure_scene(output: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output)
    scene.render.film_transparent = False
    scene.world.color = (0.035, 0.045, 0.055)
    scene.view_settings.look = "AgX - Medium High Contrast"


def add_camera() -> None:
    data = bpy.data.cameras.new("CharacterPreviewCamera")
    camera = bpy.data.objects.new("CharacterPreviewCamera", data)
    bpy.context.collection.objects.link(camera)
    camera.location = (3.0, -4.8, 2.45)
    data.lens = 68
    look_at(camera, (0, 0, 1.05))
    bpy.context.scene.camera = camera


def add_ground() -> None:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=1.15, depth=0.08, location=(0, 0, -0.05)
    )
    ground = bpy.context.object
    ground.name = "CharacterPreviewGround"
    material = bpy.data.materials.new("CharacterPreviewGround")
    material.diffuse_color = (0.12, 0.15, 0.17, 1.0)
    ground.data.materials.append(material)


def apply_pose(animation_name: str, frame: int) -> None:
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    action = bpy.data.actions.get(animation_name)
    if len(armatures) != 1 or action is None:
        raise RuntimeError(f"preview animation is unavailable: {animation_name}")
    armature = armatures[0]
    armature.animation_data_create()
    armature.animation_data.action = action
    bpy.context.scene.frame_set(frame)
    for obj in bpy.context.scene.objects:
        if obj.name.startswith("CoffeeCup"):
            obj.hide_render = animation_name != "drink"


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    configure_scene(args.output.resolve())
    add_camera()
    add_ground()
    add_light("CharacterKey", (-3.0, -4.0, 5.0), 900.0, 3.0)
    add_light("CharacterFill", (3.5, -1.0, 2.8), 550.0, 2.5)
    add_light("CharacterRim", (0.0, 3.0, 4.0), 750.0, 2.0)
    apply_pose(args.animation, args.frame)
    bpy.context.scene.render.image_settings.color_mode = "RGBA"
    bpy.ops.render.render(write_still=True)
    if not args.output.is_file() or args.output.stat().st_size == 0:
        raise RuntimeError(f"character preview was not rendered: {args.output}")


if __name__ == "__main__":
    main()
