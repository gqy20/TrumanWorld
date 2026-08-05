extends SceneTree

var _failures := 0


func _initialize() -> void:
	_test_valid_host_message()
	_test_protocol_mismatch()
	_test_unknown_type()
	_test_fixture_shape()
	_test_scenario_scene_registry()
	_test_world_map_export()
	_test_narrative_world_map_export()
	_test_runtime_map_visuals()
	_test_narrative_runtime_visuals()
	_test_world_map_duplicate_id()
	_test_world_map_disconnected_entrances()
	_test_client_clock_pause_and_speed()
	_test_activity_visual_mapping()
	_test_mei_vector_avatar()
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


func _test_scenario_scene_registry() -> void:
	var campus := ScenarioSceneRegistry.resolve("campus_world")
	var narrative := ScenarioSceneRegistry.resolve("narrative_world")
	_expect(campus.get("map_id") == "campus-world-v2", "registry resolves the campus map")
	_expect(
		narrative.get("map_id") == "narrative-world-v1",
		"registry resolves the narrative world map",
	)
	_expect(ScenarioSceneRegistry.resolve("missing_world").is_empty(), "unknown maps are rejected")
	var narrative_map := ScenarioSceneRegistry.instantiate_map("narrative_world")
	_expect(narrative_map is Node3D, "registry instantiates the narrative world scene")
	if narrative_map != null:
		narrative_map.free()


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


func _test_narrative_world_map_export() -> void:
	var scene := load("res://scenes/maps/narrative_world.tscn") as PackedScene
	_expect(scene != null, "narrative world map scene can be loaded")
	if scene == null:
		return
	var map_root := scene.instantiate()
	var result := WorldMapExporter.new().build_document(map_root, "narrative-world-v1")
	map_root.free()
	_expect(result.get("ok", false), "narrative world map exports successfully")
	if not result.get("ok", false):
		return
	var document: Dictionary = result["document"]
	_expect(document["locations"].size() == 7, "narrative map contains seven town locations")
	_expect(document["zones"].size() == 11, "narrative map contains eleven authored zones")
	_expect(document["portals"].size() == 4, "narrative map links key interior zones")
	_expect(document["interactables"].size() == 7, "narrative map contains embodied props")
	_expect(document["interaction_slots"].size() == 12, "narrative props expose exact slots")
	_expect(document["camera_anchors"].size() == 4, "narrative map exports director views")
	_expect(document["route_edges"].size() == 15, "narrative map route graph follows town streets")


func _test_runtime_map_visuals() -> void:
	var scene := load("res://scenes/maps/campus_world.tscn") as PackedScene
	var map_root := scene.instantiate() as Node3D
	root.add_child(map_root)
	var visuals := RuntimeMapVisuals.build(map_root)
	var meshes := visuals.find_children("*", "MeshInstance3D", true, false)
	_expect(meshes.size() >= 80, "runtime map builds authored and procedural geometry")
	var cafe := visuals.get_node_or_null("AuthoredStudioCafe")
	_expect(cafe is Node3D, "runtime map instantiates the authored Studio Cafe GLB")
	if cafe is Node3D:
		var cafe_meshes := cafe.find_children("*", "MeshInstance3D", true, false)
		_expect(cafe_meshes.size() >= 100, "authored Studio Cafe contains detailed geometry")
		var bounds := AABB()
		var has_bounds := false
		for raw_mesh: Node in cafe_meshes:
			var mesh := raw_mesh as MeshInstance3D
			var to_cafe := _relative_transform(cafe as Node3D, mesh)
			var mesh_bounds: AABB = to_cafe * mesh.get_aabb()
			bounds = bounds.merge(mesh_bounds) if has_bounds else mesh_bounds
			has_bounds = true
		_expect(
			has_bounds and bounds.size.x > 3.5 and bounds.size.y > 2.0 and bounds.size.z > 2.8,
			"authored Studio Cafe preserves meter scale and Y-up orientation",
		)
	var landmarks := visuals.get_node_or_null("AuthoredCampusLandmarks")
	_expect(landmarks is Node3D, "runtime map instantiates authored campus landmarks")
	if landmarks is Node3D:
		var landmark_meshes := landmarks.find_children("*", "MeshInstance3D", true, false)
		_expect(landmark_meshes.size() >= 260, "campus environment contains detailed geometry")
		_expect(
			landmarks.find_child("CampusGround", true, false) != null
			and landmarks.find_child("SouthBoulevard", true, false) != null
			and landmarks.find_child("CampusArchitecture", true, false) != null
			and landmarks.find_child("CampusEntryBeam", true, false) != null
			and landmarks.find_child("CampusTrees", true, false) != null
			and landmarks.find_child("CampusLamps", true, false) != null,
			"authored environment fills the campus beyond primary locations",
		)
		_expect(
			landmarks.find_child("DormText", true, false) != null
			and landmarks.find_child("LectureText", true, false) != null
			and landmarks.find_child("LibraryText", true, false) != null,
			"authored buildings retain distinct visual identities",
		)
		_expect(
			landmarks.find_child("FountainJet", true, false) != null
			and landmarks.find_child("DormPillow1", true, false) != null
			and landmarks.find_child("LectureMicrophoneHead", true, false) != null
			and landmarks.find_child("LibraryLampShade1", true, false) != null,
			"campus landmarks retain location-specific prop details",
		)
	map_root.free()


