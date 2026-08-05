class_name AgentAvatar
extends StaticBody3D

signal selected(agent_id: String)

const PALETTE := [
	Color("5aa7a7"),
	Color("e07a5f"),
	Color("81b29a"),
	Color("f2cc8f"),
	Color("8d86c9"),
]
const STATE_LABELS := {
	"idle": "Observing",
	"walk": "Walking",
	"jog": "Jogging",
	"queue": "Waiting in line",
	"sit": "Taking a seat",
	"drink": "Having coffee",
	"talk": "In conversation",
	"use_object": "Using object",
	"wave": "Waving",
	"think": "Thinking",
	"read": "Reading",
	"phone": "Checking phone",
	"carry": "Carrying",
	"celebrate": "Celebrating",
	"surprised": "Surprised",
	"sleep": "Sleeping",
}
const VECTOR_POSE_IDS := [
	"idle", "walk", "jog", "queue", "sit", "drink", "talk", "use_object",
	"wave", "think", "read", "phone", "carry", "celebrate", "surprised", "sleep",
]

var agent_id := ""
var visual_asset_id := ""
var display_name := ""
var _body_root: Node3D
var _torso: MeshInstance3D
var _head: MeshInstance3D
var _left_arm: MeshInstance3D
var _right_arm: MeshInstance3D
var _left_leg: MeshInstance3D
var _right_leg: MeshInstance3D
var _cup: MeshInstance3D
var _name_label: Label3D
var _action_label: Label3D
var _speech_label: Label3D
var _selection_ring: MeshInstance3D
var _vector_sprite: Sprite3D
var _vector_previous_sprite: Sprite3D
var _vector_textures: Dictionary = {}
var _vector_animations: Dictionary = {}
var _vector_pose_id := ""
var _vector_transition: Tween
var _model_character: AgentModel3D
var _target_position := Vector3.ZERO
var _has_position := false
var _movement: Dictionary = {}
var _route_positions: Dictionary = {}
var _route_path: Dictionary = {}
var _route_movement_id := ""
var _client_clock: ClientClock
var _visual_state := "idle"
var _presentation_paused := false
var _motion_time := 0.0
var _activity_progress := 0.0
var _conversation_partner_position := Vector3.ZERO
var _has_conversation_partner := false
var _is_speaking := false
var _stride_phase := 0.0
var _travel_distance := 0.0
var _gait_strength := 0.0
var _motion_tangent := Vector3(0.0, 0.0, 1.0)
var _model_turn_state := ""
var _idle_offset := Vector3.ZERO
var _can_use_idle_offset := false
var _avoidance_offset := Vector3.ZERO
var _avoidance_target := Vector3.ZERO
var _presentation_base_position := Vector3.ZERO
var _lane_offset := 0.09
var _longitudinal_offset := 0.0
var _conversation_offset := Vector3.ZERO
var _conversation_target := Vector3.ZERO
var _selection_press_position := Vector2.ZERO
var _selection_press_active := false

const SELECTION_DRAG_THRESHOLD_PIXELS := 6.0


func _ready() -> void:
	input_ray_pickable = true
	_build_visuals()
	input_event.connect(_on_input_event)


func configure_navigation(route_positions: Dictionary, client_clock: ClientClock) -> void:
	_route_positions = route_positions
	_client_clock = client_clock


func configure(snapshot: Dictionary) -> void:
	agent_id = str(snapshot.get("id", "unknown-agent"))
	display_name = str(snapshot.get("name", agent_id))
	name = "Agent_%s" % agent_id.validate_node_name()
	_movement = snapshot.get("movement", {}) if snapshot.get("movement") is Dictionary else {}
	_update_route_path()
	_can_use_idle_offset = _resolve_can_use_idle_offset(snapshot)
	if is_instance_valid(_name_label):
		_name_label.text = display_name
	if is_instance_valid(_torso):
		var material := _torso.material_override as StandardMaterial3D
		material.albedo_color = PALETTE[abs(agent_id.hash()) % PALETTE.size()]

	var raw_position: Variant = snapshot.get("position_meters", [0.0, 0.0, 0.0])
	if raw_position is Array and raw_position.size() >= 3:
		_target_position = Vector3(
			float(raw_position[0]),
			float(raw_position[1]),
			float(raw_position[2]),
		)
		_presentation_base_position = _projected_position()
		if not _has_position:
			position = _presentation_base_position
			_has_position = true
	_visual_state = _resolve_visual_state(snapshot)
	_activity_progress = _resolve_activity_progress(snapshot)
	_update_action_label()
	if not snapshot.get("movement") is Dictionary and not _has_conversation_partner:
		rotation.y = float(snapshot.get("facing_radians", rotation.y))


