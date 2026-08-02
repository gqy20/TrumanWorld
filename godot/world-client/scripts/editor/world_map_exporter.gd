class_name WorldMapExporter
extends RefCounted

const SCHEMA_VERSION := 1


func build_document(scene_root: Node, map_id: String, meters_per_unit: float = 1.0) -> Dictionary:
	var collections := {
		"districts": [],
		"locations": [],
		"zones": [],
		"portals": [],
		"route_nodes": [],
		"route_edges": [],
		"interactables": [],
		"interaction_slots": [],
		"spawn_anchors": [],
		"camera_anchors": [],
	}
	_collect_nodes(scene_root, collections)
	for collection: Variant in collections.values():
		(collection as Array).sort_custom(_sort_by_id)

	var errors := _validate(collections)
	if not errors.is_empty():
		return {"ok": false, "errors": errors}

	var route_positions := {}
	for route_node: Dictionary in collections["route_nodes"]:
		route_positions[route_node["id"]] = _array_to_vector(route_node["position"])
	for edge: Dictionary in collections["route_edges"]:
		if float(edge["distance_meters"]) <= 0.0:
			edge["distance_meters"] = _rounded(
				route_positions[edge["from_node_id"]].distance_to(
					route_positions[edge["to_node_id"]],
				) * meters_per_unit
			)

	var document := {
		"schema_version": SCHEMA_VERSION,
		"map_id": map_id,
		"meters_per_unit": meters_per_unit,
		"districts": collections["districts"],
		"locations": collections["locations"],
		"zones": collections["zones"],
		"portals": collections["portals"],
		"route_nodes": collections["route_nodes"],
		"route_edges": collections["route_edges"],
		"interactables": collections["interactables"],
		"interaction_slots": collections["interaction_slots"],
		"spawn_anchors": collections["spawn_anchors"],
		"camera_anchors": collections["camera_anchors"],
	}
	var canonical := JSON.stringify(document, "", true, true)
	document["content_hash"] = "sha256:%s" % _sha256(canonical)
	return {"ok": true, "document": document}


func write_document(document: Dictionary, output_path: String) -> Error:
	var absolute_path := ProjectSettings.globalize_path(output_path)
	var directory_error := DirAccess.make_dir_recursive_absolute(absolute_path.get_base_dir())
	if directory_error != OK:
		return directory_error
	var file := FileAccess.open(absolute_path, FileAccess.WRITE)
	if file == null:
		return FileAccess.get_open_error()
	file.store_string(JSON.stringify(document, "  ", true, true) + "\n")
	return OK


func _collect_nodes(node: Node, collections: Dictionary) -> void:
	if node is WorldDistrict3D:
		collections["districts"].append({
			"id": node.stable_id,
			"name": node.display_name,
			"position": _vector(_world_transform(node).origin),
			"size_meters": _vector(node.size_meters),
		})
	elif node is WorldLocation3D:
		collections["locations"].append({
			"id": node.stable_id,
			"name": node.display_name,
			"type": node.location_type,
			"position": _vector(_world_transform(node).origin),
			"capacity": node.capacity,
			"public_access": node.public_access,
			"entrance_node_id": node.entrance_node_id,
		})
	elif node is WorldZone3D:
		collections["zones"].append({
			"id": node.stable_id,
			"location_id": node.location_id,
			"type": node.zone_type,
			"position": _vector(_world_transform(node).origin),
			"size_meters": _vector(node.size_meters),
			"capacity": node.capacity,
		})
	elif node is WorldPortal3D:
		collections["portals"].append({
			"id": node.stable_id,
			"from_zone_id": node.from_zone_id,
			"to_zone_id": node.to_zone_id,
			"position": _vector(_world_transform(node).origin),
			"is_open": node.is_open,
		})
	elif node is RouteNode3D:
		collections["route_nodes"].append({
			"id": node.stable_id,
			"kind": node.node_kind,
			"position": _vector(_world_transform(node).origin),
		})
	elif node is RouteEdge3D:
		collections["route_edges"].append({
			"id": node.stable_id,
			"from_node_id": node.from_node_id,
			"to_node_id": node.to_node_id,
			"distance_meters": node.distance_override_meters,
			"bidirectional": node.bidirectional,
		})
	elif node is Interactable3D:
		collections["interactables"].append({
			"id": node.stable_id,
			"type": node.object_type,
			"location_id": node.location_id,
			"zone_id": node.zone_id,
			"position": _vector(_world_transform(node).origin),
			"rotation_y_degrees": _rotation_y_degrees(node),
			"slot_ids": [],
		})
	elif node is InteractionSlot3D:
		collections["interaction_slots"].append({
			"id": node.stable_id,
			"object_id": node.object_id,
			"kind": node.slot_kind,
			"position": _vector(_world_transform(node).origin),
			"rotation_y_degrees": _rotation_y_degrees(node),
			"capacity": node.capacity,
		})
	elif node is SpawnAnchor3D:
		collections["spawn_anchors"].append({
			"id": node.stable_id,
			"zone_id": node.zone_id,
			"kind": node.anchor_kind,
			"position": _vector(_world_transform(node).origin),
			"rotation_y_degrees": _rotation_y_degrees(node),
		})
	elif node is CameraAnchor3D:
		collections["camera_anchors"].append({
			"id": node.stable_id,
			"target_id": node.target_id,
			"position": _vector(_world_transform(node).origin),
			"look_at_position": _vector(node.look_at_position),
		})

	for child: Node in node.get_children():
		_collect_nodes(child, collections)


