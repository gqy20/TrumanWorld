#!/usr/bin/env python3
"""Build configured 3D characters with the pinned Blender toolchain."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BLENDER = ROOT / ".tools" / "blender" / "blender"
BUILDER = ROOT / "scripts" / "assets" / "blender" / "build_character.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--character")
    selection.add_argument("--all-enabled", action="store_true")
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    return parser.parse_args()


def load_config(scenario_id: str, character_id: str) -> dict[str, Any]:
    appearance_path = ROOT / "scenarios" / scenario_id / "agents" / character_id / "appearance.yml"
    raw = yaml.safe_load(appearance_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError(f"invalid appearance configuration: {appearance_path}")
    model = raw.get("model_3d")
    if not isinstance(model, dict) or model.get("builder") != "stylized_humanoid_v1":
        raise ValueError(f"3D model is not enabled for {scenario_id}/{character_id}")
    return {
        "schema_version": 1,
        "scenario_id": scenario_id,
        "character_id": character_id,
        "display_name": raw["display_name"],
        "hair_style": raw["hair_style"],
        "glasses": raw["glasses"],
        "accessory": raw["accessory"],
        "palette": raw["palette"],
        "builder": model["builder"],
    }


def enabled_characters(scenario_id: str) -> list[str]:
    agents_root = ROOT / "scenarios" / scenario_id / "agents"
    result: list[str] = []
    for appearance_path in sorted(agents_root.glob("*/appearance.yml")):
        raw = yaml.safe_load(appearance_path.read_text(encoding="utf-8"))
        model = raw.get("model_3d") if isinstance(raw, dict) else None
        if isinstance(model, dict) and model.get("builder") == "stylized_humanoid_v1":
            result.append(appearance_path.parent.name)
    return result


def build_command(
    scenario_id: str,
    character_id: str,
    blender: Path,
    config: dict[str, Any],
) -> list[str]:
    asset_root = ROOT / "godot" / "world-client" / "assets" / "scenarios"
    output_dir = asset_root / scenario_id / "characters" / character_id / "model"
    source = ROOT / "art" / "blender" / "characters" / scenario_id / f"{character_id}.blend"
    return [
        str(blender.resolve()),
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(BUILDER),
        "--",
        "--output",
        str(output_dir / "character.glb"),
        "--source",
        str(source),
        "--metadata",
        str(output_dir / "manifest.json"),
        "--config-json",
        json.dumps(config, ensure_ascii=True, sort_keys=True),
    ]


def main() -> int:
    args = parse_args()
    if not args.blender.is_file() or not BUILDER.is_file():
        raise FileNotFoundError("Blender or animated character builder is missing")
    character_ids = enabled_characters(args.scenario) if args.all_enabled else [args.character]
    if not character_ids:
        raise ValueError(f"no 3D characters are enabled for {args.scenario}")
    for character_id in character_ids:
        config = load_config(args.scenario, character_id)
        command = build_command(args.scenario, character_id, args.blender, config)
        subprocess.run(command, cwd=ROOT, check=True)
    print(
        json.dumps(
            {
                "ok": True,
                "visual_asset_ids": [f"{args.scenario}/{item}" for item in character_ids],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
