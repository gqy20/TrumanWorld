class_name WorldAtmosphere
extends RefCounted

const NIGHT_BACKGROUND := Color("0b1320")
const DAWN_BACKGROUND := Color("8b6d65")
const DAY_BACKGROUND := Color("b8d2cc")
const NIGHT_AMBIENT := Color("38506b")
const DAY_AMBIENT := Color("d8e5dc")

var _environment: Environment
var _sun: DirectionalLight3D
var _root: Node


func configure(environment: Environment, sun: DirectionalLight3D, root: Node) -> void:
	_environment = environment
	_sun = sun
	_root = root


func update(world_time_seconds: float) -> void:
	if _environment == null or not is_instance_valid(_sun):
		return
	var time := Time.get_datetime_dict_from_unix_time(int(world_time_seconds))
	var hour := float(time.get("hour", 12)) + float(time.get("minute", 0)) / 60.0
	var daylight := smoothstep(5.25, 7.5, hour) * (1.0 - smoothstep(17.25, 20.0, hour))
	var dawn_mix := smoothstep(4.8, 6.4, hour) * (1.0 - smoothstep(7.3, 9.0, hour))
	_environment.background_color = NIGHT_BACKGROUND.lerp(DAY_BACKGROUND, daylight).lerp(
		DAWN_BACKGROUND, dawn_mix * 0.52
	)
	_environment.ambient_light_color = NIGHT_AMBIENT.lerp(DAY_AMBIENT, daylight)
	_environment.ambient_light_energy = lerpf(0.28, 0.72, daylight)
	_sun.light_energy = lerpf(0.08, 1.18, daylight)
	_sun.light_color = Color("9db5d6").lerp(Color("ffe1ac"), daylight)
	_sun.rotation_degrees = Vector3(-18.0 - daylight * 42.0, hour * 8.0 - 105.0, 0.0)
	if is_instance_valid(_root):
		for light: Node in _root.get_tree().get_nodes_in_group("night_light"):
			if light is OmniLight3D:
				(light as OmniLight3D).light_energy = lerpf(1.7, 0.0, daylight)