func _process(delta: float) -> void:
	if not _has_position:
		return
	if not _presentation_paused:
		_motion_time += delta
		var motion_sample := _motion_sample()
		var projected_position := motion_sample.get("position", _target_position) as Vector3
		_presentation_base_position = projected_position
		_update_locomotion_state(motion_sample)
		_avoidance_offset = _avoidance_offset.lerp(_avoidance_target, minf(1.0, delta * 10.0))
		_conversation_offset = _conversation_offset.lerp(
			_conversation_target, minf(1.0, delta * 6.0)
		)
		var desired_position := projected_position + _avoidance_offset + _conversation_offset
		var offset := desired_position - position
		if offset.length_squared() > 0.0001:
			position = position.lerp(desired_position, minf(1.0, delta * 10.0))
		_update_facing(delta)
	_apply_pose()


func _update_facing(delta: float) -> void:
	var target_yaw: Variant = _facing_target_yaw()
	if target_yaw == null:
		_model_turn_state = ""
		return
	var yaw_error := angle_difference(rotation.y, float(target_yaw))
	var can_play_turn := _visual_state in ["idle", "talk", "queue", "think"]
	if can_play_turn and absf(yaw_error) > 0.14:
		_model_turn_state = "turn_left" if yaw_error > 0.0 else "turn_right"
	else:
		_model_turn_state = ""
	var turn_speed := 6.0 if _has_conversation_partner else 7.0
	rotation.y = lerp_angle(rotation.y, float(target_yaw), minf(1.0, delta * turn_speed))


func _facing_target_yaw() -> Variant:
	if _has_conversation_partner:
		var partner_offset := _conversation_partner_position - global_position
		if partner_offset.length_squared() > 0.01:
			return atan2(partner_offset.x, partner_offset.z)
	if _visual_state in ["walk", "jog"]:
		return atan2(_motion_tangent.x, _motion_tangent.z)
	return null


func _conversation_look_yaw() -> float:
	if not _has_conversation_partner:
		return 0.0
	var partner_offset := _conversation_partner_position - global_position
	if partner_offset.length_squared() <= 0.01:
		return 0.0
	return angle_difference(rotation.y, atan2(partner_offset.x, partner_offset.z))


func _projected_position() -> Vector3:
	return _motion_sample().get("position", _target_position) as Vector3


func _motion_sample() -> Dictionary:
	if _movement.is_empty() or _client_clock == null or _route_path.is_empty():
		var presentation_offset := _idle_offset if _can_use_idle_offset else Vector3.ZERO
		return {
			"position": _target_position + presentation_offset,
			"tangent": _motion_tangent,
			"distance": 0.0,
			"total_length": 0.0,
		}
	var progress := RouteProjection.movement_progress(
		_movement, _client_clock.world_time_seconds()
	)
	return RouteProjection.offset_sample(
		RouteProjection.sample_path(_route_path, progress),
		_lane_offset,
		_longitudinal_offset,
	)


func _update_route_path() -> void:
	var movement_id := str(_movement.get("id", ""))
	if movement_id == _route_movement_id:
		return
	_route_movement_id = movement_id
	_route_path = (
		RouteProjection.build_path(_movement, _route_positions)
		if not movement_id.is_empty()
		else {}
	)


