class_name WorldPresenter
extends Node3D

signal agent_selected(agent_id: String)

var _avatars: Dictionary = {}
var _highlighted_agent_id := ""
var _route_positions: Dictionary = {}
var _client_clock: ClientClock
var _conversation_partner_by_agent_id: Dictionary = {}


func _process(_delta: float) -> void:
	_update_local_avoidance()
	_update_conversation_positions()
	_update_conversation_facing()


func configure_navigation(map_document: Dictionary, client_clock: ClientClock) -> void:
	_route_positions = RouteProjection.route_positions(map_document)
	_client_clock = client_clock


func apply_snapshot(payload: Dictionary) -> void:
	var seen_ids := {}
	var agents: Variant = payload.get("agents", [])
	if not agents is Array:
		return

	for raw_agent: Variant in agents:
		if not raw_agent is Dictionary:
			continue
		var agent := raw_agent as Dictionary
		var agent_id := str(agent.get("id", ""))
		if agent_id.is_empty():
			continue
		seen_ids[agent_id] = true
		var avatar := _get_or_create_avatar(agent_id, str(agent.get("visual_asset_id", "")))
		avatar.configure(agent)
		avatar.set_highlighted(agent_id == _highlighted_agent_id)

	for existing_id: Variant in _avatars.keys():
		if seen_ids.has(existing_id):
			continue
		var stale_avatar := _avatars[existing_id] as AgentAvatar
		stale_avatar.queue_free()
		_avatars.erase(existing_id)

	_arrange_idle_agents()
	_arrange_moving_agents()
	_apply_conversations(payload.get("conversations", []))


func focus_agent(agent_id: String) -> bool:
	if not _avatars.has(agent_id):
		return false
	_highlighted_agent_id = agent_id
	for current_id: Variant in _avatars:
		var avatar := _avatars[current_id] as AgentAvatar
		avatar.set_highlighted(str(current_id) == agent_id)
	return true


func agent_count() -> int:
	return _avatars.size()


func agent_focus_position(agent_id: String) -> Vector3:
	if not _avatars.has(agent_id):
		return Vector3.ZERO
	return (_avatars[agent_id] as AgentAvatar).focus_position()


func set_presentation_paused(value: bool) -> void:
	for avatar: AgentAvatar in _avatars.values():
		avatar.set_presentation_paused(value)


func _arrange_idle_agents() -> void:
	var groups := {}
	for avatar: AgentAvatar in _avatars.values():
		avatar.set_idle_offset(Vector3.ZERO)
		if not avatar.can_use_idle_offset():
			continue
		var base := avatar.presentation_base_position()
		var key := "%d:%d" % [roundi(base.x * 10.0), roundi(base.z * 10.0)]
		if not groups.has(key):
			groups[key] = []
		(groups[key] as Array).append(avatar.agent_id)
	for raw_agent_ids: Variant in groups.values():
		var agent_ids: Array[String] = []
		agent_ids.assign(raw_agent_ids)
		var offsets := AgentPlacement.radial_offsets(agent_ids)
		for agent_id: String in agent_ids:
			(_avatars[agent_id] as AgentAvatar).set_idle_offset(offsets[agent_id] as Vector3)


func _update_local_avoidance() -> void:
	var positions := {}
	for agent_id: Variant in _avatars:
		positions[agent_id] = (_avatars[agent_id] as AgentAvatar).avoidance_base_position()
	var offsets := AgentPlacement.avoidance_offsets(positions)
	for agent_id: Variant in _avatars:
		var avatar := _avatars[agent_id] as AgentAvatar
		var offset := offsets.get(agent_id, Vector3.ZERO) as Vector3
		avatar.set_avoidance_target(offset if avatar.can_use_avoidance() else Vector3.ZERO)


