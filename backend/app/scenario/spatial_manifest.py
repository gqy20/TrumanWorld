from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.scenario.bundle_registry import get_scenario_bundle, load_world_config_for_scenario

StableId = Annotated[str, Field(min_length=1)]
Vec3 = tuple[float, float, float]


class SpatialManifestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorldMapAssetManifest(SpatialManifestModel):
    schema_version: Literal[1]
    map_id: StableId
    source_scene: StableId
    exported_world_map: StableId
    meters_per_unit: float = Field(gt=0)


class WorldMapDistrict(SpatialManifestModel):
    id: StableId
    name: str
    position: Vec3
    size_meters: Vec3


class WorldMapLocation(SpatialManifestModel):
    id: StableId
    name: str
    type: StableId
    position: Vec3
    capacity: int = Field(ge=1)
    public_access: bool
    entrance_node_id: StableId


class WorldMapZone(SpatialManifestModel):
    id: StableId
    location_id: StableId
    type: StableId
    position: Vec3
    size_meters: Vec3
    capacity: int = Field(ge=1)


class WorldMapPortal(SpatialManifestModel):
    id: StableId
    from_zone_id: StableId
    to_zone_id: StableId
    position: Vec3
    is_open: bool


class WorldMapRouteNode(SpatialManifestModel):
    id: StableId
    kind: StableId
    position: Vec3


class WorldMapRouteEdge(SpatialManifestModel):
    id: StableId
    from_node_id: StableId
    to_node_id: StableId
    distance_meters: float = Field(gt=0)
    bidirectional: bool


class WorldMapInteractable(SpatialManifestModel):
    id: StableId
    type: StableId
    location_id: StableId
    zone_id: StableId
    position: Vec3
    rotation_y_degrees: float
    slot_ids: list[StableId] = Field(default_factory=list)


class WorldMapInteractionSlot(SpatialManifestModel):
    id: StableId
    object_id: StableId
    kind: StableId
    position: Vec3
    rotation_y_degrees: float
    capacity: int = Field(ge=1)


class WorldMapSpawnAnchor(SpatialManifestModel):
    id: StableId
    zone_id: StableId
    kind: StableId
    position: Vec3
    rotation_y_degrees: float


class WorldMapCameraAnchor(SpatialManifestModel):
    id: StableId
    target_id: StableId
    position: Vec3
    look_at_position: Vec3