func _validate(collections: Dictionary) -> PackedStringArray:
	var errors := PackedStringArray()
	var all_ids := {}
	for collection_name: String in collections:
		for item: Dictionary in collections[collection_name]:
			var item_id := str(item.get("id", ""))
			if item_id.is_empty():
				errors.append("%s contains an empty stable ID" % collection_name)
			elif all_ids.has(item_id):
				errors.append("duplicate stable ID: %s" % item_id)
			else:
				all_ids[item_id] = collection_name

	var location_ids := _id_set(collections["locations"])
	var zone_ids := _id_set(collections["zones"])
	var route_node_ids := _id_set(collections["route_nodes"])
	var object_ids := _id_set(collections["interactables"])

	for location: Dictionary in collections["locations"]:
		if not route_node_ids.has(location["entrance_node_id"]):
			errors.append("location %s has an invalid entrance node" % location["id"])
	for zone: Dictionary in collections["zones"]:
		if not location_ids.has(zone["location_id"]):
			errors.append("zone %s has an invalid location" % zone["id"])
	for portal: Dictionary in collections["portals"]:
		if not zone_ids.has(portal["from_zone_id"]) or not zone_ids.has(portal["to_zone_id"]):
			errors.append("portal %s has an invalid zone" % portal["id"])
	for edge: Dictionary in collections["route_edges"]:
		if not route_node_ids.has(edge["from_node_id"]) or not route_node_ids.has(edge["to_node_id"]):
			errors.append("route edge %s has an invalid node" % edge["id"])
		elif edge["from_node_id"] == edge["to_node_id"]:
			errors.append("route edge %s cannot connect a node to itself" % edge["id"])
	for object: Dictionary in collections["interactables"]:
		if not location_ids.has(object["location_id"]) or not zone_ids.has(object["zone_id"]):
			errors.append("interactable %s has an invalid location or zone" % object["id"])
		else:
			for zone: Dictionary in collections["zones"]:
				if zone["id"] == object["zone_id"] and zone["location_id"] != object["location_id"]:
					errors.append("interactable %s crosses location boundaries" % object["id"])
					break
	for slot: Dictionary in collections["interaction_slots"]:
		if not object_ids.has(slot["object_id"]):
			errors.append("interaction slot %s has an invalid object" % slot["id"])
		else:
			for object: Dictionary in collections["interactables"]:
				if object["id"] == slot["object_id"]:
					object["slot_ids"].append(slot["id"])
					object["slot_ids"].sort()
					break
	for anchor: Dictionary in collections["spawn_anchors"]:
		if not zone_ids.has(anchor["zone_id"]):
			errors.append("spawn anchor %s has an invalid zone" % anchor["id"])
	for anchor: Dictionary in collections["camera_anchors"]:
		if not all_ids.has(anchor["target_id"]):
			errors.append("camera anchor %s has an invalid target" % anchor["id"])
	if errors.is_empty():
		errors.append_array(_validate_route_connectivity(collections))
	return errors


func _validate_route_connectivity(collections: Dictionary) -> PackedStringArray:
	var entrances := {}
	for location: Dictionary in collections["locations"]:
		entrances[location["entrance_node_id"]] = true
	if entrances.size() <= 1:
		return PackedStringArray()
	var neighbors := {}
	for route_node: Dictionary in collections["route_nodes"]:
		neighbors[route_node["id"]] = []
	for edge: Dictionary in collections["route_edges"]:
		neighbors[edge["from_node_id"]].append(edge["to_node_id"])
		if edge["bidirectional"]:
			neighbors[edge["to_node_id"]].append(edge["from_node_id"])
	var pending: Array = [entrances.keys().min()]
	var visited := {pending[0]: true}
	while not pending.is_empty():
		var current: String = pending.pop_front()
		for neighbor: String in neighbors[current]:
			if not visited.has(neighbor):
				visited[neighbor] = true
				pending.append(neighbor)
	var missing := entrances.keys().filter(func(id: String) -> bool: return not visited.has(id))
	if missing.is_empty():
		return PackedStringArray()
	missing.sort()
	return PackedStringArray(["location entrances are disconnected: %s" % ", ".join(missing)])


func _id_set(items: Array) -> Dictionary:
	var result := {}
	for item: Dictionary in items:
		result[item["id"]] = true
	return result


func _vector(value: Vector3) -> Array[float]:
	return [_rounded(value.x), _rounded(value.y), _rounded(value.z)]


func _array_to_vector(value: Array) -> Vector3:
	return Vector3(float(value[0]), float(value[1]), float(value[2]))


func _world_transform(node: Node3D) -> Transform3D:
	var result := node.transform
	var parent := node.get_parent()
	while parent is Node3D:
		result = (parent as Node3D).transform * result
		parent = parent.get_parent()
	return result


func _rotation_y_degrees(node: Node3D) -> float:
	return _rounded(rad_to_deg(_world_transform(node).basis.get_euler().y))


func _rounded(value: float) -> float:
	var snapped := snappedf(value, 0.0001)
	var nearest_integer := roundf(snapped)
	return nearest_integer if absf(snapped - nearest_integer) < 0.0002 else snapped


func _sha256(value: String) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(value.to_utf8_buffer())
	return context.finish().hex_encode()


func _sort_by_id(left: Dictionary, right: Dictionary) -> bool:
	return str(left.get("id", "")) < str(right.get("id", ""))
