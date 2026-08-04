class_name RuntimeMapVisuals
extends RefCounted

const COLOR_ROAD := Color("b8b5a8")
const COLOR_ROAD_EDGE := Color("d8d2c2")
const COLOR_QUAD := Color("9aaa83")
const COLOR_CAFE := Color("c78662")
const COLOR_LIBRARY := Color("8299a5")
const COLOR_DORM := Color("b29b7c")
const COLOR_LECTURE := Color("8f9b82")
const COLOR_ROOF := Color("475a63")
const COLOR_WINDOW := Color("e8c77e")
const STUDIO_CAFE_ASSET_PATH := (
	"res://assets/scenarios/campus_world/locations/studio_cafe/studio_cafe.glb"
)
const CAMPUS_LANDMARKS_ASSET_PATH := (
	"res://assets/scenarios/campus_world/environment/campus_landmarks.glb"
)
const NARRATIVE_TOWN_ASSET_PATH := (
	"res://assets/scenarios/narrative_world/environment/seaside_town.glb"
)


static func build(map_root: Node3D, scenario_id := "campus_world") -> Node3D:
	var visuals := Node3D.new()
	visuals.name = "RuntimeVisuals"
	map_root.add_child(visuals)
	visuals.set_meta("scenario_id", scenario_id)
	visuals.set_meta(
		"has_authored_narrative_town",
		scenario_id == "narrative_world" and _add_authored_narrative_town(visuals),
	)
	if not visuals.get_meta("has_authored_narrative_town", false):
		_build_roads(map_root, visuals)
	visuals.set_meta(
		"has_authored_campus_landmarks",
		scenario_id == "campus_world" and _add_authored_campus_landmarks(visuals),
	)
	for node: Node in _descendants(map_root):
		if node is WorldLocation3D:
			_build_location(map_root, visuals, node as WorldLocation3D)
		elif node is Interactable3D:
			_build_interactable(map_root, visuals, node as Interactable3D)
	if (
		not visuals.get_meta("has_authored_campus_landmarks", false)
		and not visuals.get_meta("has_authored_narrative_town", false)
	):
		_build_ambient_details(visuals)
	return visuals


static func _build_roads(map_root: Node3D, visuals: Node3D) -> void:
	var route_positions: Dictionary = {}
	var edges: Array[RouteEdge3D] = []
	for node: Node in _descendants(map_root):
		if node is RouteNode3D:
			var route_node := node as RouteNode3D
			route_positions[route_node.stable_id] = _local_position(map_root, route_node)
		elif node is RouteEdge3D:
			edges.append(node as RouteEdge3D)
	for edge: RouteEdge3D in edges:
		if not route_positions.has(edge.from_node_id) or not route_positions.has(edge.to_node_id):
			continue
		var start := route_positions[edge.from_node_id] as Vector3
		var finish := route_positions[edge.to_node_id] as Vector3
		var delta := finish - start
		var length := Vector2(delta.x, delta.z).length()
		if length <= 0.01:
			continue
		_add_box(
			visuals,
			(start + finish) * 0.5 + Vector3(0.0, 0.035, 0.0),
			Vector3(length, 0.07, 0.42),
			COLOR_ROAD,
			-atan2(delta.z, delta.x),
		)
		_add_box(
			visuals,
			(start + finish) * 0.5 + Vector3(0.0, 0.012, 0.0),
			Vector3(length + 0.12, 0.025, 0.58),
			COLOR_ROAD_EDGE,
			-atan2(delta.z, delta.x),
		)