class ExportedWorldMap(SpatialManifestModel):
    schema_version: Literal[1]
    map_id: StableId
    meters_per_unit: float = Field(gt=0)
    content_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    districts: list[WorldMapDistrict] = Field(default_factory=list)
    locations: list[WorldMapLocation] = Field(default_factory=list)
    zones: list[WorldMapZone] = Field(default_factory=list)
    portals: list[WorldMapPortal] = Field(default_factory=list)
    route_nodes: list[WorldMapRouteNode] = Field(default_factory=list)
    route_edges: list[WorldMapRouteEdge] = Field(default_factory=list)
    interactables: list[WorldMapInteractable] = Field(default_factory=list)
    interaction_slots: list[WorldMapInteractionSlot] = Field(default_factory=list)
    spawn_anchors: list[WorldMapSpawnAnchor] = Field(default_factory=list)
    camera_anchors: list[WorldMapCameraAnchor] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> ExportedWorldMap:
        collections: tuple[list[Any], ...] = (
            self.districts,
            self.locations,
            self.zones,
            self.portals,
            self.route_nodes,
            self.route_edges,
            self.interactables,
            self.interaction_slots,
            self.spawn_anchors,
            self.camera_anchors,
        )
        all_ids = [item.id for collection in collections for item in collection]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("world map stable IDs must be globally unique")

        location_ids = {item.id for item in self.locations}
        zone_by_id = {item.id: item for item in self.zones}
        route_node_ids = {item.id for item in self.route_nodes}
        object_by_id = {item.id: item for item in self.interactables}
        slot_ids = {item.id for item in self.interaction_slots}

        for location in self.locations:
            if location.entrance_node_id not in route_node_ids:
                raise ValueError(f"location {location.id} references an unknown entrance node")
        for zone in self.zones:
            if zone.location_id not in location_ids:
                raise ValueError(f"zone {zone.id} references an unknown location")
        for portal in self.portals:
            if portal.from_zone_id not in zone_by_id or portal.to_zone_id not in zone_by_id:
                raise ValueError(f"portal {portal.id} references an unknown zone")
        for edge in self.route_edges:
            if edge.from_node_id not in route_node_ids or edge.to_node_id not in route_node_ids:
                raise ValueError(f"route edge {edge.id} references an unknown node")
            if edge.from_node_id == edge.to_node_id:
                raise ValueError(f"route edge {edge.id} cannot connect a node to itself")
        for interactable in self.interactables:
            zone = zone_by_id.get(interactable.zone_id)
            if interactable.location_id not in location_ids or zone is None:
                raise ValueError(f"interactable {interactable.id} has an invalid location or zone")
            if zone.location_id != interactable.location_id:
                raise ValueError(f"interactable {interactable.id} crosses location boundaries")
            if len(interactable.slot_ids) != len(set(interactable.slot_ids)):
                raise ValueError(f"interactable {interactable.id} repeats a slot ID")
            if any(slot_id not in slot_ids for slot_id in interactable.slot_ids):
                raise ValueError(f"interactable {interactable.id} references an unknown slot")
        for slot in self.interaction_slots:
            interactable = object_by_id.get(slot.object_id)
            if interactable is None or slot.id not in interactable.slot_ids:
                raise ValueError(f"interaction slot {slot.id} is not owned by its object")
        for anchor in self.spawn_anchors:
            if anchor.zone_id not in zone_by_id:
                raise ValueError(f"spawn anchor {anchor.id} references an unknown zone")
        for anchor in self.camera_anchors:
            if anchor.target_id not in all_ids:
                raise ValueError(f"camera anchor {anchor.id} references an unknown target")

        self._validate_location_routes()
        return self

    def _validate_location_routes(self) -> None:
        entrances = {location.entrance_node_id for location in self.locations}
        if len(entrances) <= 1:
            return
        neighbors: dict[str, set[str]] = {node.id: set() for node in self.route_nodes}
        for edge in self.route_edges:
            neighbors[edge.from_node_id].add(edge.to_node_id)
            if edge.bidirectional:
                neighbors[edge.to_node_id].add(edge.from_node_id)
        start = min(entrances)
        visited = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in sorted(neighbors[current]):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        missing = sorted(entrances - visited)
        if missing:
            raise ValueError(f"location entrances are disconnected: {', '.join(missing)}")


def load_world_map_manifest_for_scenario(
    scenario_id: str | None,
    *,
    project_root: Path | None = None,
) -> ExportedWorldMap | None:
    bundle = get_scenario_bundle(scenario_id, project_root=project_root)
    if bundle is None:
        return None
    world_config = load_world_config_for_scenario(scenario_id, project_root=project_root)
    spatial_config = world_config.get("spatial")
    if not isinstance(spatial_config, dict):
        return None
    manifest_reference = spatial_config.get("map_manifest")
    if not isinstance(manifest_reference, str) or not manifest_reference:
        return None

    asset_path = _resolve_bundle_asset(bundle.root, manifest_reference)
    try:
        asset_raw = yaml.safe_load(asset_path.read_text(encoding="utf-8")) or {}
        asset_manifest = WorldMapAssetManifest.model_validate(asset_raw)
    except Exception as exc:
        raise ValueError(f"Invalid world map asset manifest: {asset_path}") from exc

    exported_path = _resolve_bundle_asset(asset_path.parent, asset_manifest.exported_world_map)
    try:
        raw = json.loads(exported_path.read_text(encoding="utf-8"))
        world_map = ExportedWorldMap.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"Invalid exported world map: {exported_path}") from exc

    if world_map.map_id != asset_manifest.map_id:
        raise ValueError("World map ID does not match its asset manifest")
    if world_map.meters_per_unit != asset_manifest.meters_per_unit:
        raise ValueError("World map scale does not match its asset manifest")
    expected_hash = calculate_world_map_content_hash(raw)
    if world_map.content_hash != expected_hash:
        raise ValueError("World map content hash does not match its exported content")
    return world_map


def calculate_world_map_content_hash(raw: dict[str, Any]) -> str:
    content = dict(raw)
    content.pop("content_hash", None)
    canonical = json.dumps(
        content,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def _resolve_bundle_asset(root: Path, reference: str) -> Path:
    resolved_root = root.resolve()
    candidate = (resolved_root / reference).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"World map asset escapes scenario bundle: {reference}") from exc
    if not candidate.is_file():
        raise ValueError(f"World map asset does not exist: {candidate}")
    return candidate
