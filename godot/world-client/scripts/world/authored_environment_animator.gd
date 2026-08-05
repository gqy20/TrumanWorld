class_name AuthoredEnvironmentAnimator
extends Node

var _ocean: Node3D
var _ocean_origin := Vector3.ZERO
var _phase := 0.0


func configure(authored_root: Node3D) -> void:
	_ocean = authored_root.find_child("BacklotOcean", true, false) as Node3D
	if is_instance_valid(_ocean):
		_ocean_origin = _ocean.position
	set_process(is_instance_valid(_ocean))


func _process(delta: float) -> void:
	if not is_instance_valid(_ocean):
		set_process(false)
		return
	_phase = fmod(_phase + delta, TAU * 8.0)
	_ocean.position = _ocean_origin + Vector3(0.0, sin(_phase * 0.42) * 0.025, 0.0)
	_ocean.rotation.y = sin(_phase * 0.17) * 0.0025
