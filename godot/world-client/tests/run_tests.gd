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
	_test_director_camera_web_interactions()
	_test_route_projection()
	_test_idle_agent_placement()
	_test_agent_local_avoidance()
	_test_agent_movement_formation()
	_test_conversation_placement()
	_test_agent_selection_click_threshold()
	_test_activity_visual_mapping()
	_test_vector_animation_library()
	_test_truman_3d_character()
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
		var town_ground := town.find_child("TownGround", true, false) as MeshInstance3D
		var town_roads := town.find_child("TownRoads", true, false) as MeshInstance3D
		var studio_door := town.find_child(
			"StudioBoundaryServiceDoor", true, false
		) as Node3D
		_expect(
			town_ground != null
			and town_ground.mesh.get_aabb().size.x >= 179.0
			and town_ground.mesh.get_aabb().size.z >= 109.0
			and town_roads != null
			and town_roads.mesh.get_aabb().size.x >= 179.0
			and town.find_child("TownBufferBuildings", true, false) != null
			and studio_door != null
			and absf(studio_door.position.z) >= 240.0,
			"narrative town separates semantic core, visual buffer and hidden boundary",
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
	var manifest_path := "res://assets/scenarios/campus_world/characters/mei/vector/manifest.json"
	var raw_manifest: Variant = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
	_expect(raw_manifest is Dictionary, "Mei vector manifest is valid JSON")
	var manifest := raw_manifest as Dictionary
	for animation_id: String in ["idle", "walk", "jog"]:
		for frame_path: String in manifest["animations"][animation_id]["frames"]:
			var path := (
				"res://assets/scenarios/campus_world/characters/mei/vector/%s" % frame_path
			)
			_expect(ResourceLoader.exists(path), "Mei %s animation frame exists" % animation_id)
			_expect(load(path) is Texture2D, "Mei %s frame imports as Texture2D" % animation_id)
	var avatar := AgentAvatar.new()
	avatar.agent_id = "run-1-mei"
	avatar.visual_asset_id = "campus_world/mei"
	avatar._build_visuals()
	_expect(avatar.get_node_or_null("VectorCharacter") is Sprite3D, "Mei uses SVG Sprite3D")
	var fallback := avatar.get_node_or_null("BodyRig") as Node3D
	_expect(fallback != null and not fallback.visible, "Mei hides procedural mesh fallback")
	for pose_id in pose_ids:
		_expect(avatar._vector_pose_for_state(pose_id) == pose_id, "Mei maps %s pose" % pose_id)
	_expect(avatar._vector_animations.size() == 3, "Mei loads three multi-frame animations")
	avatar.free()


func _test_truman_3d_character() -> void:
	var resident_ids := ["alice", "bob", "friend", "neighbor", "spouse", "truman"]
	for resident_id in resident_ids:
		var resident_path := (
			"res://assets/scenarios/narrative_world/characters/%s/model/character.glb"
			% resident_id
		)
		_expect(ResourceLoader.exists(resident_path), "%s rigged GLB exists" % resident_id)
		_expect(load(resident_path) is PackedScene, "%s GLB imports as a scene" % resident_id)
		var resident_model := AgentModel3D.instantiate_asset("narrative_world/%s" % resident_id)
		_expect(
			resident_model != null and resident_model.is_ready(),
			"%s model satisfies the shared runtime contract" % resident_id,
		)
		if resident_model != null:
			resident_model.free()
	var model := AgentModel3D.instantiate_asset("narrative_world/truman")
	_expect(model != null and model.is_ready(), "Truman 3D model exposes an AnimationPlayer")
	if model == null:
		return
	var animations := model.animation_names()
	var expected_animations := [
		"idle", "walk", "jog", "turn_left", "turn_right", "sit", "drink", "queue",
		"talk", "use_object", "wave", "think", "read", "phone", "carry", "celebrate",
		"surprised", "sleep",
	]
	for animation_id in expected_animations:
		_expect(
			animation_id in animations,
			"Truman GLB contains %s animation" % animation_id,
		)
	_expect(
		model.find_children("*", "Skeleton3D", true, false).size() == 1,
		"Truman GLB contains one reusable humanoid skeleton",
	)
	var cup := model.find_child("CoffeeCup", true, false) as MeshInstance3D
	_expect(cup != null and not cup.visible, "3D coffee cup starts hidden")
	model.update_pose("drink", 1.0, 0.0, 0.0)
	_expect(cup != null and cup.visible, "drink state reveals the rigged coffee cup")
	model.update_pose("wave", 100.0, 0.0, 0.0)
	_expect(model._active_animation == "wave", "semantic wave state selects its native 3D action")
	_expect(
		is_zero_approx(model._animation_player.current_animation_position),
		"a newly entered semantic action starts at its first frame",
	)
	model.update_pose("wave", 100.4, 0.0, 0.0)
	_expect(
		model._animation_player.current_animation_position > 0.3,
		"semantic action time advances from state entry",
	)
	_expect(cup != null and not cup.visible, "leaving drink hides every coffee-cup part")
	model.update_pose("celebrate", 200.0, 0.0, 0.0)
	model.update_pose("celebrate", 200.2, 0.0, 0.0)
	_expect(model._motion_offset.y > 0.07, "celebration adds a bounded presentation-only hop")
	model.update_pose("walk", 201.0, 0.26, 1.0)
	_expect(model._motion_offset.y > 0.02, "3D walking adds distance-synchronized body rise")
	_expect(
		model._state_offset("sit").is_equal_approx(Vector3(0.0, -0.32, 0.08)),
		"sit state applies its authored model-space seating offset",
	)
	model.free()
	var avatar := AgentAvatar.new()
	avatar.agent_id = "run-1-truman"
	avatar.visual_asset_id = "narrative_world/truman"
	avatar._build_visuals()
	_expect(avatar.get_node_or_null("CharacterModel") is AgentModel3D, "Truman prefers 3D")
	var vector := avatar.get_node_or_null("VectorCharacter") as Sprite3D
	_expect(vector != null and not vector.visible, "Truman hides SVG after 3D loads")
	avatar.free()


func _test_vector_animation_library() -> void:
	var time_animation := {"driver": "time", "fps": 2.0, "frames": [0, 1, 2, 3]}
	_expect(
		VectorAnimationLibrary.frame_index(time_animation, 1.1, 0.0) == 2,
		"time-driven animation interprets fps as frames per second",
	)
	_expect(
		VectorAnimationLibrary.frame_index(time_animation, 3.1, 0.0) == 2,
		"time-driven animation loops after its complete frame sequence",
	)
	var distance_animation := {
		"driver": "distance",
		"cycle_distance_m": 1.0,
		"frames": [0, 1, 2, 3],
	}
	_expect(
		VectorAnimationLibrary.frame_index(distance_animation, 99.0, 0.26) == 1,
		"distance-driven gait selects frames from travelled distance",
	)
	_expect(
		VectorAnimationLibrary.frame_index(distance_animation, 99.0, 1.26) == 1,
		"distance-driven gait loops at the configured stride length",
	)
	_expect(
		VectorAnimationLibrary.cycle_distance_m(
			{"walk": distance_animation}, "walk", 0.52
		) == 1.0,
		"pose bobbing uses the same distance cycle as its SVG frames",
	)
	_expect(
		VectorAnimationLibrary.cycle_distance_m({}, "walk", 0.52) == 0.52,
		"procedural residents keep their fallback gait cycle",
	)


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


func _test_director_camera_web_interactions() -> void:
	_expect(
		ProjectSettings.get_setting("display/window/stretch/mode") == "disabled",
		"web viewport is not constrained to a letterboxed design aspect",
	)
	var director := DirectorCamera.new()
	var camera := Camera3D.new()
	camera.name = "Camera3D"
	director.add_child(camera)
	root.add_child(director)
	director.camera = camera
	var yaw_before: float = director.get("_yaw")
	var press := InputEventMouseButton.new()
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = true
	director._input(press)
	var drag := InputEventMouseMotion.new()
	drag.relative = Vector2(80.0, 20.0)
	director._input(drag)
	_expect(director.get("_yaw") != yaw_before, "left mouse drag orbits the director camera")
	var release := InputEventMouseButton.new()
	release.button_index = MOUSE_BUTTON_LEFT
	release.pressed = false
	director._input(release)
	_expect(director.get("_drag_mode") == 0, "left mouse release stops camera dragging")
	var target_before: Vector3 = director.get("_desired_target")
	director._move_target(Vector2(0.0, 1.0), 1.0)
	_expect(
		director.get("_desired_target") != target_before,
		"keyboard movement advances the camera target along the ground",
	)
	_expect(not director.is_following_target(), "manual movement exits resident follow mode")
	director._move_target(Vector2(1.0, 0.0), 100.0, true)
	var bounded_target: Vector3 = director.get("_desired_target")
	var overview_target: Vector3 = director.get("_overview_target")
	_expect(
		bounded_target.x <= overview_target.x + 45.0,
		"free camera movement remains inside the authored visual buffer",
	)
	var focused_target := Vector3(4.0, 0.6, -3.0)
	director.focus_position(focused_target, false)
	_expect(director.is_following_target(), "focusing a resident enters follow mode")
	var home := InputEventKey.new()
	home.keycode = KEY_HOME
	home.pressed = true
	director._input(home)
	_expect(director.get("_desired_target") == overview_target, "Home restores the map overview")
	var refocus := InputEventKey.new()
	refocus.keycode = KEY_F
	refocus.pressed = true
	director._input(refocus)
	_expect(director.get("_desired_target") == focused_target, "F returns to the selected resident")
	var tap_forward := InputEventKey.new()
	tap_forward.physical_keycode = KEY_W
	tap_forward.pressed = true
	director._input(tap_forward)
	_expect(
		director.get("_desired_target") != focused_target,
		"a short WASD tap immediately moves the camera target",
	)
	director.free()


func _test_route_projection() -> void:
	var nodes := {
		"a": Vector3(0.0, 0.0, 0.0),
		"b": Vector3(4.0, 0.0, 0.0),
		"c": Vector3(4.0, 0.0, 6.0),
	}
	var movement := {
		"state": "in_transit",
		"route_node_ids": ["a", "b", "c"],
		"started_at_world_time": "2026-03-02T06:00:00Z",
		"expected_arrival_world_time": "2026-03-02T06:00:10Z",
	}
	var halfway_time := Time.get_unix_time_from_datetime_string("2026-03-02T06:00:05Z")
	var halfway := RouteProjection.sample(movement, nodes, halfway_time, Vector3.ZERO)
	_expect(
		halfway.distance_to(Vector3(4.0, 0.0, 1.0)) < 0.08,
		"route projection follows arc length across corners",
	)
	var path := RouteProjection.build_path(movement, nodes)
	_expect(
		(path.get("points", []) as Array).size() > 3,
		"route projection rounds authored street corners",
	)
	var corner_approach := RouteProjection.sample_path_distance(path, 3.9)
	var corner_exit := RouteProjection.sample_path_distance(path, 4.1)
	_expect(
		(corner_approach["tangent"] as Vector3).dot(corner_exit["tangent"] as Vector3) > 0.0,
		"rounded route changes direction without a right-angle snap",
	)
	_expect(
		RouteProjection.endpoint_blend(0.0, 10.0) == 0.0
		and RouteProjection.endpoint_blend(5.0, 10.0) == 1.0,
		"locomotion gait settles at route endpoints",
	)
	var lane_start := RouteProjection.offset_sample(RouteProjection.sample_path(path, 0.0), 0.14)
	var lane_middle := RouteProjection.offset_sample(RouteProjection.sample_path(path, 0.5), 0.14)
	_expect(lane_start["position"] == path["points"][0], "lane offset fades at an entrance")
	_expect(
		(lane_middle["position"] as Vector3).distance_to(halfway) > 0.1,
		"moving residents keep to one side of the road",
	)
	movement["state"] = "paused"
	movement["paused_progress"] = 0.25
	_expect(
		RouteProjection.sample(movement, nodes, halfway_time, Vector3.ZERO)
		.distance_to(Vector3(2.5, 0.0, 0.0)) < 0.08,
		"paused movement stays at its authoritative progress",
	)


func _test_agent_selection_click_threshold() -> void:
	var avatar := AgentAvatar.new()
	avatar.agent_id = "mei"
	var selected_ids: Array[String] = []
	avatar.selected.connect(func(agent_id: String) -> void: selected_ids.append(agent_id))
	var press := InputEventMouseButton.new()
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = true
	press.position = Vector2(10.0, 10.0)
	avatar._on_input_event(null, press, Vector3.ZERO, Vector3.UP, 0)
	var drag := InputEventMouseMotion.new()
	drag.position = Vector2(30.0, 10.0)
	avatar._on_input_event(null, drag, Vector3.ZERO, Vector3.UP, 0)
	var release := InputEventMouseButton.new()
	release.button_index = MOUSE_BUTTON_LEFT
	release.pressed = false
	release.position = drag.position
	avatar._on_input_event(null, release, Vector3.ZERO, Vector3.UP, 0)
	_expect(selected_ids.is_empty(), "dragging from a resident does not select it")
	avatar._on_input_event(null, press, Vector3.ZERO, Vector3.UP, 0)
	release.position = press.position
	avatar._on_input_event(null, release, Vector3.ZERO, Vector3.UP, 0)
	_expect(selected_ids == ["mei"], "a resident is selected after a completed click")
	avatar.free()


func _test_idle_agent_placement() -> void:
	var offsets := AgentPlacement.radial_offsets(["mei", "chen", "lin"])
	_expect(offsets.size() == 3, "idle placement gives every resident a stable offset")
	_expect(
		(offsets["mei"] as Vector3).distance_to(offsets["chen"] as Vector3) >= 0.57,
		"idle placement keeps residents out of the same standing point",
	)
	_expect(
		offsets == AgentPlacement.radial_offsets(["lin", "mei", "chen"]),
		"idle placement is deterministic regardless of snapshot order",
	)


func _test_agent_local_avoidance() -> void:
	var positions := {
		"mei": Vector3.ZERO,
		"chen": Vector3.ZERO,
		"lin": Vector3(4.0, 0.0, 0.0),
	}
	var offsets := AgentPlacement.avoidance_offsets(positions)
	_expect(
		(offsets["mei"] as Vector3).dot(offsets["chen"] as Vector3) < 0.0,
		"coincident residents receive opposite avoidance offsets",
	)
	_expect(
		(offsets["mei"] as Vector3).length() <= 0.121
		and (offsets["chen"] as Vector3).length() <= 0.121,
		"local avoidance remains visually bounded",
	)
	_expect(offsets["lin"] == Vector3.ZERO, "distant residents are not displaced")


func _test_agent_movement_formation() -> void:
	var formation := AgentPlacement.movement_formation(["charlie", "alpha", "bravo"])
	_expect(
		formation["alpha"]["lane_offset"] == 0.0
		and formation["bravo"]["lane_offset"] == 0.18,
		"same-route residents form a stable walking row",
	)
	_expect(
		formation["charlie"]["lane_offset"] == 0.09
		and formation["charlie"]["longitudinal_offset"] == 0.42,
		"an unpaired resident follows behind the first row",
	)


func _test_conversation_placement() -> void:
	var offsets := AgentPlacement.conversation_pair_offsets(
		"mei", Vector3.ZERO, "chen", Vector3(2.0, 0.0, 0.0)
	)
	var final_mei := offsets["mei"] as Vector3
	var final_chen := Vector3(2.0, 0.0, 0.0) + (offsets["chen"] as Vector3)
	_expect(
		absf(final_mei.distance_to(final_chen) - 1.15) < 0.001,
		"free-standing conversation partners approach a natural speaking distance",
	)
	var coincident := AgentPlacement.conversation_pair_offsets(
		"mei", Vector3.ZERO, "chen", Vector3.ZERO
	)
	_expect(
		(coincident["mei"] as Vector3).dot(coincident["chen"] as Vector3) < 0.0,
		"coincident conversation partners separate deterministically",
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
