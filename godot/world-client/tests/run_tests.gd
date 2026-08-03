extends SceneTree

var _failures := 0


func _initialize() -> void:
	_test_valid_host_message()
	_test_protocol_mismatch()
	_test_unknown_type()
	_test_fixture_shape()
	_test_world_map_export()
	_test_runtime_map_visuals()
	_test_world_map_duplicate_id()
	_test_world_map_disconnected_entrances()
	_test_client_clock_pause_and_speed()
	_test_activity_visual_mapping()
	if _failures == 0:
		print("Godot world client tests passed")
		quit(0)
	else:
		printerr("Godot world client tests failed: %s" % _failures)
		quit(1)


func _test_valid_host_message() -> void:
	var result := WorldProtocolCodec.decode_host_message(JSON.stringify({
		"protocol_version": 1,
		"run_id": "run-1",
		"sequence": 1,
		"type": "initialize",
		"payload": {},
	}))
	_expect(result.get("ok", false), "valid initialize message is accepted")


func _test_protocol_mismatch() -> void:
	var result := WorldProtocolCodec.decode_host_message(JSON.stringify({
		"protocol_version": 99,
		"run_id": "run-1",
		"sequence": 1,
		"type": "initialize",
		"payload": {},
	}))
	_expect(not result.get("ok", true), "protocol mismatch is rejected")


func _test_unknown_type() -> void:
	var result := WorldProtocolCodec.decode_host_message(JSON.stringify({
		"protocol_version": 1,
		"run_id": "run-1",
		"sequence": 1,
		"type": "execute_script",
		"payload": {},
	}))
	_expect(not result.get("ok", true), "unknown host type is rejected")


func _test_fixture_shape() -> void:
	var file := FileAccess.open("res://tests/fixtures/world_snapshot.json", FileAccess.READ)
	_expect(file != null, "world fixture can be opened")
	if file == null:
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	_expect(parsed is Dictionary, "world fixture is an object")
	if parsed is Dictionary:
		_expect(parsed.get("agents", []).size() == 3, "world fixture contains three agents")


func _test_world_map_export() -> void:
	var scene := load("res://scenes/maps/campus_world.tscn") as PackedScene
	_expect(scene != null, "campus map scene can be loaded")
	if scene == null:
		return
	var root := scene.instantiate()
	var result := WorldMapExporter.new().build_document(root, "campus-world-v2")
	root.free()
	_expect(result.get("ok", false), "campus map exports successfully")
	if not result.get("ok", false):
		return
	var document: Dictionary = result["document"]
	_expect(document["locations"].size() == 5, "map export contains five locations")
	_expect(document["zones"].size() == 7, "map export contains seven zones")
	_expect(document["interactables"].size() == 2, "map export contains cafe resources")
	_expect(document["interaction_slots"].size() == 5, "map export contains resource slots")
	_expect(document["route_edges"][0]["distance_meters"] > 0.0, "route distance is derived")
	_expect(
		str(document["content_hash"]).begins_with("sha256:"),
		"map export includes a content hash",
	)


func _test_runtime_map_visuals() -> void:
	var scene := load("res://scenes/maps/campus_world.tscn") as PackedScene
	var map_root := scene.instantiate() as Node3D
	root.add_child(map_root)
	var visuals := RuntimeMapVisuals.build(map_root)
	var meshes := visuals.find_children("*", "MeshInstance3D", true, false)
	_expect(meshes.size() >= 15, "runtime map builds visible roads and locations")
	map_root.free()


func _test_world_map_duplicate_id() -> void:
	var root := Node3D.new()
	var first := RouteNode3D.new()
	first.stable_id = "route:duplicate"
	root.add_child(first)
	var second := RouteNode3D.new()
	second.stable_id = "route:duplicate"
	root.add_child(second)
	var result := WorldMapExporter.new().build_document(root, "invalid-map")
	root.free()
	_expect(not result.get("ok", true), "duplicate stable IDs are rejected")


func _test_world_map_disconnected_entrances() -> void:
	var scene := load("res://scenes/maps/campus_world.tscn") as PackedScene
	var root := scene.instantiate()
	root.get_node("Routes/QuadToCenter").free()
	root.get_node("Routes/CenterToCafe").free()
	var result := WorldMapExporter.new().build_document(root, "invalid-map")
	root.free()
	_expect(not result.get("ok", true), "disconnected location entrances are rejected")


func _test_client_clock_pause_and_speed() -> void:
	var clock := ClientClock.new()
	_expect(
		clock.synchronize("2026-03-02T09:00:00Z", "running", 2.0),
		"client clock accepts authoritative world time",
	)
	_expect(
		clock.project_world_time(5.0) == 1772442010.0,
		"client clock projects elapsed time using simulation speed",
	)
	clock.set_status("paused")
	var paused_time := clock.world_time_seconds()
	_expect(
		clock.project_world_time(20.0) == paused_time,
		"client clock freezes while paused",
	)


func _test_activity_visual_mapping() -> void:
	var avatar := AgentAvatar.new()
	avatar.configure({
		"id": "mei",
		"name": "Mei",
		"position_meters": [0.0, 0.0, 0.0],
		"activity": {"activity_type": "drink_coffee", "status": "performing"},
	})
	_expect(avatar.visual_state() == "drink", "performing coffee activity maps to drink")
	avatar.configure({
		"id": "mei",
		"name": "Mei",
		"position_meters": [0.0, 0.0, 0.0],
		"activity": {"activity_type": "drink_coffee", "status": "waiting_for_resource"},
	})
	_expect(avatar.visual_state() == "queue", "waiting activity maps to queue")
	avatar.configure({
		"id": "mei",
		"name": "Mei",
		"position_meters": [0.0, 0.0, 0.0],
		"activity": {"activity_type": "drink_coffee", "status": "paused"},
	})
	_expect(avatar.visual_state() == "talk", "paused activity maps to talk")
	avatar.configure({
		"id": "mei",
		"name": "Mei",
		"position_meters": [0.0, 0.0, 0.0],
		"movement": {"state": "paused"},
	})
	_expect(avatar.visual_state() == "talk", "paused movement maps to talk")
	avatar.configure({
		"id": "mei",
		"name": "Mei",
		"position_meters": [0.0, 0.0, 0.0],
		"activity": {
			"activity_type": "drink_coffee",
			"status": "performing",
			"visual_state": "sit",
		},
	})
	_expect(avatar.visual_state() == "sit", "configured step visual state is authoritative")
	avatar.free()


func _expect(condition: bool, message: String) -> void:
	if condition:
		print("PASS: %s" % message)
		return
	_failures += 1
	printerr("FAIL: %s" % message)
