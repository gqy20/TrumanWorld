#!/usr/bin/env python3
"""Generate scenario-scoped SVG character poses from bundle appearance files."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPOSITORY_ROOT / "art" / "svg_pose_sets.yml"
DEFAULT_SCENARIOS_ROOT = REPOSITORY_ROOT / "scenarios"
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
REQUIRED_COLORS = {
    "outline",
    "hair",
    "skin",
    "skin_shadow",
    "overshirt",
    "overshirt_shadow",
    "tshirt",
    "trousers",
    "shoes",
    "glasses",
    "blush",
    "cup",
}
REQUIRED_POSES = {
    "idle",
    "walk",
    "jog",
    "queue",
    "sit",
    "drink",
    "talk",
    "use_object",
    "wave",
    "think",
    "read",
    "phone",
    "carry",
    "celebrate",
    "surprised",
    "sleep",
}
SUPPORTED_PROPS = {"book", "cup", "parcel", "phone", "tool"}
SUPPORTED_HAIR = {"bob", "long", "messy", "ponytail", "short", "wave"}
SUPPORTED_ACCESSORIES = {"apron", "badge", "none", "tie"}


class SvgConfigurationError(ValueError):
    """Raised when an SVG source configuration is invalid."""


@dataclass(frozen=True)
class Canvas:
    width: int
    height: int
    stroke_width: int


@dataclass(frozen=True)
class Pose:
    body_y: int
    left_arm: int
    right_arm: int
    left_leg: int
    right_leg: int
    expression: str
    prop: str | None


@dataclass(frozen=True)
class Character:
    scenario_id: str
    id: str
    display_name: str
    hair_style: str
    glasses: bool
    accessory: str
    palette: dict[str, str]
    poses: dict[str, Pose]

    @property
    def visual_asset_id(self) -> str:
        return f"{self.scenario_id}/{self.id}"


@dataclass(frozen=True)
class SvgPlan:
    canvas: Canvas
    output_root: Path
    characters: tuple[Character, ...]


def load_plan(
    path: Path = DEFAULT_CONFIG, scenarios_root: Path = DEFAULT_SCENARIOS_ROOT
) -> SvgPlan:
    raw = _load_yaml(path)
    if raw.get("schema_version") != 1:
        raise SvgConfigurationError("SVG pose configuration requires schema_version: 1")
    raw_canvas = _mapping(raw, "canvas")
    canvas = Canvas(
        width=_positive_int(raw_canvas.get("width"), "canvas.width"),
        height=_positive_int(raw_canvas.get("height"), "canvas.height"),
        stroke_width=_positive_int(
            raw_canvas.get("stroke_width"), "canvas.stroke_width"
        ),
    )
    output_root = _repository_path(_string(raw, "output_root"))
    raw_pose_sets = _mapping(raw, "pose_sets")
    characters: list[Character] = []
    for scenario_root in sorted(
        path for path in scenarios_root.iterdir() if path.is_dir()
    ):
        visuals_path = scenario_root / "visuals.yml"
        if not visuals_path.is_file():
            continue
        visuals = _load_yaml(visuals_path)
        if visuals.get("schema_version") != 1 or visuals.get("style") != "svg_flat_v1":
            raise SvgConfigurationError(f"invalid scenario visuals: {visuals_path}")
        pose_set_id = _string(visuals, "pose_set")
        raw_poses = raw_pose_sets.get(pose_set_id)
        if not isinstance(raw_poses, dict):
            raise SvgConfigurationError(
                f"scenario {scenario_root.name} references unknown pose set: {pose_set_id}"
            )
        poses = _parse_poses(pose_set_id, raw_poses)
        agents_root = scenario_root / "agents"
        for agent_root in sorted(
            path for path in agents_root.iterdir() if path.is_dir()
        ):
            appearance_path = agent_root / "appearance.yml"
            if not appearance_path.is_file():
                continue
            if not (agent_root / "agent.yml").is_file():
                raise SvgConfigurationError(
                    f"appearance has no agent.yml: {appearance_path}"
                )
            characters.append(
                _parse_character(
                    scenario_root.name, agent_root.name, appearance_path, poses
                )
            )
    if not characters:
        raise SvgConfigurationError("no scenario character appearance files found")
    return SvgPlan(canvas=canvas, output_root=output_root, characters=tuple(characters))


def render_character(character: Character, pose_id: str, canvas: Canvas) -> str:
    if pose_id not in character.poses:
        raise SvgConfigurationError(
            f"character {character.visual_asset_id} has no pose: {pose_id}"
        )
    pose = character.poses[pose_id]
    c = character.palette
    back_hair, front_hair = _hair(character.hair_style, c)
    glasses = _glasses(c) if character.glasses else ""
    eyes = _eyes(pose.expression, c)
    mouth = _mouth(pose.expression, c)
    accessory = _accessory(character.accessory, c)
    prop = _prop(pose.prop, c)
    title = html.escape(f"{character.display_name} — {pose_id}")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{canvas.width}" height="{canvas.height}" viewBox="0 0 192 256">
  <title>{title}</title>
  <desc>Deterministic transparent Truman World character sprite.</desc>
  <g transform="translate(0 {pose.body_y})" stroke="{c["outline"]}" stroke-width="{canvas.stroke_width}" stroke-linecap="round" stroke-linejoin="round">
    {back_hair}
    <g aria-label="back-leg" transform="rotate({pose.right_leg}, 108, 170)">
      <rect x="98" y="162" width="25" height="66" rx="12" fill="{c["trousers"]}"/>
      <path d="M99 218h27l9 10c3 4 1 10-5 10H99z" fill="{c["shoes"]}"/>
    </g>
    <g aria-label="back-arm" transform="rotate({pose.right_arm}, 126, 116)">
      <rect x="116" y="108" width="23" height="68" rx="11" fill="{c["overshirt_shadow"]}"/>
      <circle cx="128" cy="178" r="11" fill="{c["skin"]}"/>
    </g>
    <g aria-label="front-leg" transform="rotate({pose.left_leg}, 83, 170)">
      <rect x="70" y="162" width="27" height="67" rx="12" fill="{c["trousers"]}"/>
      <path d="M68 219h29v19H61c-7 0-9-8-3-12z" fill="{c["shoes"]}"/>
    </g>
    <path d="M73 109c12-9 34-9 46 0l12 65H62z" fill="{c["tshirt"]}"/>
    <path d="M71 108l23 12-7 58H55l4-46c2-12 5-20 12-24z" fill="{c["overshirt"]}"/>
    <path d="M119 108l-24 12 7 58h34l-5-47c-2-11-6-19-12-23z" fill="{c["overshirt"]}"/>
    <path d="M95 121v54M63 153h20m28 0h19" fill="none" stroke="{c["overshirt_shadow"]}" stroke-width="3"/>
    {accessory}
    <g aria-label="front-arm" transform="rotate({pose.left_arm}, 64, 116)">
      <rect x="52" y="108" width="23" height="69" rx="11" fill="{c["overshirt"]}"/>
      <circle cx="63" cy="179" r="11" fill="{c["skin"]}"/>
    </g>
    <rect x="84" y="91" width="23" height="28" rx="10" fill="{c["skin_shadow"]}"/>
    <circle cx="52" cy="67" r="11" fill="{c["skin"]}"/>
    <circle cx="139" cy="67" r="11" fill="{c["skin"]}"/>
    <path d="M51 51c3-27 20-41 44-41 25 0 43 16 45 42l-4 28c-5 21-21 34-41 34-21 0-37-14-42-35z" fill="{c["skin"]}"/>
    {front_hair}
    {glasses}
    {eyes}
    <path d="M92 76c2 2 5 2 7 0" fill="none" stroke="{c["skin_shadow"]}" stroke-width="2"/>
    {mouth}
    <circle cx="66" cy="80" r="5" fill="{c["blush"]}" opacity="0.32" stroke="none"/>
    <circle cx="124" cy="80" r="5" fill="{c["blush"]}" opacity="0.32" stroke="none"/>
    {prop}
  </g>
</svg>
'''
    return re.sub(r"^[ \t]+$", "", svg, flags=re.MULTILINE)


def generate(
    plan: SvgPlan,
    *,
    scenario_id: str | None = None,
    character_id: str | None = None,
    check: bool = False,
) -> list[Path]:
    selected = [
        character
        for character in plan.characters
        if (scenario_id is None or character.scenario_id == scenario_id)
        and (character_id is None or character.id == character_id)
    ]
    if not selected:
        raise SvgConfigurationError("no characters matched the requested filters")
    outputs: list[Path] = []
    stale: list[Path] = []
    for character in selected:
        character_dir = (
            plan.output_root
            / character.scenario_id
            / "characters"
            / character.id
            / "vector"
        )
        for pose_id in sorted(character.poses):
            output = character_dir / f"{pose_id}.svg"
            _write_or_check(
                output, render_character(character, pose_id, plan.canvas), check, stale
            )
            outputs.append(output)
        manifest = character_dir / "manifest.json"
        manifest_content = (
            json.dumps(
                {
                    "schema_version": 1,
                    "visual_asset_id": character.visual_asset_id,
                    "display_name": character.display_name,
                    "format": "svg",
                    "poses": sorted(character.poses),
                    "transparent_background": True,
                    "generator": "scripts/assets/generate_svg_characters.py",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        _write_or_check(manifest, manifest_content, check, stale)
        outputs.append(manifest)
    # A character-only run must not replace the scenario index with a partial list.
    # Scenario-wide and repository-wide runs own the aggregate manifests.
    indexed_scenarios = (
        sorted({character.scenario_id for character in selected})
        if character_id is None
        else []
    )
    for current_scenario in indexed_scenarios:
        assets = [
            {
                "character_id": character.id,
                "visual_asset_id": character.visual_asset_id,
            }
            for character in plan.characters
            if character.scenario_id == current_scenario
        ]
        manifest = plan.output_root / current_scenario / "characters" / "manifest.json"
        content = (
            json.dumps(
                {
                    "schema_version": 1,
                    "scenario_id": current_scenario,
                    "characters": assets,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        _write_or_check(manifest, content, check, stale)
        outputs.append(manifest)
    if stale:
        raise SvgConfigurationError(
            "generated SVG assets are stale: " + ", ".join(str(path) for path in stale)
        )
    return outputs


def _parse_character(
    scenario_id: str, character_id: str, path: Path, poses: dict[str, Pose]
) -> Character:
    if not SAFE_ID.fullmatch(scenario_id) or not SAFE_ID.fullmatch(character_id):
        raise SvgConfigurationError(
            f"invalid visual asset id: {scenario_id}/{character_id}"
        )
    raw = _load_yaml(path)
    if raw.get("schema_version") != 1:
        raise SvgConfigurationError(f"appearance requires schema_version: 1: {path}")
    palette = _mapping(raw, "palette")
    missing = sorted(REQUIRED_COLORS - palette.keys())
    if missing:
        raise SvgConfigurationError(
            f"appearance {path} is missing colors: {', '.join(missing)}"
        )
    normalized: dict[str, str] = {}
    for color_id, value in palette.items():
        if not isinstance(value, str) or not HEX_COLOR.fullmatch(value):
            raise SvgConfigurationError(
                f"appearance {path} color {color_id} must be #RRGGBB"
            )
        normalized[color_id] = value.upper()
    hair_style = _string(raw, "hair_style")
    accessory = _string(raw, "accessory")
    glasses = raw.get("glasses")
    if hair_style not in SUPPORTED_HAIR or accessory not in SUPPORTED_ACCESSORIES:
        raise SvgConfigurationError(
            f"appearance {path} uses an unsupported visual component"
        )
    if not isinstance(glasses, bool):
        raise SvgConfigurationError(f"appearance {path} glasses must be a boolean")
    return Character(
        scenario_id=scenario_id,
        id=character_id,
        display_name=_string(raw, "display_name"),
        hair_style=hair_style,
        glasses=glasses,
        accessory=accessory,
        palette=normalized,
        poses=poses,
    )


def _parse_poses(pose_set_id: str, raw: dict[str, Any]) -> dict[str, Pose]:
    if set(raw) != REQUIRED_POSES:
        raise SvgConfigurationError(
            f"pose set {pose_set_id} must define exactly 16 standard poses"
        )
    poses: dict[str, Pose] = {}
    for pose_id, value in raw.items():
        if not isinstance(value, dict):
            raise SvgConfigurationError(f"pose {pose_id} must be an object")
        prop = value.get("prop")
        if prop is not None and prop not in SUPPORTED_PROPS:
            raise SvgConfigurationError(f"pose {pose_id} has unsupported prop: {prop}")
        poses[pose_id] = Pose(
            body_y=_integer(value.get("body_y"), f"pose {pose_id}.body_y"),
            left_arm=_angle(value.get("left_arm"), f"pose {pose_id}.left_arm"),
            right_arm=_angle(value.get("right_arm"), f"pose {pose_id}.right_arm"),
            left_leg=_angle(value.get("left_leg"), f"pose {pose_id}.left_leg"),
            right_leg=_angle(value.get("right_leg"), f"pose {pose_id}.right_leg"),
            expression=_string(value, "expression"),
            prop=prop,
        )
    return poses


def _hair(style: str, c: dict[str, str]) -> tuple[str, str]:
    color = c["hair"]
    if style == "bob":
        return (
            f'<path d="M48 58C48 24 67 5 96 5c31 0 50 20 50 55l-3 25c-2 10-10 18-22 20H76c-13-2-21-10-23-21z" fill="{color}"/>',
            f'<path d="M50 55C52 23 70 7 97 7c23 0 40 13 46 36-15 1-28-5-37-15-11 14-30 23-56 27zM52 43c-9 15-10 43 2 61l10-11c-6-17-6-32 0-45zm88 0c10 16 10 43-2 61l-10-11c6-18 6-33 0-46z" fill="{color}"/>',
        )
    if style == "long":
        return (
            f'<path d="M44 58C44 20 65 2 96 2c33 0 53 21 53 59l-2 94-30 13-15-52H78l-12 52-26-13z" fill="{color}"/>',
            f'<path d="M49 55C51 22 70 6 97 6c25 0 42 14 47 39-17-1-29-7-38-17-12 15-31 23-57 27z" fill="{color}"/>',
        )
    if style == "ponytail":
        return (
            f'<path d="M49 59C49 23 68 5 97 5c30 0 48 19 48 54l-5 32H54zM140 43c28 2 34 30 18 49-4-18-13-25-25-28z" fill="{color}"/>',
            f'<path d="M50 55C52 23 70 7 97 7c23 0 40 13 46 36-15 1-28-5-37-15-11 14-30 23-56 27z" fill="{color}"/>',
        )
    if style == "messy":
        return (
            f'<path d="M48 61C47 27 67 7 95 6c32-1 51 20 51 54l-6 28H53z" fill="{color}"/>',
            f'<path d="M48 57l9-30 10 8 10-23 13 12 13-19 9 19 17-10 3 21 14-2-4 22c-16-2-27-10-35-22-13 14-31 22-59 24z" fill="{color}"/>',
        )
    if style == "wave":
        return (
            f'<path d="M48 60C48 25 67 5 96 5c31 0 50 20 50 55l-5 31H52z" fill="{color}"/>',
            f'<path d="M49 55c5-34 25-49 49-49 24 0 41 13 47 36-9-6-17-6-25 0-8-14-18-17-28-4-9-12-20-10-29 5z" fill="{color}"/>',
        )
    return (
        f'<path d="M49 59C49 25 68 6 96 6c30 0 48 19 48 53l-5 25H54z" fill="{color}"/>',
        f'<path d="M49 54C52 23 70 7 97 7c22 0 39 12 45 34-16 2-28-3-38-13-13 13-31 21-55 26z" fill="{color}"/>',
    )


def _glasses(c: dict[str, str]) -> str:
    color = c["glasses"]
    return f'<circle cx="76" cy="65" r="15" fill="none" stroke="{color}"/><circle cx="115" cy="65" r="15" fill="none" stroke="{color}"/><path d="M91 64h9m-39-3-8-2m77 2 8-2" fill="none" stroke="{color}"/>'


def _eyes(expression: str, c: dict[str, str]) -> str:
    if expression == "asleep":
        return f'<path d="M72 68h10m27 0h10" stroke="{c["glasses"]}" stroke-width="3" fill="none"/>'
    radius = "5" if expression == "surprised" else "3.5"
    return f'<circle cx="77" cy="67" r="{radius}" fill="{c["glasses"]}" stroke="none"/><circle cx="114" cy="67" r="{radius}" fill="{c["glasses"]}" stroke="none"/>'


def _mouth(expression: str, c: dict[str, str]) -> str:
    if expression in {"smile", "content", "delighted"}:
        return f'<path d="M86 88c6 6 13 6 19 0" fill="none" stroke="{c["skin_shadow"]}" stroke-width="3"/>'
    if expression == "surprised":
        return (
            f'<circle cx="96" cy="91" r="5" fill="{c["skin_shadow"]}" stroke="none"/>'
        )
    return f'<path d="M88 90c5 2 10 2 15 0" fill="none" stroke="{c["skin_shadow"]}" stroke-width="3"/>'


def _accessory(accessory: str, c: dict[str, str]) -> str:
    if accessory == "tie":
        return f'<path d="M91 115h10l3 10-8 31-8-31z" fill="{c["outline"]}"/>'
    if accessory == "apron":
        return f'<path d="M76 125h40l5 51H71z" fill="{c["tshirt"]}" opacity="0.92"/><path d="M82 145h28" fill="none" stroke="{c["overshirt_shadow"]}" stroke-width="3"/>'
    if accessory == "badge":
        return f'<rect x="108" y="128" width="13" height="9" rx="2" fill="{c["tshirt"]}" stroke-width="2"/>'
    return ""


def _prop(prop: str | None, c: dict[str, str]) -> str:
    if prop is None:
        return ""
    if prop == "cup":
        return f'<g transform="translate(146 126)"><rect width="18" height="22" rx="5" fill="{c["cup"]}"/><path d="M18 6h4c8 0 8 11 0 11h-4" fill="none"/><path d="M5 4h8" stroke="{c["tshirt"]}" stroke-width="2"/></g>'
    if prop == "book":
        return f'<path d="M63 145c12-5 23-3 33 4v30c-10-7-21-9-33-4z" fill="{c["cup"]}"/><path d="M129 145c-12-5-23-3-33 4v30c10-7 21-9 33-4z" fill="{c["tshirt"]}"/><path d="M96 150v29" fill="none" stroke-width="2"/>'
    if prop == "phone":
        return f'<g transform="translate(148 63) rotate(8)"><rect width="15" height="27" rx="4" fill="{c["glasses"]}"/><rect x="3" y="4" width="9" height="16" rx="2" fill="{c["overshirt"]}" stroke="none"/></g>'
    if prop == "parcel":
        return f'<rect x="70" y="143" width="52" height="39" rx="4" fill="{c["cup"]}"/><path d="M96 143v39m-26-26h52" fill="none" stroke="{c["tshirt"]}" stroke-width="3"/>'
    return f'<g transform="translate(145 124) rotate(-20)"><path d="M8 3c-7 5-5 14 2 17l-9 24 9 4 10-24c8 0 12-9 7-16l-7 8-7-3z" fill="{c["glasses"]}"/></g>'


def _write_or_check(path: Path, content: str, check: bool, stale: list[Path]) -> None:
    if check:
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            stale.append(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SvgConfigurationError(f"missing configuration: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SvgConfigurationError(f"configuration must be an object: {path}")
    return raw


def _repository_path(value: str) -> Path:
    candidate = (REPOSITORY_ROOT / value).resolve()
    if not candidate.is_relative_to(REPOSITORY_ROOT):
        raise SvgConfigurationError(f"path escapes repository: {value}")
    return candidate


def _mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise SvgConfigurationError(f"{key} must be an object")
    return result


def _string(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise SvgConfigurationError(f"{key} must be a non-empty string")
    return result.strip()


def _integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SvgConfigurationError(f"{label} must be an integer")
    return value


def _positive_int(value: Any, label: str) -> int:
    result = _integer(value, label)
    if result <= 0:
        raise SvgConfigurationError(f"{label} must be positive")
    return result


def _angle(value: Any, label: str) -> int:
    result = _integer(value, label)
    if not -160 <= result <= 160:
        raise SvgConfigurationError(f"{label} must be between -160 and 160")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scenarios-root", type=Path, default=DEFAULT_SCENARIOS_ROOT)
    parser.add_argument("--scenario")
    parser.add_argument("--character")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        outputs = generate(
            load_plan(args.config.resolve(), args.scenarios_root.resolve()),
            scenario_id=args.scenario,
            character_id=args.character,
            check=args.check,
        )
    except SvgConfigurationError as exc:
        print(f"SVG pipeline error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "check": args.check, "output_count": len(outputs)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