func _update_locomotion_state(sample: Dictionary) -> void:
	if _movement.is_empty():
		_gait_strength = 0.0
		_travel_distance = 0.0
		return
	var distance := float(sample.get("distance", 0.0))
	var total_length := float(sample.get("total_length", 0.0))
	var cycle_distance := VectorAnimationLibrary.cycle_distance_m(
		_vector_animations, _visual_state, 0.52
	)
	_stride_phase = (distance / cycle_distance) * TAU
	_travel_distance = distance
	_gait_strength = RouteProjection.endpoint_blend(distance, total_length)
	_motion_tangent = _look_ahead_tangent(sample)


func _look_ahead_tangent(sample: Dictionary) -> Vector3:
	var distance := float(sample.get("distance", 0.0))
	var total_length := float(sample.get("total_length", 0.0))
	var speed := float(_movement.get("speed_mps", _movement.get("speed", 1.5)))
	var look_ahead_distance := clampf(0.14 + speed * 0.16, 0.14, 0.4)
	var look_ahead := RouteProjection.sample_path_distance(
		_route_path, minf(total_length, distance + look_ahead_distance)
	)
	var current_position := sample.get("position", position) as Vector3
	var look_position := look_ahead.get("position", current_position) as Vector3
	if current_position.distance_squared_to(look_position) > 0.000001:
		return current_position.direction_to(look_position)
	return sample.get("tangent", _motion_tangent) as Vector3


func can_use_idle_offset() -> bool:
	return _can_use_idle_offset


func presentation_base_position() -> Vector3:
	return _target_position


func set_idle_offset(value: Vector3) -> void:
	_idle_offset = value


func avoidance_base_position() -> Vector3:
	return _presentation_base_position if _has_position else _target_position


func can_use_avoidance() -> bool:
	return not _movement.is_empty() or _can_use_idle_offset


func set_avoidance_target(value: Vector3) -> void:
	_avoidance_target = value


func movement_formation_key() -> String:
	if _movement.is_empty() or _movement.get("state") != "in_transit":
		return ""
	var route_ids: Variant = _movement.get("route_node_ids", [])
	if not route_ids is Array:
		return ""
	return "%s>%s:%s" % [
		str(_movement.get("from_location_id", "")),
		str(_movement.get("to_location_id", "")),
		",".join(route_ids),
	]


func set_movement_formation(lane_offset: float, longitudinal_offset: float) -> void:
	_lane_offset = lane_offset
	_longitudinal_offset = longitudinal_offset


func can_reposition_for_conversation() -> bool:
	return _can_use_idle_offset or _movement.get("state") == "paused"


func set_conversation_target(value: Vector3) -> void:
	_conversation_target = value


func _resolve_can_use_idle_offset(snapshot: Dictionary) -> bool:
	if not _movement.is_empty():
		return false
	var activity: Variant = snapshot.get("activity")
	if not activity is Dictionary:
		return true
	var activity_data := activity as Dictionary
	var claimed_resources: Variant = activity_data.get("claimed_resource_ids", [])
	return (
		(not claimed_resources is Array or claimed_resources.is_empty())
		and activity_data.get("queue_position") == null
		and activity_data.get("paused_position_meters") == null
	)


func set_presentation_paused(value: bool) -> void:
	_presentation_paused = value


func visual_state() -> String:
	return _visual_state


func focus_position() -> Vector3:
	return global_position + Vector3(0.0, 1.0, 0.0)


func set_conversation(
	partner_name: String,
	partner_position: Vector3,
	is_speaking: bool,
) -> void:
	_has_conversation_partner = true
	_conversation_partner_position = partner_position
	_is_speaking = is_speaking
	_visual_state = "talk"
	if is_instance_valid(_speech_label):
		_speech_label.text = "Talking to %s" % partner_name
		_speech_label.visible = is_speaking
	if is_instance_valid(_action_label):
		_action_label.visible = false
	_update_action_label()


func update_conversation_partner_position(partner_position: Vector3) -> void:
	_conversation_partner_position = partner_position


