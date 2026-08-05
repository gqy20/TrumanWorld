class_name DirectorCamera
extends Node3D

enum CameraMode { OVERVIEW, FREE, FOLLOW_AGENT }

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
var _last_focus_target := Vector3.ZERO
var _has_focus_target := false
var _mode := CameraMode.OVERVIEW

const ORBIT_DRAG := 1
const PAN_DRAG := 2
const MOVE_SPEED := 8.0
const BOOST_MULTIPLIER := 2.4
const PAN_HALF_EXTENTS := Vector2(45.0, 30.0)


func _ready() -> void:
	_update_camera(1.0)


func _process(delta: float) -> void:
	_move_from_keyboard(delta)
	_current_target = _current_target.lerp(_desired_target, minf(1.0, delta * 4.5))
	_update_camera(delta)


func focus_position(target: Vector3, close_view := true) -> void:
	_last_focus_target = target
	_has_focus_target = true
	_mode = CameraMode.FOLLOW_AGENT
	_set_desired_target(target)
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
	_mode = CameraMode.OVERVIEW
	_set_desired_target(_overview_target)
	_distance = _overview_distance
	_yaw = _overview_yaw
	_pitch = _overview_pitch


func update_follow_target(target: Vector3) -> void:
	_last_focus_target = target
	_has_focus_target = true
	if _mode == CameraMode.FOLLOW_AGENT:
		_set_desired_target(target)


func is_following_target() -> bool:
	return _mode == CameraMode.FOLLOW_AGENT


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
			if event.pressed:
				_enter_free_mode()
			_drag_mode = PAN_DRAG if event.pressed else 0
		elif event.button_index == MOUSE_BUTTON_MIDDLE:
			if event.pressed:
				_enter_free_mode()
			_drag_mode = PAN_DRAG if event.pressed else 0
	elif event is InputEventMouseMotion and _drag_mode != 0:
		if _drag_mode == ORBIT_DRAG:
			_yaw -= event.relative.x * 0.008
			_pitch = clampf(_pitch + event.relative.y * 0.006, 0.2, 1.18)
		else:
			_enter_free_mode()
			_set_desired_target(
				_desired_target
				+ (-_ground_right() * event.relative.x + _ground_forward() * event.relative.y)
				* (0.0011 * _distance)
			)
	elif event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_HOME or event.physical_keycode == KEY_HOME:
			show_overview()
		elif (event.keycode == KEY_F or event.physical_keycode == KEY_F) and _has_focus_target:
			focus_position(_last_focus_target)
		else:
			var key_axis := _movement_axis_for_event(event)
			if not key_axis.is_zero_approx():
				# Give short taps an immediate nudge; holding the key remains frame-rate independent
				# through _move_from_keyboard().
				_move_target(key_axis, 0.15, event.shift_pressed)


func _move_from_keyboard(delta: float) -> void:
	var axis := Vector2.ZERO
	if Input.is_physical_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
		axis.x -= 1.0
	if Input.is_physical_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
		axis.x += 1.0
	if Input.is_physical_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
		axis.y += 1.0
	if Input.is_physical_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):
		axis.y -= 1.0
	if axis.is_zero_approx():
		return
	_move_target(axis.normalized(), delta, Input.is_key_pressed(KEY_SHIFT))


func _movement_axis_for_event(event: InputEventKey) -> Vector2:
	var key := event.physical_keycode if event.physical_keycode != 0 else event.keycode
	match key:
		KEY_A, KEY_LEFT:
			return Vector2.LEFT
		KEY_D, KEY_RIGHT:
			return Vector2.RIGHT
		KEY_W, KEY_UP:
			return Vector2(0.0, 1.0)
		KEY_S, KEY_DOWN:
			return Vector2(0.0, -1.0)
	return Vector2.ZERO


func _move_target(axis: Vector2, delta: float, boosted := false) -> void:
	_enter_free_mode()
	var speed := MOVE_SPEED * (BOOST_MULTIPLIER if boosted else 1.0)
	_set_desired_target(
		_desired_target
		+ (_ground_right() * axis.x + _ground_forward() * axis.y) * speed * delta
	)


func _enter_free_mode() -> void:
	_mode = CameraMode.FREE


func _ground_right() -> Vector3:
	return Vector3(cos(_yaw), 0.0, -sin(_yaw))


func _ground_forward() -> Vector3:
	return Vector3(-sin(_yaw), 0.0, -cos(_yaw))


func _set_desired_target(target: Vector3) -> void:
	_desired_target = Vector3(
		clampf(
			target.x,
			_overview_target.x - PAN_HALF_EXTENTS.x,
			_overview_target.x + PAN_HALF_EXTENTS.x,
		),
		target.y,
		clampf(
			target.z,
			_overview_target.z - PAN_HALF_EXTENTS.y,
			_overview_target.z + PAN_HALF_EXTENTS.y,
		),
	)


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
