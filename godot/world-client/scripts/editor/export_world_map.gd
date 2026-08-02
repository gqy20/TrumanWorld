extends SceneTree

const DEFAULT_SOURCE := "res://scenes/maps/campus_world.tscn"
const DEFAULT_MAP_ID := "campus-world-v2"


func _initialize() -> void:
	var options := _parse_options(OS.get_cmdline_user_args())
	var source_path := str(options.get("source", DEFAULT_SOURCE))
	var output_path := str(options.get("output", "res://generated/world-map.json"))
	var map_id := str(options.get("map-id", DEFAULT_MAP_ID))

	var packed_scene := load(source_path) as PackedScene
	if packed_scene == null:
		printerr("Unable to load map scene: %s" % source_path)
		quit(1)
		return
	var instance := packed_scene.instantiate()
	root.add_child(instance)

	var exporter := WorldMapExporter.new()
	var result := exporter.build_document(instance, map_id)
	if not result.get("ok", false):
		for error: String in result.get("errors", []):
			printerr(error)
		quit(1)
		return
	var write_error := exporter.write_document(result["document"], output_path)
	if write_error != OK:
		printerr("Unable to write map manifest: %s" % error_string(write_error))
		quit(1)
		return
	print("Exported %s to %s" % [map_id, output_path])
	quit(0)


func _parse_options(arguments: PackedStringArray) -> Dictionary:
	var options := {}
	var index := 0
	while index < arguments.size():
		var argument := arguments[index]
		if argument.begins_with("--") and index + 1 < arguments.size():
			options[argument.trim_prefix("--")] = arguments[index + 1]
			index += 2
		else:
			index += 1
	return options
