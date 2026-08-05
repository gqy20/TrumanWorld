from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUILDER_PATH = ROOT / "scripts" / "assets" / "build_3d_character.py"
SPEC = importlib.util.spec_from_file_location("truman_3d_character", BUILDER_PATH)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def test_truman_3d_config_reuses_scenario_appearance() -> None:
    config = builder.load_config("narrative_world", "truman")

    assert config["builder"] == "stylized_humanoid_v1"
    assert config["palette"]["overshirt"] == "#5B8AA4"
    assert config["hair_style"] == "short"


def test_blender_command_uses_isolated_animated_builder() -> None:
    config = builder.load_config("narrative_world", "truman")
    command = builder.build_command(
        "narrative_world",
        "truman",
        ROOT / ".tools" / "blender" / "blender",
        config,
    )

    assert command[1:5] == ["--background", "--factory-startup", "--python-exit-code", "1"]
    assert "build_character.py" in command[6]
    assert json.loads(command[-1])["character_id"] == "truman"


def test_narrative_world_enables_3d_for_every_resident() -> None:
    assert builder.enabled_characters("narrative_world") == [
        "alice",
        "bob",
        "friend",
        "neighbor",
        "spouse",
        "truman",
    ]


def test_checked_in_resident_models_share_rig_and_animation_contract() -> None:
    for character_id in builder.enabled_characters("narrative_world"):
        path = (
            ROOT
            / "godot/world-client/assets/scenarios/narrative_world/characters"
            / character_id
            / "model/manifest.json"
        )
        manifest = json.loads(path.read_text(encoding="utf-8"))

        assert manifest["rig_id"] == "truman_humanoid_v1"
        assert set(manifest["animations"]) == {
            "idle",
            "walk",
            "jog",
            "turn_left",
            "turn_right",
            "sit",
            "drink",
            "queue",
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
        assert manifest["state_offsets_m"]["sit"] == [0.0, -0.32, 0.08]
        assert manifest["state_offsets_m"]["sleep"] == [0.0, -0.32, 0.08]
        assert manifest["stats"]["bones"] == 14
        assert manifest["stats"]["polygons"] < 20_000
