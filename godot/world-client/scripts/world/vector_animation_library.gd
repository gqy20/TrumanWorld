class_name VectorAnimationLibrary
extends RefCounted


static func load_asset(visual_asset_id: String, pose_ids: Array) -> Dictionary:
	var base_path := _asset_base_path(visual_asset_id)
	if base_path.is_empty():
		return {}
	var poses := _load_poses(base_path, pose_ids)
	if not poses.has("idle"):
		return {}
	return {
		"poses": poses,
		"animations": _load_animations(base_path),
	}


static func frame_index(definition: Dictionary, elapsed_seconds: float, distance_m: float) -> int:
	var frames: Variant = definition.get("frames", [])
	if not frames is Array or frames.is_empty():
		return 0
	if definition.get("driver") == "time":
		var fps := maxf(float(definition.get("fps", 1.0)), 0.001)
		return posmod(floori(maxf(elapsed_seconds, 0.0) * fps), frames.size())
	var phase := _distance_phase(definition, distance_m)
	return mini(floori(phase * frames.size()), frames.size() - 1)


static func texture_for(
	poses: Dictionary,
	animations: Dictionary,
	state: String,
	elapsed_seconds: float,
	distance_m: float,
) -> Texture2D:
	if animations.has(state):
		var definition := animations[state] as Dictionary
		var frames := definition.get("frames", []) as Array
		if not frames.is_empty():
			return frames[frame_index(definition, elapsed_seconds, distance_m)] as Texture2D
	return poses.get(state, poses.get("idle")) as Texture2D


static func cycle_distance_m(animations: Dictionary, state: String, fallback: float) -> float:
	var definition: Variant = animations.get(state)
	if not definition is Dictionary or definition.get("driver") != "distance":
		return fallback
	return maxf(float(definition.get("cycle_distance_m", fallback)), 0.001)


static func _distance_phase(definition: Dictionary, distance_m: float) -> float:
	var cycle_distance := maxf(float(definition.get("cycle_distance_m", 1.0)), 0.001)
	return fposmod(maxf(distance_m, 0.0), cycle_distance) / cycle_distance


static func _asset_base_path(visual_asset_id: String) -> String:
	var parts := visual_asset_id.split("/", false)
	if parts.size() != 2 or not _is_safe_part(parts[0]) or not _is_safe_part(parts[1]):
		return ""
	return "res://assets/scenarios/%s/characters/%s/vector" % [parts[0], parts[1]]


static func _is_safe_part(value: String) -> bool:
	if value.is_empty() or value in [".", ".."]:
		return false
	for character: String in value:
		if character.to_lower() not in "abcdefghijklmnopqrstuvwxyz0123456789_-":
			return false
	return true


static func _load_poses(base_path: String, pose_ids: Array) -> Dictionary:
	var poses := {}
	for raw_pose_id: Variant in pose_ids:
		var pose_id := str(raw_pose_id)
		var texture := _load_texture("%s/%s.svg" % [base_path, pose_id])
		if texture != null:
			poses[pose_id] = texture
	return poses


static func _load_animations(base_path: String) -> Dictionary:
	var manifest := _read_manifest("%s/manifest.json" % base_path)
	var raw_animations: Variant = manifest.get("animations", {})
	if not raw_animations is Dictionary:
		return {}
	var animations := {}
	for raw_animation_id: Variant in raw_animations:
		var animation_id := str(raw_animation_id)
		var raw_definition: Variant = raw_animations[raw_animation_id]
		if not raw_definition is Dictionary:
			continue
		var definition := _load_animation(
			base_path,
			raw_definition as Dictionary,
		)
		if not definition.is_empty():
			animations[animation_id] = definition
	return animations


static func _load_animation(base_path: String, raw: Dictionary) -> Dictionary:
	var frame_paths: Variant = raw.get("frames", [])
	if not frame_paths is Array or frame_paths.size() < 2:
		return {}
	var frames: Array[Texture2D] = []
	for raw_path: Variant in frame_paths:
		var relative_path := str(raw_path)
		if relative_path.is_empty() or ".." in relative_path or relative_path.begins_with("/"):
			return {}
		var texture := _load_texture("%s/%s" % [base_path, relative_path])
		if texture == null:
			return {}
		frames.append(texture)
	var definition := raw.duplicate()
	definition["frames"] = frames
	return definition if _has_valid_timing(definition) else {}


static func _has_valid_timing(definition: Dictionary) -> bool:
	if definition.get("driver") == "time":
		return float(definition.get("fps", 0.0)) > 0.0
	if definition.get("driver") == "distance":
		return float(definition.get("cycle_distance_m", 0.0)) > 0.0
	return false


static func _read_manifest(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed as Dictionary if parsed is Dictionary else {}


static func _load_texture(path: String) -> Texture2D:
	if not ResourceLoader.exists(path):
		return null
	return load(path) as Texture2D
