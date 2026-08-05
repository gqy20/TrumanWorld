class_name AgentPlacement
extends RefCounted

const MIN_SPACING := 0.58
const MAX_PER_RING := 8
const PERSONAL_SPACE := 0.62
const MAX_AVOIDANCE_OFFSET := 0.12
const CONVERSATION_DISTANCE := 1.15
const MAX_CONVERSATION_SHIFT := 0.65


static func radial_offsets(agent_ids: Array[String]) -> Dictionary:
	var sorted_ids := agent_ids.duplicate()
	sorted_ids.sort()
	if sorted_ids.size() <= 1:
		return {sorted_ids[0]: Vector3.ZERO} if not sorted_ids.is_empty() else {}
	var offsets := {}
	var base_angle := _stable_angle(":".join(sorted_ids))
	for index in range(sorted_ids.size()):
		var ring := int(index / MAX_PER_RING)
		var ring_index := index % MAX_PER_RING
		var remaining := sorted_ids.size() - ring * MAX_PER_RING
		var ring_count := mini(MAX_PER_RING, remaining)
		var radius := _ring_radius(ring_count, ring)
		var angle := base_angle + TAU * float(ring_index) / float(ring_count)
		offsets[sorted_ids[index]] = Vector3(cos(angle) * radius, 0.0, sin(angle) * radius)
	return offsets


static func avoidance_offsets(position_by_agent_id: Dictionary) -> Dictionary:
	var agent_ids := position_by_agent_id.keys()
	agent_ids.sort()
	var offsets := {}
	for agent_id: Variant in agent_ids:
		offsets[agent_id] = Vector3.ZERO
	for left_index in range(agent_ids.size()):
		for right_index in range(left_index + 1, agent_ids.size()):
			_apply_pair_avoidance(
				offsets,
				position_by_agent_id,
				agent_ids[left_index],
				agent_ids[right_index],
			)
	for agent_id: Variant in agent_ids:
		offsets[agent_id] = (offsets[agent_id] as Vector3).limit_length(MAX_AVOIDANCE_OFFSET)
	return offsets


static func movement_formation(agent_ids: Array[String]) -> Dictionary:
	var sorted_ids := agent_ids.duplicate()
	sorted_ids.sort()
	var formation := {}
	for index in range(sorted_ids.size()):
		var row_index := int(index / 2)
		var is_unpaired := index == sorted_ids.size() - 1 and sorted_ids.size() % 2 == 1
		formation[sorted_ids[index]] = {
			"lane_offset": 0.09 if sorted_ids.size() == 1 or is_unpaired else 0.18 * (index % 2),
			"longitudinal_offset": row_index * 0.42,
		}
	return formation


static func conversation_pair_offsets(
	left_id: String, left_position: Vector3, right_id: String, right_position: Vector3
) -> Dictionary:
	var delta := right_position - left_position
	delta.y = 0.0
	var distance := delta.length()
	var direction := (
		delta / distance if distance > 0.0001 else _pair_direction(right_id, left_id)
	)
	var shift := clampf((distance - CONVERSATION_DISTANCE) * 0.5, -MAX_CONVERSATION_SHIFT, MAX_CONVERSATION_SHIFT)
	return {left_id: direction * shift, right_id: -direction * shift}


static func _apply_pair_avoidance(
	offsets: Dictionary, positions: Dictionary, left_id: Variant, right_id: Variant
) -> void:
	var delta := (positions[left_id] as Vector3) - (positions[right_id] as Vector3)
	delta.y = 0.0
	var distance := delta.length()
	if distance >= PERSONAL_SPACE:
		return
	var direction := (
		delta / distance
		if distance > 0.0001
		else _pair_direction(str(left_id), str(right_id))
	)
	var pressure := pow(1.0 - distance / PERSONAL_SPACE, 2.0)
	var separation := direction * pressure * MAX_AVOIDANCE_OFFSET
	offsets[left_id] = (offsets[left_id] as Vector3) + separation
	offsets[right_id] = (offsets[right_id] as Vector3) - separation


static func _ring_radius(count: int, ring: int) -> float:
	var radius := MIN_SPACING
	if count > 2:
		radius = MIN_SPACING / (2.0 * sin(PI / float(count)))
	return radius + ring * MIN_SPACING


static func _stable_angle(value: String) -> float:
	return float(posmod(value.hash(), 360)) * PI / 180.0


static func _pair_direction(left_id: String, right_id: String) -> Vector3:
	var first := left_id if left_id < right_id else right_id
	var second := right_id if left_id < right_id else left_id
	var angle := _stable_angle("%s:%s" % [first, second])
	var sign_value := 1.0 if left_id == first else -1.0
	return Vector3(cos(angle) * sign_value, 0.0, sin(angle) * sign_value)
