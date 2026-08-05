"""Build a rigged low-poly character with deterministic animations in Blender 5.2."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import bpy
from mathutils import Color, Vector

REQUIRED_BLENDER = (5, 2)
FPS = 24
ANIMATIONS = {
    "idle": 48,
    "walk": 24,
    "jog": 18,
    "turn_left": 18,
    "turn_right": 18,
    "sit": 24,
    "drink": 48,
    "queue": 48,
    "talk": 36,
    "use_object": 36,
    "wave": 32,
    "think": 48,
    "read": 48,
    "phone": 40,
    "carry": 36,
    "celebrate": 32,
    "surprised": 32,
    "sleep": 48,
}
BONE_SPECS = {
    "root": ((0, 0, 0.02), (0, 0, 0.22), None),
    "pelvis": ((0, 0, 0.78), (0, 0, 1.02), "root"),
    "spine": ((0, 0, 1.02), (0, 0, 1.52), "pelvis"),
    "head": ((0, 0, 1.52), (0, 0, 1.96), "spine"),
    "upper_arm.L": ((-0.27, 0, 1.43), (-0.56, 0, 1.17), "spine"),
    "forearm.L": ((-0.56, 0, 1.17), (-0.67, 0, 0.91), "upper_arm.L"),
    "hand.L": ((-0.67, 0, 0.91), (-0.70, 0, 0.74), "forearm.L"),
    "upper_arm.R": ((0.27, 0, 1.43), (0.56, 0, 1.17), "spine"),
    "forearm.R": ((0.56, 0, 1.17), (0.67, 0, 0.91), "upper_arm.R"),
    "hand.R": ((0.67, 0, 0.91), (0.70, 0, 0.74), "forearm.R"),
    "thigh.L": ((-0.14, 0, 0.84), (-0.14, 0, 0.46), "pelvis"),
    "shin.L": ((-0.14, 0, 0.46), (-0.14, 0, 0.08), "thigh.L"),
    "thigh.R": ((0.14, 0, 0.84), (0.14, 0, 0.46), "pelvis"),
    "shin.R": ((0.14, 0, 0.46), (0.14, 0, 0.08), "thigh.R"),
}


def parse_args() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--config-json", required=True)
    return parser.parse_args(arguments)


def require_blender_version() -> None:
    if bpy.app.version[:2] != REQUIRED_BLENDER:
        raise RuntimeError(f"Blender 5.2.x required, got {bpy.app.version_string}")


def reset_scene() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.fps = FPS
    bpy.context.preferences.filepaths.save_version = 0


def srgb(hex_color: str) -> tuple[float, float, float, float]:
    value = hex_color.lstrip("#")
    color = Color(tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)))
    color.from_srgb_to_scene_linear()
    return color.r, color.g, color.b, 1.0


def material(name: str, hex_color: str) -> Any:
    result = bpy.data.materials.new(f"TW_{name}")
    color = srgb(hex_color)
    result.diffuse_color = color
    result.use_backface_culling = True
    principled = result.node_tree.nodes.get("Principled BSDF")
    if principled is None:
        raise RuntimeError(f"material has no Principled BSDF: {name}")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = 0.78
    return result


def build_armature(asset_id: str) -> Any:
    data = bpy.data.armatures.new("TrumanHumanoidV1")
    armature = bpy.data.objects.new("CharacterRig", data)
    bpy.context.collection.objects.link(armature)
    armature["visual_asset_id"] = asset_id
    armature["rig_id"] = "truman_humanoid_v1"
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, parent) in BONE_SPECS.items():
        bone = data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        if parent:
            bone.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


def apply_soft_edges(obj: Any, width: float = 0.025) -> None:
    modifier = obj.modifiers.new(name="SoftEdges", type="BEVEL")
    modifier.width = width
    modifier.segments = 2
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.select_set(False)


def skin_object(obj: Any, armature: Any, bone_name: str) -> Any:
    group = obj.vertex_groups.new(name=bone_name)
    group.add(range(len(obj.data.vertices)), 1.0, "REPLACE")
    modifier = obj.modifiers.new(name="CharacterRig", type="ARMATURE")
    modifier.object = armature
    obj.parent = armature
    return obj


def add_box(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    surface: Any,
    armature: Any,
    bone: str,
) -> Any:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(surface)
    apply_soft_edges(obj)
    return skin_object(obj, armature, bone)


def add_sphere(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    surface: Any,
    armature: Any,
    bone: str,
    segments: int = 16,
) -> Any:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=8, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(surface)
    obj.data.shade_smooth()
    return skin_object(obj, armature, bone)


def add_limb(
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    surface: Any,
    armature: Any,
    bone: str,
) -> Any:
    start_vector, end_vector = Vector(start), Vector(end)
    direction = end_vector - start_vector
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius, depth=direction.length)
    obj = bpy.context.object
    obj.name = name
    obj.location = (start_vector + end_vector) / 2
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(surface)
    apply_soft_edges(obj, 0.018)
    return skin_object(obj, armature, bone)


def add_cylinder(
    name: str,
    location: tuple[float, float, float],
    radius: float,
    depth: float,
    surface: Any,
    armature: Any,
    bone: str,
) -> Any:
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(surface)
    apply_soft_edges(obj, 0.012)
    return skin_object(obj, armature, bone)


def build_body(config: dict[str, Any], armature: Any) -> None:
    palette = config["palette"]
    surfaces = {name: material(name, color) for name, color in palette.items()}
    add_box("Torso", (0, 0, 1.26), (0.53, 0.30, 0.55), surfaces["overshirt"], armature, "spine")
    add_box("Shirt", (0, -0.158, 1.31), (0.22, 0.025, 0.40), surfaces["tshirt"], armature, "spine")
    add_box("Pelvis", (0, 0, 0.91), (0.43, 0.28, 0.25), surfaces["trousers"], armature, "pelvis")
    add_sphere("Head", (0, 0, 1.72), (0.255, 0.235, 0.29), surfaces["skin"], armature, "head")
    add_hair(config["hair_style"], surfaces["hair"], armature)
    add_face(bool(config["glasses"]), surfaces, armature)
    add_arms(surfaces, armature)
    add_legs(surfaces, armature)
    add_accessory(config["accessory"], surfaces, armature)
    add_cylinder(
        "CoffeeCup",
        (0.61, -0.16, 1.20),
        0.09,
        0.22,
        surfaces["cup"],
        armature,
        "hand.R",
    )
    add_cylinder(
        "CoffeeCupSurface",
        (0.61, -0.16, 1.315),
        0.074,
        0.012,
        surfaces["outline"],
        armature,
        "hand.R",
    )
    add_box(
        "CoffeeCupHandle",
        (0.71, -0.16, 1.20),
        (0.06, 0.045, 0.12),
        surfaces["cup"],
        armature,
        "hand.R",
    )


def add_hair(style: str, surface: Any, armature: Any) -> None:
    scale = (0.275, 0.25, 0.18 if style == "short" else 0.24)
    add_sphere("Hair", (0, 0.025, 1.88), scale, surface, armature, "head", 12)
    if style == "long":
        add_box("BackHair", (0, 0.10, 1.58), (0.43, 0.18, 0.52), surface, armature, "head")
    elif style == "ponytail":
        add_sphere("Ponytail", (0, 0.25, 1.62), (0.13, 0.14, 0.27), surface, armature, "head", 10)
    elif style == "messy":
        for index, (x, z) in enumerate(((-0.16, 1.98), (0.0, 2.03), (0.16, 1.97))):
            add_sphere(
                f"HairTuft.{index}", (x, 0.02, z), (0.11, 0.10, 0.13), surface, armature, "head", 8
            )
    elif style == "wave":
        add_sphere(
            "HairWave", (-0.13, -0.17, 1.91), (0.17, 0.09, 0.11), surface, armature, "head", 10
        )


def add_face(glasses: bool, surfaces: dict[str, Any], armature: Any) -> None:
    for side, x in (("L", -0.085), ("R", 0.085)):
        add_sphere(
            f"Eye.{side}",
            (x, -0.225, 1.75),
            (0.026, 0.018, 0.034),
            surfaces["glasses"],
            armature,
            "head",
            8,
        )
    add_sphere(
        "Nose",
        (0, -0.245, 1.68),
        (0.035, 0.035, 0.05),
        surfaces["skin_shadow"],
        armature,
        "head",
        8,
    )
    add_box(
        "Mouth", (0, -0.238, 1.61), (0.09, 0.014, 0.018), surfaces["skin_shadow"], armature, "head"
    )
    if glasses:
        add_box(
            "GlassesBridge",
            (0, -0.254, 1.75),
            (0.08, 0.014, 0.014),
            surfaces["glasses"],
            armature,
            "head",
        )
        for side, x in (("L", -0.085), ("R", 0.085)):
            add_sphere(
                f"GlassesLens.{side}",
                (x, -0.252, 1.75),
                (0.072, 0.012, 0.064),
                surfaces["glasses"],
                armature,
                "head",
                10,
            )


def add_arms(surfaces: dict[str, Any], armature: Any) -> None:
    for side, sign in (("L", -1), ("R", 1)):
        upper = ((0.27 * sign, 0, 1.43), (0.56 * sign, 0, 1.17))
        lower = ((0.56 * sign, 0, 1.17), (0.67 * sign, 0, 0.91))
        add_limb(
            f"UpperArm.{side}", *upper, 0.105, surfaces["overshirt"], armature, f"upper_arm.{side}"
        )
        add_limb(f"Forearm.{side}", *lower, 0.09, surfaces["skin"], armature, f"forearm.{side}")
        add_sphere(
            f"Hand.{side}",
            lower[1],
            (0.105, 0.09, 0.11),
            surfaces["skin"],
            armature,
            f"hand.{side}",
            10,
        )


def add_legs(surfaces: dict[str, Any], armature: Any) -> None:
    for side, sign in (("L", -1), ("R", 1)):
        thigh = ((0.14 * sign, 0, 0.84), (0.14 * sign, 0, 0.46))
        shin = ((0.14 * sign, 0, 0.46), (0.14 * sign, 0, 0.08))
        add_limb(f"Thigh.{side}", *thigh, 0.13, surfaces["trousers"], armature, f"thigh.{side}")
        add_limb(f"Shin.{side}", *shin, 0.115, surfaces["trousers"], armature, f"shin.{side}")
        add_box(
            f"Shoe.{side}",
            (0.14 * sign, -0.07, 0.08),
            (0.25, 0.40, 0.15),
            surfaces["shoes"],
            armature,
            f"shin.{side}",
        )


def add_accessory(accessory: str, surfaces: dict[str, Any], armature: Any) -> None:
    if accessory == "tie":
        add_box(
            "Tie", (0, -0.18, 1.27), (0.07, 0.035, 0.30), surfaces["outline"], armature, "spine"
        )
    elif accessory == "badge":
        add_box(
            "Badge", (0.15, -0.18, 1.36), (0.10, 0.025, 0.07), surfaces["tshirt"], armature, "spine"
        )
    elif accessory == "apron":
        add_box(
            "Apron",
            (0, -0.18, 1.16),
            (0.39, 0.03, 0.48),
            surfaces["tshirt"],
            armature,
            "spine",
        )


def reset_pose(armature: Any) -> None:
    for bone in armature.pose.bones:
        bone.rotation_mode = "XYZ"
        bone.rotation_euler = (0, 0, 0)


def key_pose(armature: Any, frame: int, rotations: dict[str, tuple[float, float, float]]) -> None:
    reset_pose(armature)
    for bone_name, rotation in rotations.items():
        armature.pose.bones[bone_name].rotation_euler = rotation
        armature.pose.bones[bone_name].keyframe_insert(
            "rotation_euler", frame=frame, group=bone_name
        )


def create_action(
    armature: Any, name: str, poses: list[tuple[int, dict[str, tuple[float, float, float]]]]
) -> None:
    action = bpy.data.actions.new(name=name)
    action.use_fake_user = True
    armature.animation_data.action = action
    for frame, rotations in poses:
        key_pose(armature, frame, rotations)
    armature.animation_data.action = None


def gait_poses(
    length: int, leg_swing: float, arm_swing: float
) -> list[tuple[int, dict[str, tuple[float, float, float]]]]:
    result = []
    phases = (
        (1, 0.0),
        (length // 4 + 1, math.pi / 2),
        (length // 2 + 1, math.pi),
        (3 * length // 4 + 1, 3 * math.pi / 2),
        (length + 1, math.tau),
    )
    for frame, phase in phases:
        leg = math.cos(phase) * leg_swing
        arm = math.cos(phase) * arm_swing
        result.append(
            (
                frame,
                {
                    "thigh.L": (leg, 0, 0),
                    "thigh.R": (-leg, 0, 0),
                    "upper_arm.L": (-arm, 0, 0),
                    "upper_arm.R": (arm, 0, 0),
                    "spine": (0.03 * abs(math.sin(phase)), 0, 0),
                },
            )
        )
    return result


def turn_poses(length: int, yaw: float) -> list[tuple[int, dict[str, tuple[float, float, float]]]]:
    return [
        (1, {"pelvis": (0, 0, 0)}),
        (length // 2, {"pelvis": (0, 0, yaw), "spine": (0, 0, yaw * 0.5)}),
        (length, {"pelvis": (0, 0, 0)}),
    ]


def seated_pose(overrides: dict[str, tuple[float, float, float]] | None = None) -> dict:
    pose = {
        "spine": (0.16, 0, 0),
        "thigh.L": (-1.25, 0, 0),
        "thigh.R": (-1.25, 0, 0),
        "shin.L": (1.15, 0, 0),
        "shin.R": (1.15, 0, 0),
    }
    pose.update(overrides or {})
    return pose


def drink_poses() -> list[tuple[int, dict]]:
    arm_down = {"upper_arm.R": (0, 0, 0)}
    arm_up = {
        "upper_arm.R": (-0.78, 0.10, -0.34),
        "forearm.R": (-0.82, 0, -0.24),
        "hand.R": (1.48, 0, 0.48),
    }
    sip = {
        "head": (0.08, 0, 0),
        "upper_arm.R": (-0.96, 0.10, -0.40),
        "forearm.R": (-1.02, 0, -0.28),
        "hand.R": (1.86, 0, 0.58),
    }
    return [
        (1, seated_pose(arm_down)),
        (15, seated_pose(arm_up)),
        (29, seated_pose(sip)),
        (39, seated_pose(arm_up)),
        (48, seated_pose(arm_down)),
    ]


def loop_poses(start: dict, middle: dict, length: int) -> list[tuple[int, dict]]:
    return [(1, start), (length // 2, middle), (length, start)]


def wave_poses() -> list[tuple[int, dict]]:
    left = {"upper_arm.R": (-0.18, 0, -1.85), "forearm.R": (-0.25, 0, -0.45)}
    right = {"upper_arm.R": (-0.18, 0, -1.85), "forearm.R": (-0.25, 0, 0.35)}
    return [(1, left), (11, right), (21, left), (32, right)]


def social_action_poses() -> dict[str, list[tuple[int, dict]]]:
    talk_start = {"upper_arm.R": (-0.30, 0, -0.12)}
    talk_gesture = {
        "spine": (0, 0, -0.08),
        "upper_arm.R": (-0.65, 0, -0.42),
        "forearm.R": (-0.45, 0, 0.22),
    }
    think = {"head": (0.08, 0, 0), "upper_arm.R": (-0.62, 0, -0.22), "forearm.R": (-0.92, 0, -0.18)}
    thinking = {
        "head": (0.12, 0, 0.10),
        "upper_arm.R": (-0.68, 0, -0.28),
        "forearm.R": (-1.02, 0, -0.18),
    }
    return {
        "queue": loop_poses(
            {"pelvis": (0, 0, -0.06)}, {"pelvis": (0, 0, 0.06), "head": (0, 0, -0.12)}, 48
        ),
        "talk": loop_poses(talk_start, talk_gesture, 36),
        "wave": wave_poses(),
        "think": loop_poses(think, thinking, 48),
    }


def hands_forward_pose() -> dict:
    return {
        "upper_arm.L": (-0.45, 0, 0.22),
        "upper_arm.R": (-0.45, 0, -0.22),
        "forearm.L": (-0.55, 0, 0),
        "forearm.R": (-0.55, 0, 0),
    }


def object_action_poses() -> dict[str, list[tuple[int, dict]]]:
    hands_forward = hands_forward_pose()
    phone = {"upper_arm.R": (-0.72, 0, -0.30), "forearm.R": (-1.12, 0, -0.22)}
    phone_listen = {
        "head": (0, 0, -0.08),
        "upper_arm.R": (-0.78, 0, -0.35),
        "forearm.R": (-1.18, 0, -0.22),
    }
    return {
        "use_object": loop_poses(
            hands_forward, {**hands_forward, "head": (0.10, 0, 0), "spine": (0.08, 0, 0)}, 36
        ),
        "read": loop_poses(hands_forward, {**hands_forward, "head": (0.14, 0, 0)}, 48),
        "phone": loop_poses(phone, phone_listen, 40),
        "carry": loop_poses(hands_forward, {**hands_forward, "spine": (0.06, 0, 0)}, 36),
    }


def celebrate_poses(arms_up: dict) -> list[tuple[int, dict]]:
    return [
        (1, arms_up),
        (9, {**arms_up, "pelvis": (0.10, 0, 0)}),
        (17, arms_up),
        (25, {**arms_up, "pelvis": (-0.08, 0, 0)}),
        (32, arms_up),
    ]


def reaction_action_poses() -> dict[str, list[tuple[int, dict]]]:
    arms_up = {
        "upper_arm.L": (-0.30, 0, 0.92),
        "upper_arm.R": (-0.30, 0, -0.92),
        "forearm.L": (-0.18, 0, 0),
        "forearm.R": (-0.18, 0, 0),
    }
    arms_out = {
        "upper_arm.L": (-0.30, 0, 0.65),
        "upper_arm.R": (-0.30, 0, -0.65),
        "head": (-0.12, 0, 0),
    }
    return {
        "celebrate": celebrate_poses(arms_up),
        "surprised": loop_poses(arms_out, {**arms_out, "spine": (-0.10, 0, 0)}, 32),
        "sleep": loop_poses(
            seated_pose({"spine": (0.48, 0, 0), "head": (0.34, 0, -0.08)}),
            seated_pose({"spine": (0.52, 0, 0), "head": (0.38, 0, 0.08)}),
            48,
        ),
    }


def animation_poses() -> dict[str, list[tuple[int, dict]]]:
    poses = {
        "idle": [
            (1, {"spine": (0.01, 0, 0)}),
            (24, {"spine": (-0.015, 0, 0), "head": (0.015, 0, 0)}),
            (48, {"spine": (0.01, 0, 0)}),
        ],
        "walk": gait_poses(24, 0.48, 0.42),
        "jog": gait_poses(18, 0.72, 0.62),
        "turn_left": turn_poses(18, 0.35),
        "turn_right": turn_poses(18, -0.35),
        "sit": [(1, {"spine": (0, 0, 0)}), (24, seated_pose({"spine": (0.18, 0, 0)}))],
        "drink": drink_poses(),
    }
    for group in (social_action_poses(), object_action_poses(), reaction_action_poses()):
        poses.update(group)
    return poses


def build_animations(armature: Any) -> None:
    armature.animation_data_create()
    for name, poses in animation_poses().items():
        create_action(armature, name, poses)
    reset_pose(armature)


def validate_scene(armature: Any) -> dict[str, int]:
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    for obj in meshes:
        if not obj.data.vertices or obj.data.validate(clean_customdata=False):
            raise RuntimeError(f"invalid character mesh: {obj.name}")
    if len(armature.data.bones) != 14 or set(ANIMATIONS) != set(bpy.data.actions.keys()):
        raise RuntimeError("character rig or animation contract is incomplete")
    return {
        "objects": len(bpy.context.scene.objects),
        "meshes": len(meshes),
        "vertices": sum(len(obj.data.vertices) for obj in meshes),
        "polygons": sum(len(obj.data.polygons) for obj in meshes),
        "bones": len(armature.data.bones),
        "animations": len(bpy.data.actions),
    }


def export_glb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = bpy.ops.export_scene.gltf(
        filepath=str(path),
        check_existing=False,
        export_format="GLB",
        use_selection=False,
        export_yup=True,
        export_apply=False,
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
        export_extras=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_skins=True,
        export_morph=False,
    )
    if result != {"FINISHED"} or not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"glTF export failed: {path}")


def main() -> None:
    args = parse_args()
    config = json.loads(args.config_json)
    require_blender_version()
    reset_scene()
    asset_id = f"{config['scenario_id']}/{config['character_id']}"
    armature = build_armature(asset_id)
    build_body(config, armature)
    build_animations(armature)
    stats = validate_scene(armature)
    args.source.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.source.resolve()), check_existing=False)
    export_glb(args.output.resolve())
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "visual_asset_id": asset_id,
                "format": "glb",
                "rig_id": "truman_humanoid_v1",
                "animations": ANIMATIONS,
                "cycle_distance_m": {"walk": 1.04, "jog": 1.32},
                "state_offsets_m": {
                    "sit": [0.0, -0.32, 0.08],
                    "drink": [0.0, -0.32, 0.08],
                    "sleep": [0.0, -0.32, 0.08],
                },
                "blender_version": bpy.app.version_string,
                "stats": stats,
                "generator": "scripts/assets/blender/build_character.py",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "asset_id": asset_id, "stats": stats}))


if __name__ == "__main__":
    main()
