class_name ClientClock
extends RefCounted

var _base_world_time_seconds := 0.0
var _speed := 1.0
var _running := false
var _synchronized_at_msec := 0


func synchronize(world_time_iso: String, run_status: String, speed: float) -> bool:
	var parsed := Time.get_unix_time_from_datetime_string(world_time_iso)
	if parsed <= 0:
		return false
	_base_world_time_seconds = float(parsed)
	_speed = clampf(speed, 0.25, 8.0)
	_running = run_status == "running"
	_synchronized_at_msec = Time.get_ticks_msec()
	return true


func world_time_seconds() -> float:
	return project_world_time(float(Time.get_ticks_msec() - _synchronized_at_msec) / 1000.0)


func project_world_time(elapsed_real_seconds: float) -> float:
	if not _running:
		return _base_world_time_seconds
	return _base_world_time_seconds + (maxf(0.0, elapsed_real_seconds) * _speed)


func set_status(run_status: String) -> void:
	_commit_projection()
	_running = run_status == "running"


func set_speed(speed: float) -> void:
	_commit_projection()
	_speed = clampf(speed, 0.25, 8.0)


func is_running() -> bool:
	return _running


func speed() -> float:
	return _speed


func _commit_projection() -> void:
	_base_world_time_seconds = world_time_seconds()
	_synchronized_at_msec = Time.get_ticks_msec()