static func _build_location(
	map_root: Node3D,
	visuals: Node3D,
	location: WorldLocation3D,
) -> void:
	var center := _local_position(map_root, location)
	if (
		visuals.get_meta("has_authored_campus_landmarks", false)
		and location.location_type in ["quad", "dorm", "lecture_hall", "library"]
	):
		var label_height := 1.45 if location.location_type == "quad" else 3.05
		_add_location_label(
			visuals,
			center + Vector3(0.0, label_height, 0.0),
			location.display_name,
		)
		return
	if visuals.get_meta("has_authored_narrative_town", false):
		_add_location_label(
			visuals,
			center + Vector3(0.0, 4.15 if location.location_type == "plaza" else 3.8, 0.0),
			location.display_name,
		)
		return
	if location.location_type == "quad":
		_add_cylinder(visuals, center + Vector3(0.0, 0.025, 0.0), 1.65, 0.05, COLOR_QUAD)
		_add_cylinder(visuals, center + Vector3(0.0, 0.08, 0.0), 0.58, 0.14, Color("d3c7aa"))
		_add_bench(visuals, center + Vector3(-1.05, 0.0, 0.85), 0.2)
		_add_bench(visuals, center + Vector3(1.05, 0.0, -0.85), PI + 0.2)
		_add_location_label(visuals, center + Vector3(0.0, 0.4, -1.55), location.display_name)
		return
	if (
		visuals.get_meta("scenario_id", "") == "campus_world"
		and location.location_type == "cafe"
		and _add_authored_studio_cafe(visuals, center)
	):
		_add_location_label(visuals, center + Vector3(0.0, 3.05, 0.0), location.display_name)
		return
	_add_cylinder(visuals, center + Vector3(0.0, 0.025, 0.0), 1.65, 0.05, COLOR_QUAD)

	var size := Vector3(2.8, 1.65, 2.2)
	var wall_color := COLOR_DORM
	match location.location_type:
		"cafe":
			size = Vector3(3.0, 1.45, 2.35)
			wall_color = COLOR_CAFE
		"library":
			size = Vector3(3.2, 1.8, 2.45)
			wall_color = COLOR_LIBRARY
		"lecture_hall":
			size = Vector3(3.45, 1.95, 2.65)
			wall_color = COLOR_LECTURE
		"dorm":
			size = Vector3(3.05, 1.7, 2.35)
			wall_color = COLOR_DORM
		"home":
			size = Vector3(3.2, 1.75, 2.5)
			wall_color = COLOR_DORM
		"office":
			size = Vector3(3.6, 2.1, 2.7)
			wall_color = COLOR_LIBRARY
		"hospital":
			size = Vector3(4.2, 2.25, 2.9)
			wall_color = Color("d5d8cf")
		"shop":
			size = Vector3(4.5, 2.0, 3.0)
			wall_color = COLOR_CAFE
	# Keep authoritative indoor positions visible from the director camera. The low wall and
	# rear roof read as a building while behaving like a tabletop-game cutaway.
	var cutaway_wall_height := minf(size.y, 0.92)
	_add_box(
		visuals,
		center + Vector3(0.0, cutaway_wall_height * 0.5, 0.0),
		Vector3(size.x, cutaway_wall_height, size.z),
		wall_color,
	)
	_add_box(
		visuals,
		center + Vector3(0.0, size.y + 0.12, -size.z * 0.31),
		Vector3(size.x + 0.22, 0.24, size.z * 0.4),
		COLOR_ROOF,
	)
	_add_box(
		visuals,
		center + Vector3(0.0, 0.72, size.z * 0.51),
		Vector3(0.82, 0.52, 0.05),
		COLOR_WINDOW,
	)
	_add_box(
		visuals,
		center + Vector3(0.0, 0.02, size.z * 0.72),
		Vector3(1.3, 0.04, 0.72),
		Color("c9bea9"),
	)
	_add_box(
		visuals,
		center + Vector3(-size.x * 0.26, 0.48, size.z * 0.515),
		Vector3(0.46, 0.88, 0.07),
		Color("344851"),
	)
	_add_box(
		visuals,
		center + Vector3(size.x * 0.26, 0.82, size.z * 0.515),
		Vector3(0.62, 0.58, 0.06),
		COLOR_WINDOW,
	)
	_add_location_label(
		visuals,
		center + Vector3(0.0, size.y + 0.52, 0.0),
		location.display_name,
	)
	if location.location_type == "cafe":
		_add_box(
			visuals,
			center + Vector3(0.0, 1.18, size.z * 0.62),
			Vector3(size.x * 0.72, 0.12, 0.7),
			Color("8d4f3d"),
		)
		_add_cafe_table(visuals, center + Vector3(1.55, 0.0, 0.65))


static func _build_interactable(
	map_root: Node3D,
	visuals: Node3D,
	interactable: Interactable3D,
) -> void:
	if ResourceLoader.exists(STUDIO_CAFE_ASSET_PATH) and interactable.object_type in [
		"coffee_counter", "cafe_chair",
	]:
		return
	var center := _local_position(map_root, interactable)
	match interactable.object_type:
		"coffee_counter":
			_add_box(
				visuals,
				center + Vector3(0.0, 0.42, 0.0),
				Vector3(1.45, 0.84, 0.5),
				Color("6f5543"),
			)
		"cafe_chair":
			_add_cylinder(
				visuals,
				center + Vector3(0.0, 0.25, 0.0),
				0.25,
				0.5,
				Color("82664d"),
			)
			_add_box(
				visuals,
				center + Vector3(0.0, 0.52, 0.18),
				Vector3(0.5, 0.48, 0.1),
				Color("82664d"),
			)


static func _add_authored_studio_cafe(visuals: Node3D, center: Vector3) -> bool:
	if not ResourceLoader.exists(STUDIO_CAFE_ASSET_PATH):
		return false
	var packed_scene := load(STUDIO_CAFE_ASSET_PATH) as PackedScene
	if packed_scene == null:
		return false
	var instance := packed_scene.instantiate() as Node3D
	if instance == null:
		return false
	instance.name = "AuthoredStudioCafe"
	instance.position = center
	instance.scale = Vector3.ONE * 0.72
	visuals.add_child(instance)
	return true


static func _add_authored_campus_landmarks(visuals: Node3D) -> bool:
	if not ResourceLoader.exists(CAMPUS_LANDMARKS_ASSET_PATH):
		return false
	var packed_scene := load(CAMPUS_LANDMARKS_ASSET_PATH) as PackedScene
	if packed_scene == null:
		return false
	var instance := packed_scene.instantiate() as Node3D
	if instance == null:
		return false
	instance.name = "AuthoredCampusLandmarks"
	visuals.add_child(instance)
	return true


