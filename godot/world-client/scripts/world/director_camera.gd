class_name DirectorCamera
extends Node3D

@onready var camera: Camera3D = $Camera3D

var _desired_target := Vector3(0.0, 0.6, 0.0)
var _current_target := Vector3(0.0, 0.6, 0.0)
var _yaw := 0.64
var _pitch := 0.58
var _distance := 14.5
var _drag_mode := 0


func _ready() -> void:
	_update_camera(1.0)


func _process(delta: float) -> void:
	_current_target = _current_target.lerp(_desired_target, minf(1.0, delta * 4.5))
	_update_camera(delta)


func focus_position(target: Vector3, close_view := true) -> void:
	_desired_target = target
	if close_view:
		_distance = minf(_distance, 8.5)


func show_overview() -> void:
	_desired_target = Vector3(0.0, 0.6, -0.5)
	_distance = 14.5
	_yaw = 0.64
	_pitch = 0.58


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
			_distance = maxf(5.0, _distance - 1.1)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
			_distance = minf(22.0, _distance + 1.1)
		elif event.button_index == MOUSE_BUTTON_RIGHT:
			_drag_mode = 1 if event.pressed else 0
		elif event.button_index == MOUSE_BUTTON_MIDDLE:
			_drag_mode = 2 if event.pressed else 0
	elif event is InputEventMouseMotion and _drag_mode != 0:
		if _drag_mode == 1:
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
