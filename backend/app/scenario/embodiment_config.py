from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.scenario.bundle_registry import get_scenario_bundle
from app.scenario.spatial_manifest import ExportedWorldMap, load_world_map_manifest_for_scenario

StableId = Annotated[str, Field(min_length=1)]
DurationRange = tuple[Annotated[float, Field(ge=0)], Annotated[float, Field(ge=0)]]


class EmbodimentConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObjectSlotDefinition(EmbodimentConfigModel):
    kind: StableId
    capacity: int = Field(default=1, ge=1)


class AffordanceDefinition(EmbodimentConfigModel):
    action: StableId
    executor: Literal["occupy_slot", "service_queue", "use_object"]
    duration_seconds: DurationRange
    interruptible: bool = True
    slot_kind: StableId | None = None

    @model_validator(mode="after")
    def validate_duration(self) -> AffordanceDefinition:
        if self.duration_seconds[1] < self.duration_seconds[0]:
            raise ValueError("duration_seconds maximum must be >= minimum")
        return self


class ObjectTypeDefinition(EmbodimentConfigModel):
    visual_preset: StableId
    slots: list[ObjectSlotDefinition] = Field(default_factory=list)
    affordances: list[AffordanceDefinition] = Field(default_factory=list)


class ObjectTypesDocument(EmbodimentConfigModel):
    schema_version: Literal[1]
    object_types: dict[StableId, ObjectTypeDefinition]


class ActivityResourceRequirement(EmbodimentConfigModel):
    object_types: list[StableId] = Field(min_length=1)
    slot_kind: StableId


class ActivityStepDefinition(EmbodimentConfigModel):
    id: StableId
    action: StableId
    duration_seconds: DurationRange
    resource: ActivityResourceRequirement | None = None
    release_after: bool = True
    visual_state: StableId | None = None

    @model_validator(mode="after")
    def validate_duration(self) -> ActivityStepDefinition:
        if self.duration_seconds[1] < self.duration_seconds[0]:
            raise ValueError("duration_seconds maximum must be >= minimum")
        return self


class ActivityRequirements(EmbodimentConfigModel):
    location_types: list[StableId] = Field(default_factory=list)


class ActivityDefinition(EmbodimentConfigModel):
    executor: StableId
    interruptible: bool = True
    requirements: ActivityRequirements = Field(default_factory=ActivityRequirements)
    steps: list[ActivityStepDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_steps(self) -> ActivityDefinition:
        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("activity step IDs must be unique")
        return self


class MovementProfile(EmbodimentConfigModel):
    speed_mps: float = Field(gt=0)
    acceleration_mps2: float = Field(gt=0)


class PerceptionDefinition(EmbodimentConfigModel):
    vision_range_meters: float = Field(gt=0)
    conversation_range_meters: float = Field(gt=0)
    hearing_range_meters: float = Field(gt=0)


class EncounterDefinition(EmbodimentConfigModel):
    candidate_distance_meters: float = Field(gt=0)
    candidate_timeout_seconds: float = Field(gt=0)
    cooldown_minutes: int = Field(ge=1)


@dataclass(frozen=True, slots=True)
class SocialSpatialConfig:
    perception: PerceptionDefinition
    encounter: EncounterDefinition


class ActivitiesDocument(EmbodimentConfigModel):
    schema_version: Literal[1]
    movement_profiles: dict[StableId, MovementProfile] = Field(default_factory=dict)
    activities: dict[StableId, ActivityDefinition]


@dataclass(frozen=True, slots=True)
class EmbodiedResource:
    id: str
    object_id: str
    object_type: str
    slot_kind: str
    location_id: str
    zone_id: str
    position: tuple[float, float, float]
    rotation_y_degrees: float
    capacity: int


@dataclass(frozen=True, slots=True)
class EmbodimentCatalog:
    activities: ActivitiesDocument
    object_types: ObjectTypesDocument
    resources: tuple[EmbodiedResource, ...]

    def get_activity(self, activity_type: str) -> ActivityDefinition | None:
        return self.activities.activities.get(activity_type)

    def resources_for(
        self,
        *,
        location_id: str,
        object_types: tuple[str, ...],
        slot_kind: str,
    ) -> tuple[EmbodiedResource, ...]:
        return tuple(
            resource
            for resource in self.resources
            if (
                location_id == resource.location_id
                or location_id.endswith(f"-{resource.location_id}")
            )
            and resource.object_type in object_types
            and resource.slot_kind == slot_kind
        )

    @staticmethod
    def resolve_duration(
        duration_range: DurationRange,
        *,
        world_seed: int,
        agent_id: str,
        activity_type: str,
        step_id: str,
        started_at_iso: str,
    ) -> float:
        minimum, maximum = duration_range
        if minimum == maximum:
            return minimum
        material = f"{world_seed}:{agent_id}:{activity_type}:{step_id}:{started_at_iso}"
        value = int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], "big")
        ratio = value / ((1 << 64) - 1)
        return round(minimum + ((maximum - minimum) * ratio), 4)


