class_name ScenarioSceneRegistry
extends RefCounted

const DEFAULT_SCENARIO_ID := "campus_world"
const DEFINITIONS := {
	"campus_world": {
		"map_id": "campus-world-v2",
		"scene_path": "res://scenes/maps/campus_world.tscn",
	},
	"narrative_world": {
		"map_id": "narrative-world-v1",
		"scene_path": "res://scenes/maps/narrative_world.tscn",
	},
}


static func resolve(scenario_id: String) -> Dictionary:
	var normalized := scenario_id.strip_edges()
	if not DEFINITIONS.has(normalized):
		return {}
	return (DEFINITIONS[normalized] as Dictionary).duplicate(true)


static func instantiate_map(scenario_id: String) -> Node3D:
	var definition := resolve(scenario_id)
	if definition.is_empty():
		return null
	var packed_scene := load(str(definition["scene_path"])) as PackedScene
	if packed_scene == null:
		return null
	return packed_scene.instantiate() as Node3D
