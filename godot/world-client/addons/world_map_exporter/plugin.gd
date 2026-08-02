@tool
extends EditorPlugin

const MENU_LABEL := "Export World Map"
const MAP_ID_SETTING := "world_map_export/map_id"
const OUTPUT_PATH_SETTING := "world_map_export/output_path"
const METERS_PER_UNIT_SETTING := "world_map_export/meters_per_unit"


func _enter_tree() -> void:
	add_tool_menu_item(MENU_LABEL, _export_edited_scene)


func _exit_tree() -> void:
	remove_tool_menu_item(MENU_LABEL)


func _export_edited_scene() -> void:
	var scene_root := EditorInterface.get_edited_scene_root()
	if scene_root == null:
		push_error("Open a world map scene before exporting")
		return
	var map_id := str(ProjectSettings.get_setting(MAP_ID_SETTING, ""))
	var output_path := str(ProjectSettings.get_setting(OUTPUT_PATH_SETTING, ""))
	var meters_per_unit := float(ProjectSettings.get_setting(METERS_PER_UNIT_SETTING, 1.0))
	if map_id.is_empty() or output_path.is_empty():
		push_error("Configure %s and %s before exporting" % [MAP_ID_SETTING, OUTPUT_PATH_SETTING])
		return
	var exporter := WorldMapExporter.new()
	var result := exporter.build_document(scene_root, map_id, meters_per_unit)
	if not result.get("ok", false):
		push_error("World map export failed: %s" % "; ".join(result.get("errors", [])))
		return
	var error := exporter.write_document(result["document"], output_path)
	if error != OK:
		push_error("Could not write world map: %s" % error_string(error))
		return
	print("Exported world map %s to %s" % [map_id, output_path])