def load_embodiment_catalog_for_scenario(
    scenario_id: str | None,
    *,
    project_root: Path | None = None,
) -> EmbodimentCatalog | None:
    bundle = get_scenario_bundle(scenario_id, project_root=project_root)
    if bundle is None:
        return None
    activities_path = bundle.root / "activities.yml"
    object_types_path = bundle.root / "object_types.yml"
    if not activities_path.exists() and not object_types_path.exists():
        return None
    if not activities_path.is_file() or not object_types_path.is_file():
        raise ValueError("activities.yml and object_types.yml must be provided together")

    import yaml

    try:
        activities = ActivitiesDocument.model_validate(
            yaml.safe_load(activities_path.read_text(encoding="utf-8")) or {}
        )
        object_types = ObjectTypesDocument.model_validate(
            yaml.safe_load(object_types_path.read_text(encoding="utf-8")) or {}
        )
    except Exception as exc:
        raise ValueError(f"Invalid embodiment configuration for scenario: {scenario_id}") from exc

    world_map = load_world_map_manifest_for_scenario(scenario_id, project_root=project_root)
    if world_map is None:
        raise ValueError("embodiment configuration requires a spatial world map")
    _validate_configuration(activities, object_types, world_map)
    return EmbodimentCatalog(
        activities=activities,
        object_types=object_types,
        resources=_build_resources(object_types, world_map),
    )


def load_social_spatial_config_for_scenario(
    scenario_id: str | None,
    *,
    project_root: Path | None = None,
) -> SocialSpatialConfig | None:
    bundle = get_scenario_bundle(scenario_id, project_root=project_root)
    if bundle is None:
        return None

    import yaml

    world_path = bundle.root / "world.yml"
    if not world_path.is_file():
        return None
    raw = yaml.safe_load(world_path.read_text(encoding="utf-8")) or {}
    perception_raw = raw.get("perception")
    encounter_raw = raw.get("encounter")
    if perception_raw is None and encounter_raw is None:
        return None
    if not isinstance(perception_raw, dict) or not isinstance(encounter_raw, dict):
        raise ValueError("perception and encounter must be configured together")
    try:
        return SocialSpatialConfig(
            perception=PerceptionDefinition.model_validate(perception_raw),
            encounter=EncounterDefinition.model_validate(encounter_raw),
        )
    except Exception as exc:
        raise ValueError(
            f"Invalid social spatial configuration for scenario: {scenario_id}"
        ) from exc


def _validate_configuration(
    activities: ActivitiesDocument,
    object_types: ObjectTypesDocument,
    world_map: ExportedWorldMap,
) -> None:
    known_location_types = {location.type for location in world_map.locations}
    mapped_object_types = {item.type for item in world_map.interactables}
    configured_object_types = set(object_types.object_types)
    unknown_mapped_types = mapped_object_types - configured_object_types
    if unknown_mapped_types:
        raise ValueError(
            f"world map uses undefined object types: {', '.join(sorted(unknown_mapped_types))}"
        )

    slot_by_id = {slot.id: slot for slot in world_map.interaction_slots}
    for interactable in world_map.interactables:
        definition = object_types.object_types[interactable.type]
        configured_slots = {slot.kind: slot.capacity for slot in definition.slots}
        for slot_id in interactable.slot_ids:
            slot = slot_by_id[slot_id]
            if slot.kind not in configured_slots:
                raise ValueError(
                    f"object {interactable.id} exposes undefined slot kind: {slot.kind}"
                )
            if slot.capacity > configured_slots[slot.kind]:
                raise ValueError(f"slot {slot.id} exceeds its object type capacity")

    for activity_id, activity in activities.activities.items():
        unknown_locations = set(activity.requirements.location_types) - known_location_types
        if unknown_locations:
            raise ValueError(
                f"activity {activity_id} references unknown location types: "
                f"{', '.join(sorted(unknown_locations))}"
            )
        for step in activity.steps:
            if step.resource is None:
                continue
            unknown_types = set(step.resource.object_types) - configured_object_types
            if unknown_types:
                raise ValueError(
                    f"activity {activity_id} references unknown object types: "
                    f"{', '.join(sorted(unknown_types))}"
                )
            matching_slot = any(
                slot.kind == step.resource.slot_kind
                for object_type in step.resource.object_types
                for slot in object_types.object_types[object_type].slots
            )
            if not matching_slot:
                raise ValueError(
                    f"activity {activity_id} has no {step.resource.slot_kind} resource slot"
                )
            matching_affordance = any(
                affordance.action == step.action and affordance.slot_kind == step.resource.slot_kind
                for object_type in step.resource.object_types
                for affordance in object_types.object_types[object_type].affordances
            )
            if not matching_affordance:
                raise ValueError(
                    f"activity {activity_id} step {step.id} has no matching affordance"
                )


def _build_resources(
    object_types: ObjectTypesDocument,
    world_map: ExportedWorldMap,
) -> tuple[EmbodiedResource, ...]:
    objects = {item.id: item for item in world_map.interactables}
    resources = []
    for slot in world_map.interaction_slots:
        interactable = objects[slot.object_id]
        definition = object_types.object_types[interactable.type]
        configured_capacity = next(
            item.capacity for item in definition.slots if item.kind == slot.kind
        )
        resources.append(
            EmbodiedResource(
                id=slot.id,
                object_id=interactable.id,
                object_type=interactable.type,
                slot_kind=slot.kind,
                location_id=interactable.location_id,
                zone_id=interactable.zone_id,
                position=slot.position,
                rotation_y_degrees=slot.rotation_y_degrees,
                capacity=min(slot.capacity, configured_capacity),
            )
        )
    return tuple(sorted(resources, key=lambda item: item.id))