static func _add_authored_narrative_town(visuals: Node3D) -> bool:
	if not ResourceLoader.exists(NARRATIVE_TOWN_ASSET_PATH):
		return false
	var packed_scene := load(NARRATIVE_TOWN_ASSET_PATH) as PackedScene
	if packed_scene == null:
		return false
	var instance := packed_scene.instantiate() as Node3D
	if instance == null:
		return false
	instance.name = "AuthoredNarrativeTown"
	visuals.add_child(instance)
	return true


static func _build_ambient_details(visuals: Node3D) -> void:
	var tree_positions := [
		Vector3(-9.2, 0.0, -4.7),
		Vector3(-8.8, 0.0, 2.8),
		Vector3(-5.5, 0.0, 3.9),
		Vector3(-1.0, 0.0, 3.7),
		Vector3(3.0, 0.0, 3.5),
		Vector3(8.1, 0.0, 2.8),
		Vector3(8.6, 0.0, -3.8),
		Vector3(5.7, 0.0, -5.2),
		Vector3(0.5, 0.0, -5.3),
		Vector3(-4.8, 0.0, -5.1),
	]
	for tree_position: Vector3 in tree_positions:
		_add_tree(visuals, tree_position)
	for lamp_position: Vector3 in [
		Vector3(-5.2, 0.0, -1.0),
		Vector3(-0.7, 0.0, -1.0),
		Vector3(3.8, 0.0, -1.0),
		Vector3(1.0, 0.0, 1.2),
	]:
		_add_lamp(visuals, lamp_position)


static func _add_tree(parent: Node3D, position: Vector3) -> void:
	_add_cylinder(parent, position + Vector3(0.0, 0.65, 0.0), 0.13, 1.3, Color("5f4934"))
	_add_cylinder(parent, position + Vector3(0.0, 1.62, 0.0), 0.62, 1.25, Color("4e7257"))
	_add_cylinder(parent, position + Vector3(0.0, 2.2, 0.0), 0.38, 0.72, Color("648567"))


static func _add_lamp(parent: Node3D, position: Vector3) -> void:
	_add_cylinder(parent, position + Vector3(0.0, 0.8, 0.0), 0.045, 1.6, Color("36434a"))
	_add_cylinder(parent, position + Vector3(0.0, 1.62, 0.0), 0.13, 0.18, Color("f4d789"))
	var light := OmniLight3D.new()
	light.position = position + Vector3(0.0, 1.62, 0.0)
	light.light_color = Color("ffd995")
	light.omni_range = 4.2
	light.light_energy = 0.0
	light.shadow_enabled = false
	light.add_to_group("night_light")
	parent.add_child(light)


static func _add_bench(parent: Node3D, position: Vector3, rotation_y: float) -> void:
	_add_box(parent, position + Vector3(0.0, 0.38, 0.0), Vector3(1.15, 0.12, 0.4), Color("806348"), rotation_y)
	_add_box(parent, position + Vector3(0.0, 0.66, 0.16), Vector3(1.15, 0.5, 0.1), Color("806348"), rotation_y)


static func _add_cafe_table(parent: Node3D, position: Vector3) -> void:
	_add_cylinder(parent, position + Vector3(0.0, 0.35, 0.0), 0.08, 0.7, Color("655044"))
	_add_cylinder(parent, position + Vector3(0.0, 0.73, 0.0), 0.55, 0.08, Color("9b785c"))


static func _add_location_label(parent: Node3D, position: Vector3, text: String) -> void:
	var label := Label3D.new()
	label.position = position
	label.text = text
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.fixed_size = false
	label.pixel_size = 0.008
	label.font_size = 20
	label.outline_size = 5
	label.modulate = Color("e9f0ec")
	label.outline_modulate = Color(0.03, 0.05, 0.07, 0.92)
	parent.add_child(label)


static func _add_box(
	parent: Node3D,
	position: Vector3,
	size: Vector3,
	color: Color,
	rotation_y := 0.0,
) -> void:
	var instance := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	instance.mesh = mesh
	instance.position = position
	instance.rotation.y = rotation_y
	instance.material_override = _material(color)
	instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	parent.add_child(instance)


static func _add_cylinder(
	parent: Node3D,
	position: Vector3,
	radius: float,
	height: float,
	color: Color,
) -> void:
	var instance := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height
	mesh.radial_segments = 24
	instance.mesh = mesh
	instance.position = position
	instance.material_override = _material(color)
	instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	parent.add_child(instance)


static func _material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.88
	return material


static func _descendants(root: Node) -> Array[Node]:
	var result: Array[Node] = []
	var pending: Array[Node] = []
	pending.assign(root.get_children())
	while not pending.is_empty():
		var node: Node = pending.pop_front()
		result.append(node)
		pending.append_array(node.get_children())
	return result


static func _local_position(root: Node3D, node: Node3D) -> Vector3:
	var transform := Transform3D.IDENTITY
	var current: Node3D = node
	while current != root:
		transform = current.transform * transform
		var parent := current.get_parent()
		if not parent is Node3D:
			break
		current = parent as Node3D
	return transform.origin
