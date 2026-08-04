from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GENERATOR_PATH = ROOT / "scripts" / "assets" / "generate_svg_characters.py"
SPEC = importlib.util.spec_from_file_location("truman_svg_characters", GENERATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
generator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generator
SPEC.loader.exec_module(generator)


def test_plan_discovers_scenario_scoped_characters() -> None:
    plan = generator.load_plan()
    by_asset_id = {character.visual_asset_id: character for character in plan.characters}

    assert len(plan.characters) == 9
    assert "campus_world/mei" in by_asset_id
    assert {
        "narrative_world/truman",
        "narrative_world/spouse",
        "narrative_world/friend",
        "narrative_world/neighbor",
        "narrative_world/alice",
        "narrative_world/bob",
    }.issubset(by_asset_id)
    assert all(set(character.poses) == generator.REQUIRED_POSES for character in plan.characters)


def test_svg_render_is_deterministic_transparent_and_appearance_specific() -> None:
    plan = generator.load_plan()
    by_asset_id = {character.visual_asset_id: character for character in plan.characters}
    mei = by_asset_id["campus_world/mei"]
    truman = by_asset_id["narrative_world/truman"]

    first = generator.render_character(mei, "idle", plan.canvas)
    second = generator.render_character(mei, "idle", plan.canvas)
    truman_svg = generator.render_character(truman, "idle", plan.canvas)

    assert first == second
    assert first != truman_svg
    assert "background" not in first.lower()
    assert ET.fromstring(first).tag == "{http://www.w3.org/2000/svg}svg"
    assert "Truman" in truman_svg


def test_checked_in_svg_assets_match_generator() -> None:
    outputs = generator.generate(generator.load_plan(), check=True)

    assert len(outputs) == 155
    assert all(path.is_file() for path in outputs)


def test_character_only_generation_does_not_replace_scenario_manifest(
    tmp_path: Path,
) -> None:
    plan = replace(generator.load_plan(), output_root=tmp_path)
    generator.generate(plan, scenario_id="narrative_world")
    manifest = tmp_path / "narrative_world" / "characters" / "manifest.json"
    original = manifest.read_text(encoding="utf-8")

    outputs = generator.generate(
        plan,
        scenario_id="narrative_world",
        character_id="truman",
    )

    assert len(outputs) == 17
    assert manifest.read_text(encoding="utf-8") == original