func _arrange_moving_agents() -> void:
	var groups := {}
	for avatar: AgentAvatar in _avatars.values():
		avatar.set_movement_formation(0.09, 0.0)
		var key := avatar.movement_formation_key()
		if key.is_empty():
			continue
		if not groups.has(key):
			groups[key] = []
		(groups[key] as Array).append(avatar.agent_id)
	for raw_agent_ids: Variant in groups.values():
		var agent_ids: Array[String] = []
		agent_ids.assign(raw_agent_ids)
		var formation := AgentPlacement.movement_formation(agent_ids)
		for agent_id: String in agent_ids:
			var member := formation[agent_id] as Dictionary
			(_avatars[agent_id] as AgentAvatar).set_movement_formation(
				float(member["lane_offset"]), float(member["longitudinal_offset"])
			)


func _update_conversation_positions() -> void:
	for avatar: AgentAvatar in _avatars.values():
		avatar.set_conversation_target(Vector3.ZERO)
	for agent_id: Variant in _conversation_partner_by_agent_id:
		var partner_id: Variant = _conversation_partner_by_agent_id[agent_id]
		if (
			str(agent_id) >= str(partner_id)
			or not _avatars.has(partner_id)
			or _conversation_partner_by_agent_id.get(partner_id) != agent_id
		):
			continue
		_apply_conversation_pair(str(agent_id), str(partner_id))


func _apply_conversation_pair(left_id: String, right_id: String) -> void:
	var left := _avatars[left_id] as AgentAvatar
	var right := _avatars[right_id] as AgentAvatar
	var offsets := AgentPlacement.conversation_pair_offsets(
		left_id, left.avoidance_base_position(), right_id, right.avoidance_base_position()
	)
	left.set_conversation_target(
		offsets[left_id] as Vector3 if left.can_reposition_for_conversation() else Vector3.ZERO
	)
	right.set_conversation_target(
		offsets[right_id] as Vector3 if right.can_reposition_for_conversation() else Vector3.ZERO
	)


func _update_conversation_facing() -> void:
	for agent_id: Variant in _conversation_partner_by_agent_id:
		var partner_id: Variant = _conversation_partner_by_agent_id[agent_id]
		if _avatars.has(agent_id) and _avatars.has(partner_id):
			(_avatars[agent_id] as AgentAvatar).update_conversation_partner_position(
				(_avatars[partner_id] as AgentAvatar).global_position
			)


func _get_or_create_avatar(agent_id: String, visual_asset_id: String = "") -> AgentAvatar:
	if _avatars.has(agent_id):
		return _avatars[agent_id] as AgentAvatar
	var avatar := AgentAvatar.new()
	avatar.agent_id = agent_id
	avatar.visual_asset_id = visual_asset_id
	avatar.configure_navigation(_route_positions, _client_clock)
	avatar.selected.connect(_on_agent_selected)
	add_child(avatar)
	_avatars[agent_id] = avatar
	return avatar


func _apply_conversations(raw_conversations: Variant) -> void:
	_conversation_partner_by_agent_id.clear()
	for avatar: AgentAvatar in _avatars.values():
		avatar.clear_conversation()
	if not raw_conversations is Array:
		return

	for raw_conversation: Variant in raw_conversations:
		if not raw_conversation is Dictionary:
			continue
		var conversation := raw_conversation as Dictionary
		var participant_ids: Variant = conversation.get("participant_ids", [])
		if not participant_ids is Array or participant_ids.size() < 2:
			continue
		var active_speaker_id := str(conversation.get("active_speaker_id", ""))
		for raw_agent_id: Variant in participant_ids:
			var current_id := str(raw_agent_id)
			if not _avatars.has(current_id):
				continue
			var partner_id := ""
			for raw_partner_id: Variant in participant_ids:
				if str(raw_partner_id) != current_id and _avatars.has(str(raw_partner_id)):
					partner_id = str(raw_partner_id)
					break
			if partner_id.is_empty():
				continue
			_conversation_partner_by_agent_id[current_id] = partner_id
			var avatar := _avatars[current_id] as AgentAvatar
			var partner := _avatars[partner_id] as AgentAvatar
			avatar.set_conversation(
				partner.display_name,
				partner.global_position,
				current_id == active_speaker_id,
			)


func _on_agent_selected(agent_id: String) -> void:
	focus_agent(agent_id)
	agent_selected.emit(agent_id)
