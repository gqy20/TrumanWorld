class_name WorldPresenter
extends Node3D

signal agent_selected(agent_id: String)

var _avatars: Dictionary = {}
var _highlighted_agent_id := ""


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
		var avatar := _get_or_create_avatar(agent_id)
		avatar.configure(agent)
		avatar.set_highlighted(agent_id == _highlighted_agent_id)

	for existing_id: Variant in _avatars.keys():
		if seen_ids.has(existing_id):
			continue
		var stale_avatar := _avatars[existing_id] as AgentAvatar
		stale_avatar.queue_free()
		_avatars.erase(existing_id)

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


func _get_or_create_avatar(agent_id: String) -> AgentAvatar:
	if _avatars.has(agent_id):
		return _avatars[agent_id] as AgentAvatar
	var avatar := AgentAvatar.new()
	avatar.agent_id = agent_id
	avatar.selected.connect(_on_agent_selected)
	add_child(avatar)
	_avatars[agent_id] = avatar
	return avatar


func _apply_conversations(raw_conversations: Variant) -> void:
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
