from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.scenario.spatial_manifest import (
    ExportedWorldMap,
    calculate_world_map_content_hash,
    load_world_map_manifest_for_scenario,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_campus_world_map_manifest_loads_with_verified_content_hash():
    world_map = load_world_map_manifest_for_scenario(
        "campus_world",
        project_root=PROJECT_ROOT,
    )

    assert world_map is not None
    assert world_map.map_id == "campus-world-v2"
    assert {location.id for location in world_map.locations} == {
        "cafe",
        "dorm",
        "lecture-hall",
        "library",
        "quad",
    }
    assert len(world_map.route_edges) == 5
    assert world_map.interactables[0].slot_ids == ["slot:cafe:window-chair-1:sit"]


def test_exported_world_map_rejects_unknown_location_entrance():
    raw = _campus_world_map_raw()
    raw["locations"][0]["entrance_node_id"] = "route:missing"

    with pytest.raises(ValidationError, match="unknown entrance node"):
        ExportedWorldMap.model_validate(raw)


def test_exported_world_map_rejects_disconnected_location_entrances():
    raw = _campus_world_map_raw()
    raw["route_edges"] = []

    with pytest.raises(ValidationError, match="location entrances are disconnected"):
        ExportedWorldMap.model_validate(raw)


def test_loader_rejects_tampered_exported_map(tmp_path: Path):
    bundle_root = tmp_path / "scenarios" / "test_world"
    map_root = bundle_root / "map"
    map_root.mkdir(parents=True)
    (bundle_root / "scenario.yml").write_text(
        "\n".join(
            [
                "id: test_world",
                "name: Test World",
                "version: 1",
                "adapter: bundle_world",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "world.yml").write_text(
        "spatial:\n  map_manifest: map/manifest.yml\n",
        encoding="utf-8",
    )
    (map_root / "manifest.yml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "map_id: campus-world-v2",
                "source_scene: res://scenes/maps/test_world.tscn",
                "exported_world_map: world-map.json",
                "meters_per_unit: 1.0",
            ]
        ),
        encoding="utf-8",
    )
    raw = _campus_world_map_raw()
    raw["locations"][0]["name"] = "Tampered after export"
    (map_root / "world-map.json").write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="content hash does not match"):
        load_world_map_manifest_for_scenario("test_world", project_root=tmp_path)


def test_python_content_hash_matches_godot_export():
    raw = _campus_world_map_raw()

    assert calculate_world_map_content_hash(raw) == raw["content_hash"]


def _campus_world_map_raw() -> dict:
    path = PROJECT_ROOT / "scenarios" / "campus_world" / "map" / "world-map.json"
    return json.loads(path.read_text(encoding="utf-8"))