func clear_conversation() -> void:
	_has_conversation_partner = false
	_is_speaking = false
	_conversation_target = Vector3.ZERO
	if is_instance_valid(_speech_label):
		_speech_label.visible = false
	if is_instance_valid(_action_label):
		_action_label.visible = true


func set_highlighted(is_highlighted: bool) -> void:
	if is_instance_valid(_selection_ring):
		_selection_ring.visible = is_highlighted
	if not is_instance_valid(_torso):
		return
	var material := _torso.material_override as StandardMaterial3D
	material.emission_enabled = is_highlighted
	material.emission = material.albedo_color.lightened(0.25)
	material.emission_energy_multiplier = 0.65 if is_highlighted else 0.0


func _build_visuals() -> void:
	_body_root = Node3D.new()
	_body_root.name = "BodyRig"
	add_child(_body_root)

	_torso = _add_capsule(_body_root, Vector3(0.0, 1.04, 0.0), 0.31, 0.86, Color.WHITE)
	_head = _add_sphere(_body_root, Vector3(0.0, 1.82, 0.0), 0.27, Color("f0c7a5"))
	_left_arm = _add_capsule(
		_body_root, Vector3(-0.42, 1.08, 0.0), 0.105, 0.72, Color("dce3df")
	)
	_right_arm = _add_capsule(
		_body_root, Vector3(0.42, 1.08, 0.0), 0.105, 0.72, Color("dce3df")
	)
	_left_leg = _add_capsule(
		_body_root, Vector3(-0.17, 0.42, 0.0), 0.115, 0.72, Color("34424b")
	)
	_right_leg = _add_capsule(
		_body_root, Vector3(0.17, 0.42, 0.0), 0.115, 0.72, Color("34424b")
	)

	_cup = _add_cylinder(
		_body_root, Vector3(0.48, 1.04, -0.18), 0.085, 0.22, Color("f4eee0")
	)
	_cup.visible = false
	_build_vector_sprite()
	_build_model_character()

	var collision := CollisionShape3D.new()
	var collision_shape := CapsuleShape3D.new()
	collision_shape.radius = 0.42
	collision_shape.height = 1.9
	collision.shape = collision_shape
	collision.position.y = 0.95
	add_child(collision)

	var shadow := MeshInstance3D.new()
	var shadow_mesh := CylinderMesh.new()
	shadow_mesh.top_radius = 0.34
	shadow_mesh.bottom_radius = 0.38
	shadow_mesh.height = 0.018
	shadow_mesh.radial_segments = 24
	shadow.mesh = shadow_mesh
	shadow.position.y = 0.015
	shadow.material_override = _material(Color(0.02, 0.03, 0.04, 0.28), true)
	add_child(shadow)

	_selection_ring = MeshInstance3D.new()
	var ring := TorusMesh.new()
	ring.inner_radius = 0.43
	ring.outer_radius = 0.5
	ring.rings = 24
	ring.ring_segments = 8
	_selection_ring.mesh = ring
	_selection_ring.position.y = 0.035
	_selection_ring.material_override = _emissive_material(Color("55d6a9"))
	_selection_ring.visible = false
	add_child(_selection_ring)

	_name_label = _add_label(2.35, 28, Color("f8fafc"), 28.0)
	_name_label.text = display_name
	_action_label = _add_label(2.08, 18, Color("bad2ca"), 16.0)
	_speech_label = _add_label(2.72, 18, Color("fff1bd"), 20.0)
	_speech_label.visible = false


