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
var _vector_pose_id := ""
var _vector_transition: Tween
var _target_position := Vector3.ZERO
var _has_position := false
var _visual_state := "idle"
var _presentation_paused := false
var _motion_time := 0.0
var _activity_progress := 0.0
var _conversation_partner_position := Vector3.ZERO
var _has_conversation_partner := false
var _is_speaking := false


func _ready() -> void:
	input_ray_pickable = true
	_build_visuals()
	input_event.connect(_on_input_event)


func configure(snapshot: Dictionary) -> void:
	agent_id = str(snapshot.get("id", "unknown-agent"))
	display_name = str(snapshot.get("name", agent_id))
	name = "Agent_%s" % agent_id.validate_node_name()
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
		if not _has_position:
			position = _target_position
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
		var offset := _target_position - position
		if offset.length_squared() > 0.0001:
			position = position.lerp(_target_position, minf(1.0, delta * 4.5))
			if _visual_state in ["walk", "jog"]:
				var desired_yaw := atan2(offset.x, offset.z)
				rotation.y = lerp_angle(rotation.y, desired_yaw, minf(1.0, delta * 7.0))
		if _has_conversation_partner:
			var partner_offset := _conversation_partner_position - global_position
			if partner_offset.length_squared() > 0.01:
				rotation.y = lerp_angle(
					rotation.y,
					atan2(partner_offset.x, partner_offset.z),
					minf(1.0, delta * 6.0),
				)
	_apply_pose()


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


func clear_conversation() -> void:
	_has_conversation_partner = false
	_is_speaking = false
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

	_name_label = _add_label(2.35, 28, Color("f8fafc"))
	_name_label.text = display_name
	_action_label = _add_label(2.08, 18, Color("bad2ca"))
	_speech_label = _add_label(2.72, 18, Color("fff1bd"))
	_speech_label.visible = false


func _apply_pose() -> void:
	var t := _motion_time
	_update_vector_sprite(t)
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
			var pace := 8.0 if _visual_state == "jog" else 5.2
			var amplitude := 0.72 if _visual_state == "jog" else 0.48
			var swing := sin(t * pace) * amplitude
			_left_arm.rotation.x = swing
			_right_arm.rotation.x = -swing
			_left_leg.rotation.x = -swing
			_right_leg.rotation.x = swing
			_body_root.position.y = abs(sin(t * pace)) * (0.055 if _visual_state == "jog" else 0.025)
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
	var asset_parts := visual_asset_id.split("/", false)
	if asset_parts.size() != 2 or asset_parts[0].is_empty() or asset_parts[1].is_empty():
		return
	if asset_parts[0] in [".", ".."] or asset_parts[1] in [".", ".."]:
		return
	for pose_id: String in VECTOR_POSE_IDS:
		var path := "res://assets/scenarios/%s/characters/%s/vector/%s.svg" % [
			asset_parts[0], asset_parts[1], pose_id,
		]
		if ResourceLoader.exists(path):
			var texture := load(path) as Texture2D
			if texture != null:
				_vector_textures[pose_id] = texture
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
	if pose_id != _vector_pose_id and _vector_textures.has(pose_id):
		_begin_vector_transition()
		_vector_sprite.texture = _vector_textures[pose_id]
		_vector_pose_id = pose_id
	_vector_sprite.scale = Vector3.ONE
	_vector_sprite.rotation.z = 0.0
	var bob_amplitude := 0.012
	var bob_speed := 1.5
	match _visual_state:
		"walk":
			bob_amplitude = 0.035
			bob_speed = 7.0
		"jog":
			bob_amplitude = 0.065
			bob_speed = 10.0
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


func _add_label(height: float, size: int, color: Color) -> Label3D:
	var label := Label3D.new()
	label.position.y = height
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.fixed_size = false
	label.pixel_size = 0.007
	label.font_size = size
	label.outline_size = 5
	label.modulate = color
	label.outline_modulate = Color(0.025, 0.035, 0.05, 0.92)
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
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
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
