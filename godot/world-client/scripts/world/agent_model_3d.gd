class_name AgentModel3D
extends Node3D

var _animation_player: AnimationPlayer
var _skeleton: Skeleton3D
var _coffee_props: Array[MeshInstance3D] = []
var _head_bone_index := -1
var _cycle_distance_m := {"walk": 1.04, "jog": 1.32}
var _state_offsets_m: Dictionary = {}
var _active_animation := ""
var _active_state := ""
var _state_started_at := 0.0
var _target_offset := Vector3.ZERO
var _motion_offset := Vector3.ZERO


static func instantiate_asset(visual_asset_id: String) -> AgentModel3D:
	var asset_path := _asset_path(visual_asset_id)
	if asset_path.is_empty() or not ResourceLoader.exists(asset_path):
		return null
	var scene := load(asset_path) as PackedScene
	if scene == null:
		return null
	var controller := AgentModel3D.new()
	controller.name = "CharacterModel"
	controller._attach_scene(scene.instantiate())
	controller._load_manifest(asset_path.get_base_dir() + "/manifest.json")
	return controller if controller.is_ready() else null


func is_ready() -> bool:
	return is_instance_valid(_animation_player)


func animation_names() -> PackedStringArray:
	return _animation_player.get_animation_list() if is_ready() else PackedStringArray()


func update_pose(
	state: String,
	elapsed_seconds: float,
	distance_m: float,
	gait: float,
	look_yaw: float = 0.0,
) -> void:
	if not is_ready():
		return
	var requested := "idle" if state in ["walk", "jog"] and gait < 0.05 else state
	if requested != _active_state:
		_active_state = requested
		_state_started_at = elapsed_seconds
	var animation_name := _resolve_animation(requested)
	if animation_name.is_empty():
		animation_name = _resolve_animation("idle")
	if animation_name.is_empty():
		return
	_activate_animation(animation_name)
	_seek_animation(animation_name, requested, elapsed_seconds, distance_m)
	_apply_head_look(look_yaw)
	_target_offset = _state_offset(requested)
	_motion_offset = _motion_bob(requested, elapsed_seconds, distance_m, gait)
	for coffee_prop in _coffee_props:
		coffee_prop.visible = requested == "drink"


func _process(delta: float) -> void:
	position = position.lerp(_target_offset + _motion_offset, minf(1.0, delta * 10.0))


func _attach_scene(instance: Node) -> void:
	instance.name = "RiggedCharacter"
	add_child(instance)
	var players := instance.find_children("*", "AnimationPlayer", true, false)
	if not players.is_empty():
		_animation_player = players[0] as AnimationPlayer
	var skeletons := instance.find_children("*", "Skeleton3D", true, false)
	if not skeletons.is_empty():
		_skeleton = skeletons[0] as Skeleton3D
		_head_bone_index = _skeleton.find_bone("head")
	var cups := instance.find_children("CoffeeCup*", "MeshInstance3D", true, false)
	for cup in cups:
		var coffee_prop := cup as MeshInstance3D
		coffee_prop.visible = false
		_coffee_props.append(coffee_prop)


func _activate_animation(animation_name: String) -> void:
	if animation_name == _active_animation:
		return
	_animation_player.play(animation_name, 0.16)
	_animation_player.pause()
	_active_animation = animation_name


func _seek_animation(
	animation_name: String,
	state: String,
	elapsed_seconds: float,
	distance_m: float,
) -> void:
	var animation := _animation_player.get_animation(animation_name)
	if animation == null or animation.length <= 0.0:
		return
	var normalized := _normalized_time(state, elapsed_seconds, distance_m, animation.length)
	_animation_player.seek(normalized * animation.length, true)


func _normalized_time(
	state: String,
	elapsed_seconds: float,
	distance_m: float,
	duration_seconds: float,
) -> float:
	if state in ["walk", "jog"]:
		var cycle := maxf(float(_cycle_distance_m.get(state, 1.0)), 0.001)
		return fposmod(maxf(distance_m, 0.0), cycle) / cycle
	if state == "sit":
		return 1.0
	var state_elapsed := maxf(elapsed_seconds - _state_started_at, 0.0)
	if state in ["turn_left", "turn_right"]:
		return clampf(state_elapsed / maxf(duration_seconds, 0.001), 0.0, 1.0)
	return fposmod(state_elapsed, maxf(duration_seconds, 0.001)) / maxf(
		duration_seconds, 0.001
	)


func _resolve_animation(state: String) -> String:
	for animation_name: String in animation_names():
		if (
			animation_name == state
			or animation_name.ends_with("|%s" % state)
			or animation_name.ends_with("/%s" % state)
		):
			return animation_name
	return ""


func _load_manifest(path: String) -> void:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		return
	var configured: Variant = parsed.get("cycle_distance_m", {})
	if configured is Dictionary:
		_cycle_distance_m.merge(configured, true)
	var offsets: Variant = parsed.get("state_offsets_m", {})
	if offsets is Dictionary:
		_state_offsets_m = offsets


func _state_offset(state: String) -> Vector3:
	var raw: Variant = _state_offsets_m.get(state, [])
	if raw is Array and raw.size() >= 3:
		return Vector3(float(raw[0]), float(raw[1]), float(raw[2]))
	return Vector3.ZERO


func _motion_bob(state: String, elapsed_seconds: float, distance_m: float, gait: float) -> Vector3:
	if state in ["walk", "jog"]:
		var cycle := maxf(float(_cycle_distance_m.get(state, 1.0)), 0.001)
		var amplitude := 0.05 if state == "jog" else 0.025
		return Vector3.UP * absf(sin((distance_m / cycle) * TAU)) * amplitude * gait
	if state == "celebrate":
		var state_elapsed := maxf(elapsed_seconds - _state_started_at, 0.0)
		return Vector3.UP * absf(sin(state_elapsed * 8.0)) * 0.08
	return Vector3.ZERO


func _apply_head_look(yaw: float) -> void:
	if not is_instance_valid(_skeleton) or _head_bone_index < 0:
		return
	var animation_rotation := _skeleton.get_bone_pose_rotation(_head_bone_index)
	_skeleton.set_bone_pose_rotation(
		_head_bone_index,
		animation_rotation * Quaternion(Vector3.UP, clampf(yaw, -0.55, 0.55)),
	)


static func _asset_path(visual_asset_id: String) -> String:
	var parts := visual_asset_id.split("/", false)
	if parts.size() != 2 or not _is_safe_part(parts[0]) or not _is_safe_part(parts[1]):
		return ""
	return "res://assets/scenarios/%s/characters/%s/model/character.glb" % [
		parts[0], parts[1],
	]


static func _is_safe_part(value: String) -> bool:
	if value.is_empty() or value in [".", ".."]:
		return false
	for character: String in value:
		if character.to_lower() not in "abcdefghijklmnopqrstuvwxyz0123456789_-":
			return false
	return true