func _apply_pose() -> void:
	var t := _motion_time
	if is_instance_valid(_model_character):
		var model_state := _model_turn_state if not _model_turn_state.is_empty() else _visual_state
		_model_character.update_pose(
			model_state, t, _travel_distance, _gait_strength, _conversation_look_yaw()
		)
		return
	_update_vector_sprite(t)
	if not _body_root.visible:
		return
	_body_root.position = Vector3.ZERO
	_body_root.rotation = Vector3.ZERO
	_torso.position = Vector3(0.0, 1.04, 0.0)
	_head.position = Vector3(0.0, 1.82, 0.0)
	_head.rotation = Vector3.ZERO
	_left_arm.position = Vector3(-0.42, 1.08, 0.0)
	_right_arm.position = Vector3(0.42, 1.08, 0.0)
	_left_leg.position = Vector3(-0.17, 0.42, 0.0)
	_right_leg.position = Vector3(0.17, 0.42, 0.0)
	_left_arm.rotation = Vector3.ZERO
	_right_arm.rotation = Vector3.ZERO
	_left_leg.rotation = Vector3.ZERO
	_right_leg.rotation = Vector3.ZERO
	_cup.position = Vector3(0.48, 1.04, -0.18)
	_cup.visible = false

	match _visual_state:
		"walk", "jog":
			var amplitude := 0.72 if _visual_state == "jog" else 0.48
			var swing := sin(_stride_phase) * amplitude * _gait_strength
			_left_arm.rotation.x = swing
			_right_arm.rotation.x = -swing
			_left_leg.rotation.x = -swing
			_right_leg.rotation.x = swing
			_body_root.position.y = (
				abs(sin(_stride_phase))
				* (0.055 if _visual_state == "jog" else 0.025)
				* _gait_strength
			)
		"sit", "drink":
			_body_root.position.y = -0.32
			_body_root.position.z = 0.08
			_left_leg.rotation.x = -1.2
			_right_leg.rotation.x = -1.2
			_left_leg.position.z = -0.26
			_right_leg.position.z = -0.26
			if _visual_state == "drink":
				_cup.visible = true
				var sip := maxf(0.0, sin(t * 1.4))
				_right_arm.rotation.x = -0.75 - (sip * 0.42)
				_right_arm.rotation.z = -0.22
				_cup.position = Vector3(0.34, 1.34 + sip * 0.18, -0.34 + sip * 0.1)
		"queue":
			_body_root.position.y = sin(t * 1.7) * 0.012
			_head.rotation.y = sin(t * 0.7) * 0.15
		"talk":
			var gesture := sin(t * 2.6)
			if _is_speaking:
				_right_arm.rotation.z = -0.45 - gesture * 0.22
				_right_arm.rotation.x = -0.4
			else:
				_head.rotation.x = sin(t * 1.8) * 0.04
		"use_object":
			_right_arm.rotation.x = -0.9 + sin(t * 2.0) * 0.12
			_right_arm.rotation.z = -0.2
		_:
			_body_root.position.y = sin(t * 1.5) * 0.012
			_left_arm.rotation.z = 0.04
			_right_arm.rotation.z = -0.04

	if is_instance_valid(_speech_label) and _speech_label.visible:
		_speech_label.position.y = 2.72 + sin(t * 2.0) * 0.035


func _build_vector_sprite() -> void:
	var asset := VectorAnimationLibrary.load_asset(visual_asset_id, VECTOR_POSE_IDS)
	if asset.is_empty():
		return
	_vector_textures = asset["poses"] as Dictionary
	_vector_animations = asset["animations"] as Dictionary
	if not _vector_textures.has("idle"):
		return
	_vector_previous_sprite = _new_vector_sprite("PreviousVectorCharacter")
	_vector_previous_sprite.visible = false
	add_child(_vector_previous_sprite)
	_vector_sprite = _new_vector_sprite("VectorCharacter")
	_vector_sprite.texture = _vector_textures["idle"]
	add_child(_vector_sprite)
	_body_root.visible = false
	_vector_pose_id = "idle"


func _build_model_character() -> void:
	_model_character = AgentModel3D.instantiate_asset(visual_asset_id)
	if not is_instance_valid(_model_character):
		return
	add_child(_model_character)
	_body_root.visible = false
	if is_instance_valid(_vector_sprite):
		_vector_sprite.visible = false
	if is_instance_valid(_vector_previous_sprite):
		_vector_previous_sprite.visible = false


func _new_vector_sprite(sprite_name: String) -> Sprite3D:
	var sprite := Sprite3D.new()
	sprite.name = sprite_name
	sprite.pixel_size = 0.0075
	sprite.position.y = 0.96
	sprite.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	sprite.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	return sprite


