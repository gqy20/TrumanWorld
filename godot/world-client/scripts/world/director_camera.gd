class_name DirectorCamera
extends Node3D

@onready var camera: Camera3D = $Camera3D

var _desired_target := Vector3(0.0, 0.6, 0.0)
var _current_target := Vector3(0.0, 0.6, 0.0)
var _yaw := 0.64
var _pitch := 0.58
var _distance := 14.5
var _drag_mode := 0
var _overview_target := Vector3(0.0, 0.6, -0.5)
var _overview_yaw := 0.64
var _overview_pitch := 0.58
var _overview_distance := 14.5
var _max_distance := 22.0

const ORBIT_DRAG := 1
const PAN_DRAG := 2


func _ready() -> void:
	_update_camera(1.0)


func _process(delta: float) -> void:
	_current_target = _current_target.lerp(_desired_target, minf(1.0, delta * 4.5))
	_update_camera(delta)


func focus_position(target: Vector3, close_view := true) -> void:
	_desired_target = target
	if close_view:
		_distance = minf(_distance, 8.5)


func configure_from_map(map_root: Node3D) -> void:
	for raw_anchor: Node in map_root.find_children("*", "CameraAnchor3D", true, false):
		var anchor := raw_anchor as CameraAnchor3D
		if not anchor.stable_id.ends_with(":overview"):
			continue
		_overview_target = anchor.look_at_position
		var offset := anchor.global_position - anchor.look_at_position
		_overview_distance = maxf(5.0, offset.length())
		# Keep normal navigation inside the authored visual buffer. Story-specific boundary
		# reveals use camera anchors instead of exposing the edge through unrestricted zoom.
		_max_distance = maxf(22.0, _overview_distance * 1.08)
		_overview_yaw = atan2(offset.x, offset.z)
		_overview_pitch = atan2(offset.y, Vector2(offset.x, offset.z).length())
		show_overview()
		return


func show_overview() -> void:
	_desired_target = _overview_target
	_distance = _overview_distance
	_yaw = _overview_yaw
	_pitch = _overview_pitch


func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
			_distance = maxf(5.0, _distance - 1.1)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
			_distance = minf(_max_distance, _distance + 1.1)
		elif event.button_index == MOUSE_BUTTON_LEFT:
			# Left drag is the primary web interaction. A press without motion still reaches
			# AgentAvatar, so selecting a resident remains independent from camera orbiting.
			_drag_mode = PAN_DRAG if event.shift_pressed and event.pressed else (
				ORBIT_DRAG if event.pressed else 0
			)
		elif event.button_index == MOUSE_BUTTON_RIGHT:
			_drag_mode = ORBIT_DRAG if event.pressed else 0
		elif event.button_index == MOUSE_BUTTON_MIDDLE:
			_drag_mode = PAN_DRAG if event.pressed else 0
	elif event is InputEventMouseMotion and _drag_mode != 0:
		if _drag_mode == ORBIT_DRAG:
			_yaw -= event.relative.x * 0.008
			_pitch = clampf(_pitch + event.relative.y * 0.006, 0.2, 1.18)
		else:
			var right := camera.global_basis.x
			var forward := -camera.global_basis.z
			forward.y = 0.0
			_desired_target += (-right * event.relative.x + forward * event.relative.y) * 0.012


func _update_camera(_delta: float) -> void:
	if not is_instance_valid(camera):
		return
	var horizontal := cos(_pitch) * _distance
	var offset := Vector3(
		sin(_yaw) * horizontal,
		sin(_pitch) * _distance,
		cos(_yaw) * horizontal,
	)
	camera.global_position = _current_target + offset
	camera.look_at(_current_target, Vector3.UP)
