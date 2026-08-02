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

var agent_id := ""
var display_name := ""
var _body_mesh: MeshInstance3D
var _name_label: Label3D
var _target_position := Vector3.ZERO
var _has_position := false
var _visual_state := "idle"
var _presentation_paused := false


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
	if is_instance_valid(_body_mesh):
		var material := _body_mesh.material_override as StandardMaterial3D
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
	rotation.y = float(snapshot.get("facing_radians", 0.0))
	_visual_state = _resolve_visual_state(snapshot)
	if is_instance_valid(_name_label):
		_name_label.text = "%s · %s" % [display_name, _visual_state]


func _process(delta: float) -> void:
	if _presentation_paused or not _has_position:
		return
	position = position.lerp(_target_position, minf(1.0, delta * 8.0))


func set_presentation_paused(value: bool) -> void:
	_presentation_paused = value


func visual_state() -> String:
	return _visual_state


func set_highlighted(is_highlighted: bool) -> void:
	if not is_instance_valid(_body_mesh):
		return
	var material := _body_mesh.material_override as StandardMaterial3D
	material.emission_enabled = is_highlighted
	material.emission = material.albedo_color.lightened(0.25)
	material.emission_energy_multiplier = 0.8 if is_highlighted else 0.0


func _build_visuals() -> void:
	_body_mesh = MeshInstance3D.new()
	var capsule := CapsuleMesh.new()
	capsule.radius = 0.32
	capsule.height = 1.35
	_body_mesh.mesh = capsule
	_body_mesh.position.y = 0.85
	var material := StandardMaterial3D.new()
	material.roughness = 0.8
	_body_mesh.material_override = material
	add_child(_body_mesh)

	var head := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = 0.27
	sphere.height = 0.54
	head.mesh = sphere
	head.position.y = 1.72
	var head_material := StandardMaterial3D.new()
	head_material.albedo_color = Color("f0c7a5")
	head_material.roughness = 0.9
	head.material_override = head_material
	add_child(head)

	var collision := CollisionShape3D.new()
	var collision_shape := CapsuleShape3D.new()
	collision_shape.radius = 0.4
	collision_shape.height = 1.8
	collision.shape = collision_shape
	collision.position.y = 0.9
	add_child(collision)

	_name_label = Label3D.new()
	_name_label.position.y = 2.25
	_name_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_name_label.fixed_size = true
	_name_label.font_size = 34
	_name_label.outline_size = 8
	_name_label.modulate = Color("f8fafc")
	_name_label.outline_modulate = Color(0.04, 0.06, 0.09, 0.9)
	_name_label.text = display_name
	add_child(_name_label)


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
		return "jog" if movement.get("movement_mode") == "jog" else "walk"
	var activity: Variant = snapshot.get("activity")
	if not activity is Dictionary:
		return "idle"
	if activity.get("status") == "navigating":
		return "walk"
	if activity.get("status") != "performing":
		return "idle"
	match str(activity.get("activity_type", "")):
		"drink_coffee":
			return "drink"
		"plaza_jog":
			return "jog"
		_:
			return "use_object"