func _update_vector_sprite(t: float) -> void:
	if not is_instance_valid(_vector_sprite):
		return
	var pose_id := _vector_pose_for_state(_visual_state)
	var next_texture := VectorAnimationLibrary.texture_for(
		_vector_textures,
		_vector_animations,
		pose_id,
		t,
		_travel_distance,
	)
	if pose_id != _vector_pose_id and _vector_textures.has(pose_id):
		_begin_vector_transition()
		_vector_pose_id = pose_id
	if next_texture != null and next_texture != _vector_sprite.texture:
		_vector_sprite.texture = next_texture
	_vector_sprite.scale = Vector3.ONE
	_vector_sprite.rotation.z = 0.0
	var bob_amplitude := 0.012
	var bob_speed := 1.5
	match _visual_state:
		"walk":
			_update_vector_facing()
			_vector_sprite.rotation.z = sin(_stride_phase) * 0.018 * _gait_strength
			_vector_sprite.position.y = (
				0.96 + abs(sin(_stride_phase)) * 0.035 * _gait_strength
			)
			return
		"jog":
			_update_vector_facing()
			_vector_sprite.rotation.z = sin(_stride_phase) * 0.028 * _gait_strength
			_vector_sprite.position.y = (
				0.96 + abs(sin(_stride_phase)) * 0.065 * _gait_strength
			)
			return
		"queue", "think", "read", "phone":
			_vector_sprite.rotation.z = sin(t * 1.3) * 0.012
		"talk", "wave":
			_vector_sprite.rotation.z = sin(t * 2.8) * 0.018
		"celebrate":
			bob_amplitude = 0.09
			bob_speed = 8.0
			var pulse: float = 1.0 + abs(sin(t * 8.0)) * 0.035
			_vector_sprite.scale = Vector3(pulse, pulse, 1.0)
		"surprised":
			var pulse: float = 1.0 + abs(sin(t * 5.0)) * 0.018
			_vector_sprite.scale = Vector3(pulse, pulse, 1.0)
		"sleep":
			bob_speed = 0.7
			_vector_sprite.rotation.z = sin(t * 0.7) * 0.008
	_vector_sprite.position.y = 0.96 + abs(sin(t * bob_speed)) * bob_amplitude


func _update_vector_facing() -> void:
	var active_camera := get_viewport().get_camera_3d()
	if active_camera == null:
		return
	var camera_right := active_camera.global_transform.basis.x.normalized()
	var screen_direction := _motion_tangent.dot(camera_right)
	if absf(screen_direction) > 0.08:
		_vector_sprite.flip_h = screen_direction < 0.0


func _begin_vector_transition() -> void:
	if not is_instance_valid(_vector_previous_sprite):
		return
	if is_instance_valid(_vector_transition):
		_vector_transition.kill()
	_vector_previous_sprite.texture = _vector_sprite.texture
	_vector_previous_sprite.position = _vector_sprite.position
	_vector_previous_sprite.rotation = _vector_sprite.rotation
	_vector_previous_sprite.scale = _vector_sprite.scale
	_vector_previous_sprite.modulate = Color.WHITE
	_vector_previous_sprite.visible = true
	_vector_sprite.modulate = Color(1.0, 1.0, 1.0, 0.0)
	_vector_transition = create_tween().set_parallel(true)
	_vector_transition.tween_property(_vector_sprite, "modulate:a", 1.0, 0.14)
	_vector_transition.tween_property(_vector_previous_sprite, "modulate:a", 0.0, 0.14)
	_vector_transition.chain().tween_callback(func() -> void: _vector_previous_sprite.visible = false)


func _vector_pose_for_state(state: String) -> String:
	return state if _vector_textures.has(state) else "idle"


func _update_action_label() -> void:
	if not is_instance_valid(_action_label):
		return
	var label := str(STATE_LABELS.get(_visual_state, "Active"))
	if _activity_progress > 0.0 and _activity_progress < 1.0:
		label += " · %d%%" % roundi(_activity_progress * 100.0)
	_action_label.text = label


