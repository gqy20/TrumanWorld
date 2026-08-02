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


func _on_agent_selected(agent_id: String) -> void:
	focus_agent(agent_id)
	agent_selected.emit(agent_id)