func _test_narrative_runtime_visuals() -> void:
	var scene := load("res://scenes/maps/narrative_world.tscn") as PackedScene
	var map_root := scene.instantiate() as Node3D
	root.add_child(map_root)
	var visuals := RuntimeMapVisuals.build(map_root, "narrative_world")
	var town := visuals.get_node_or_null("AuthoredNarrativeTown")
	_expect(town is Node3D, "narrative world instantiates its authored seaside town")
	if town is Node3D:
		var town_meshes := town.find_children("*", "MeshInstance3D", true, false)
		_expect(
			town_meshes.size() >= 80,
			"authored narrative town retains detailed geometry after semantic batching",
		)
		_expect(
			town.find_child("TownGround", true, false) != null
			and town.find_child("TownRoads", true, false) != null
			and town.find_child("TrumanHomeText", true, false) != null
			and town.find_child("CornerCafeText", true, false) != null
			and town.find_child("BayHospitalText", true, false) != null
			and town.find_child("TownBackgroundBoundary", true, false) != null,
			"narrative town retains its seaside and story-specific landmarks",
		)
		_expect(
			town.find_child("ClockFace1", true, false) != null
			and town.find_child("TownRoadMarkings", true, false) != null
			and town.find_child("TownWindowDetails", true, false) != null
			and town.find_child("TownRoofDetails", true, false) != null
			and town.find_child("TownStreetFurniture", true, false) != null
			and town.find_child("TownPromenadeDetails", true, false) != null
			and town.find_child("TownWaterfrontDetails", true, false) != null
			and town.find_child("BacklotOcean", true, false) != null
			and town.find_child("SeahavenBeach", true, false) != null,
			"narrative town retains polished architectural and street details",
		)
		_expect(
			town.find_child("TrumanLivingSofaSeat", true, false) != null
			and town.find_child("TrumanKitchenCounter", true, false) != null
			and town.find_child("CornerCafeCounter", true, false) != null
			and town.find_child("CornerCafeWindowChair", true, false) != null,
			"key narrative locations expose readable cutaway interiors",
		)
		_expect(
			town.find_child("TrumanTelevision", true, false) != null
			and town.find_child("CornerCafeCoffeeMachine", true, false) != null
			and town.find_child("TownStreetMicroScenes", true, false) != null
			and town.find_child("StudioBoundaryServiceDoor", true, false) != null
			and town.find_child("BoundaryCamera1", true, false) != null,
			"narrative town includes domestic, civic and story micro-scenes",
		)
	_expect(
		visuals.get_node_or_null("EnvironmentAnimator") is AuthoredEnvironmentAnimator,
		"narrative town enables runtime environment motion",
	)
	_expect(
		visuals.find_children("NarrativeLampLight*", "OmniLight3D", true, false).size() == 20,
		"narrative town provides runtime-controlled street lights",
	)
	_expect(
		visuals.get_node_or_null("AuthoredCampusLandmarks") == null
		and visuals.get_node_or_null("AuthoredStudioCafe") == null,
		"narrative world never loads campus authored assets",
	)
	map_root.free()


func _test_mei_vector_avatar() -> void:
	var pose_ids := [
		"idle", "walk", "jog", "queue", "sit", "drink", "talk", "use_object",
		"wave", "think", "read", "phone", "carry", "celebrate", "surprised", "sleep",
	]
	for pose_id in pose_ids:
		var path := "res://assets/scenarios/campus_world/characters/mei/vector/%s.svg" % pose_id
		_expect(ResourceLoader.exists(path), "Mei %s SVG exists" % pose_id)
		_expect(load(path) is Texture2D, "Mei %s SVG imports as Texture2D" % pose_id)
	var avatar := AgentAvatar.new()
	avatar.agent_id = "run-1-mei"
	avatar.visual_asset_id = "campus_world/mei"
	avatar._build_visuals()
	_expect(avatar.get_node_or_null("VectorCharacter") is Sprite3D, "Mei uses SVG Sprite3D")
	var fallback := avatar.get_node_or_null("BodyRig") as Node3D
	_expect(fallback != null and not fallback.visible, "Mei hides procedural mesh fallback")
	for pose_id in pose_ids:
		_expect(avatar._vector_pose_for_state(pose_id) == pose_id, "Mei maps %s pose" % pose_id)
	avatar.free()


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


func _relative_transform(ancestor: Node3D, node: Node3D) -> Transform3D:
	var result := Transform3D.IDENTITY
	var current := node
	while current != ancestor:
		result = current.transform * result
		var parent := current.get_parent()
		if not parent is Node3D:
			break
		current = parent as Node3D
	return result
