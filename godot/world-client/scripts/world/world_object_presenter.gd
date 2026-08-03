class_name WorldObjectPresenter
extends RefCounted

const AVAILABLE := Color("5f7f73")
const OCCUPIED := Color("57d3a2")
const QUEUED := Color("e7ba68")

var _markers: Dictionary = {}


func configure(map_root: Node3D) -> void:
	var presentation_root := Node3D.new()
	presentation_root.name = "ObjectStatePresentation"
	map_root.add_child(presentation_root)
	for node: Node in _descendants(map_root):
		if not node is InteractionSlot3D:
			continue
		var slot := node as InteractionSlot3D
		var marker := MeshInstance3D.new()
		var mesh := TorusMesh.new()
		mesh.inner_radius = 0.2 if slot.slot_kind == "queue" else 0.28
		mesh.outer_radius = 0.26 if slot.slot_kind == "queue" else 0.35
		mesh.rings = 20
		mesh.ring_segments = 8
		marker.mesh = mesh
		marker.position = _local_position(map_root, slot) + Vector3(0.0, 0.04, 0.0)
		marker.material_override = _material(AVAILABLE, 0.42)
		presentation_root.add_child(marker)
		_markers[slot.stable_id] = marker


func apply_states(raw_states: Variant) -> void:
	for marker: MeshInstance3D in _markers.values():
		marker.material_override = _material(AVAILABLE, 0.42)
	if not raw_states is Array:
		return
	for raw_state: Variant in raw_states:
		if not raw_state is Dictionary:
			continue
		var state := raw_state as Dictionary
		var resource_id := str(state.get("resource_id", ""))
		if not _markers.has(resource_id):
			continue
		var occupants: Variant = state.get("occupant_agent_ids", [])
		var queue: Variant = state.get("queue_agent_ids", [])
		var color := AVAILABLE
		var alpha := 0.42
		if occupants is Array and not occupants.is_empty():
			color = OCCUPIED
			alpha = 0.92
		elif queue is Array and not queue.is_empty():
			color = QUEUED
			alpha = 0.88
		(_markers[resource_id] as MeshInstance3D).material_override = _material(color, alpha)


func _material(color: Color, alpha: float) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(color, alpha)
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.emission_enabled = true
	material.emission = color
	material.emission_energy_multiplier = 0.45
	material.roughness = 0.8
	return material


func _descendants(root: Node) -> Array[Node]:
	var result: Array[Node] = []
	var pending: Array[Node] = []
	pending.assign(root.get_children())
	while not pending.is_empty():
		var node: Node = pending.pop_front()
		result.append(node)
		pending.append_array(node.get_children())
	return result


func _local_position(root: Node3D, node: Node3D) -> Vector3:
	var transform := Transform3D.IDENTITY
	var current: Node3D = node
	while current != root:
		transform = current.transform * transform
		var parent := current.get_parent()
		if not parent is Node3D:
			break
		current = parent as Node3D
	return transform.origin
