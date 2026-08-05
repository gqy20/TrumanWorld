class_name RouteProjection
extends RefCounted

const CORNER_RADIUS := 0.28
const CORNER_SUBDIVISIONS := 6
const DEFAULT_TANGENT := Vector3(0.0, 0.0, 1.0)


static func route_positions(document: Dictionary) -> Dictionary:
	var positions := {}
	for raw_node: Variant in document.get("route_nodes", []):
		if not raw_node is Dictionary:
			continue
		var node := raw_node as Dictionary
		var point: Variant = _vector_from_array(node.get("position", []))
		if point != null:
			positions[str(node.get("id", ""))] = point
	return positions


static func build_path(movement: Dictionary, node_positions: Dictionary) -> Dictionary:
	var points := _route_points(movement.get("route_node_ids", []), node_positions)
	points = _round_corners(points)
	var cumulative_lengths: Array[float] = [0.0]
	for index in range(1, points.size()):
		cumulative_lengths.append(
			cumulative_lengths[-1] + points[index - 1].distance_to(points[index])
		)
	return {
		"points": points,
		"cumulative_lengths": cumulative_lengths,
		"total_length": cumulative_lengths[-1] if not cumulative_lengths.is_empty() else 0.0,
	}


static func sample(
	movement: Dictionary,
	node_positions: Dictionary,
	world_time_seconds: float,
	fallback: Vector3,
) -> Vector3:
	var path := build_path(movement, node_positions)
	if (path.get("points", []) as Array).is_empty():
		return fallback
	var progress := movement_progress(movement, world_time_seconds)
	return (sample_path(path, progress).get("position", fallback) as Vector3)


static func sample_path(path: Dictionary, progress: float) -> Dictionary:
	var total_length := float(path.get("total_length", 0.0))
	return sample_path_distance(path, clampf(progress, 0.0, 1.0) * total_length)


static func offset_sample(
	sample: Dictionary, lane_offset: float, longitudinal_offset: float = 0.0
) -> Dictionary:
	var distance := float(sample.get("distance", 0.0))
	var total_length := float(sample.get("total_length", 0.0))
	var tangent := sample.get("tangent", DEFAULT_TANGENT) as Vector3
	var right := Vector3(tangent.z, 0.0, -tangent.x)
	var result := sample.duplicate()
	result["position"] = (
		(sample.get("position", Vector3.ZERO) as Vector3)
		+ right * lane_offset * endpoint_blend(distance, total_length, 0.65)
		- tangent * longitudinal_offset * endpoint_blend(distance, total_length, 1.15)
	)
	return result


static func sample_path_distance(path: Dictionary, requested_distance: float) -> Dictionary:
	var points := path.get("points", []) as Array
	var lengths := path.get("cumulative_lengths", []) as Array
	var total_length := float(path.get("total_length", 0.0))
	if points.is_empty():
		return _sample_result(Vector3.ZERO, DEFAULT_TANGENT, 0.0, 0.0)
	if points.size() == 1 or total_length <= 0.0001:
		return _sample_result(points[0] as Vector3, DEFAULT_TANGENT, 0.0, total_length)
	var distance := clampf(requested_distance, 0.0, total_length)
	var segment := _find_segment(lengths, distance)
	var start := points[segment] as Vector3
	var finish := points[segment + 1] as Vector3
	var segment_start := float(lengths[segment])
	var segment_length := float(lengths[segment + 1]) - segment_start
	var ratio := (distance - segment_start) / maxf(segment_length, 0.0001)
	return _sample_result(start.lerp(finish, ratio), start.direction_to(finish), distance, total_length)


static func movement_progress(movement: Dictionary, world_time_seconds: float) -> float:
	if movement.get("state") == "paused":
		var paused_progress: Variant = movement.get(
			"paused_progress", movement.get("progress", 0.0)
		)
		return clampf(float(paused_progress), 0.0, 1.0)
	var started := _unix_time(str(movement.get("started_at_world_time", "")))
	var arrival := _unix_time(str(movement.get("expected_arrival_world_time", "")))
	if started > 0.0 and arrival > started:
		return clampf((world_time_seconds - started) / (arrival - started), 0.0, 1.0)
	return clampf(float(movement.get("progress", 0.0)), 0.0, 1.0)


static func endpoint_blend(
	distance: float, total_length: float, maximum_fade_distance: float = 0.65
) -> float:
	var fade_distance := minf(maximum_fade_distance, total_length * 0.22)
	if fade_distance <= 0.0001:
		return 0.0
	var endpoint_distance := minf(distance, total_length - distance)
	var progress := clampf(endpoint_distance / fade_distance, 0.0, 1.0)
	return smoothstep(0.0, 1.0, progress)


static func _round_corners(points: Array[Vector3]) -> Array[Vector3]:
	if points.size() < 3:
		return points
	var rounded: Array[Vector3] = [points[0]]
	for index in range(1, points.size() - 1):
		_append_rounded_corner(rounded, points[index - 1], points[index], points[index + 1])
	rounded.append(points[-1])
	return _deduplicate_points(rounded)


static func _append_rounded_corner(
	result: Array[Vector3], previous: Vector3, corner: Vector3, next: Vector3
) -> void:
	var incoming := previous.direction_to(corner)
	var outgoing := corner.direction_to(next)
	if absf(incoming.dot(outgoing)) > 0.999:
		result.append(corner)
		return
	var radius := minf(
		CORNER_RADIUS,
		minf(previous.distance_to(corner) * 0.3, corner.distance_to(next) * 0.3),
	)
	var entry := corner - incoming * radius
	var exit := corner + outgoing * radius
	result.append(entry)
	for step in range(1, CORNER_SUBDIVISIONS + 1):
		result.append(_quadratic_bezier(entry, corner, exit, float(step) / CORNER_SUBDIVISIONS))


static func _quadratic_bezier(
	start: Vector3, control: Vector3, finish: Vector3, progress: float
) -> Vector3:
	var inverse := 1.0 - progress
	return (
		start * inverse * inverse
		+ control * 2.0 * inverse * progress
		+ finish * progress * progress
	)


static func _deduplicate_points(points: Array[Vector3]) -> Array[Vector3]:
	var result: Array[Vector3] = []
	for point in points:
		if result.is_empty() or result[-1].distance_squared_to(point) > 0.000001:
			result.append(point)
	return result


static func _route_points(raw_node_ids: Variant, node_positions: Dictionary) -> Array[Vector3]:
	var points: Array[Vector3] = []
	if not raw_node_ids is Array:
		return points
	for raw_node_id: Variant in raw_node_ids:
		var node_id := str(raw_node_id)
		if not node_positions.has(node_id):
			return []
		points.append(node_positions[node_id] as Vector3)
	return points


static func _find_segment(lengths: Array, distance: float) -> int:
	for index in range(lengths.size() - 1):
		if distance <= float(lengths[index + 1]):
			return index
	return maxi(0, lengths.size() - 2)


static func _sample_result(
	position: Vector3, tangent: Vector3, distance: float, total_length: float
) -> Dictionary:
	return {
		"position": position,
		"tangent": tangent,
		"distance": distance,
		"total_length": total_length,
	}


static func _unix_time(value: String) -> float:
	if value.is_empty():
		return 0.0
	return float(Time.get_unix_time_from_datetime_string(value))


static func _vector_from_array(raw_value: Variant) -> Variant:
	if not raw_value is Array or raw_value.size() < 3:
		return null
	return Vector3(float(raw_value[0]), float(raw_value[1]), float(raw_value[2]))