func _add_capsule(
	parent: Node3D,
	mesh_position: Vector3,
	radius: float,
	height: float,
	color: Color,
) -> MeshInstance3D:
	var instance := MeshInstance3D.new()
	var capsule := CapsuleMesh.new()
	capsule.radius = radius
	capsule.height = height
	instance.mesh = capsule
	instance.position = mesh_position
	instance.material_override = _material(color)
	parent.add_child(instance)
	return instance


func _add_sphere(
	parent: Node3D,
	mesh_position: Vector3,
	radius: float,
	color: Color,
) -> MeshInstance3D:
	var instance := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = radius
	sphere.height = radius * 2.0
	instance.mesh = sphere
	instance.position = mesh_position
	instance.material_override = _material(color)
	parent.add_child(instance)
	return instance


func _add_cylinder(
	parent: Node3D,
	mesh_position: Vector3,
	radius: float,
	height: float,
	color: Color,
) -> MeshInstance3D:
	var instance := MeshInstance3D.new()
	var cylinder := CylinderMesh.new()
	cylinder.top_radius = radius
	cylinder.bottom_radius = radius
	cylinder.height = height
	cylinder.radial_segments = 16
	instance.mesh = cylinder
	instance.position = mesh_position
	instance.material_override = _material(color)
	parent.add_child(instance)
	return instance


func _add_label(height: float, size: int, color: Color, max_distance: float) -> Label3D:
	var label := Label3D.new()
	label.position.y = height
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.fixed_size = false
	label.pixel_size = 0.007
	label.font_size = size
	label.outline_size = 5
	label.modulate = color
	label.outline_modulate = Color(0.025, 0.035, 0.05, 0.92)
	label.visibility_range_end = max_distance
	label.visibility_range_end_margin = 2.0
	add_child(label)
	return label


func _material(color: Color, transparent := false) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.78
	if transparent:
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return material


func _emissive_material(color: Color) -> StandardMaterial3D:
	var material := _material(color)
	material.emission_enabled = true
	material.emission = color
	material.emission_energy_multiplier = 1.2
	return material


func _on_input_event(
	_camera: Node,
	event: InputEvent,
	_event_position: Vector3,
	_normal: Vector3,
	_shape_idx: int,
) -> void:
	if event is InputEventMouseMotion and _selection_press_active:
		if event.position.distance_to(_selection_press_position) > SELECTION_DRAG_THRESHOLD_PIXELS:
			_selection_press_active = false
		return
	if not event is InputEventMouseButton or event.button_index != MOUSE_BUTTON_LEFT:
		return
	if event.pressed:
		_selection_press_position = event.position
		_selection_press_active = true
	elif _selection_press_active:
		_selection_press_active = false
		selected.emit(agent_id)


func _resolve_visual_state(snapshot: Dictionary) -> String:
	if snapshot.get("movement") is Dictionary:
		var movement: Dictionary = snapshot["movement"]
		if movement.get("state") == "paused":
			return "talk"
		return "jog" if movement.get("movement_mode") == "jog" else "walk"
	var activity: Variant = snapshot.get("activity")
	if not activity is Dictionary:
		return "idle"
	if activity.get("status") == "navigating":
		return "walk"
	if activity.get("status") == "waiting_for_resource":
		return "queue"
	if activity.get("status") == "paused":
		return "talk"
	if activity.get("status") != "performing":
		return "idle"
	var configured_visual_state := str(activity.get("visual_state", ""))
	if not configured_visual_state.is_empty():
		return configured_visual_state
	match str(activity.get("activity_type", "")):
		"drink_coffee":
			return "drink"
		"plaza_jog":
			return "jog"
		_:
			return "use_object"


func _resolve_activity_progress(snapshot: Dictionary) -> float:
	var activity: Variant = snapshot.get("activity")
	if not activity is Dictionary:
		return 0.0
	return clampf(float(activity.get("progress", 0.0)), 0.0, 1.0)
