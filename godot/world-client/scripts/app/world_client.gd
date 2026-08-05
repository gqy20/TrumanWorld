extends Node

const READY_RUN_ID := "phase-zero"

@onready var world_presenter: WorldPresenter = $WorldRoot/Agents
@onready var world_map: Node3D = $WorldRoot/Map
@onready var camera_rig: DirectorCamera = $WorldRoot/CameraRig
@onready var world_environment: WorldEnvironment = $WorldRoot/WorldEnvironment
@onready var sun: DirectionalLight3D = $WorldRoot/Sun
@onready var status_panel: PanelContainer = $Overlay/StatusPanel
@onready var status_label: Label = $Overlay/StatusPanel/StatusLabel

var _host_window: JavaScriptObject
var _host_message_callback: JavaScriptObject
var _active_run_id := READY_RUN_ID
var _scenario_id := ScenarioSceneRegistry.DEFAULT_SCENARIO_ID
var _map_id := ""
var _last_host_sequence := -1
var _client_sequence := 0
var _map_content_hash := ""
var _client_clock := ClientClock.new()
var _atmosphere := WorldAtmosphere.new()
var _object_presenter := WorldObjectPresenter.new()
var _selected_agent_id := ""
var _status_update_elapsed := 0.0


func _ready() -> void:
	status_panel.visible = not _is_embedded()
	_scenario_id = _requested_scenario_id()
	var definition := ScenarioSceneRegistry.resolve(_scenario_id)
	var map_instance := ScenarioSceneRegistry.instantiate_map(_scenario_id)
	if definition.is_empty() or map_instance == null:
		_set_status("UNKNOWN SCENARIO")
		push_error("Unable to load registered scenario map: %s" % _scenario_id)
		return
	_map_id = str(definition["map_id"])
	map_instance.name = "ScenarioMap"
	world_map.add_child(map_instance)
	camera_rig.configure_from_map(world_map)
	RuntimeMapVisuals.build(world_map, _scenario_id)
	_object_presenter.configure(world_map)
	_atmosphere.configure(world_environment.environment, sun, $WorldRoot)
	world_presenter.agent_selected.connect(_on_agent_selected)
	var map_result := WorldMapExporter.new().build_document(world_map, _map_id)
	if not map_result.get("ok", false):
		_set_status("INVALID MAP")
		push_error("Runtime world map is invalid: %s" % "; ".join(map_result.get("errors", [])))
		return
	_map_content_hash = str(map_result["document"]["content_hash"])
	world_presenter.configure_navigation(map_result["document"], _client_clock)
	if OS.has_feature("web"):
		_connect_web_bridge()
	else:
		_load_local_fixture()
	_set_status("WAITING FOR WORLD")
	_post_to_host("ready", {
		"engine_version": Engine.get_version_info().get("string", "unknown"),
		"capabilities": ["world_snapshot", "selection_changed"],
		"scenario_id": _scenario_id,
		"map_id": _map_id,
		"map_content_hash": _map_content_hash,
	})


func _process(delta: float) -> void:
	if _client_clock.world_time_seconds() <= 0.0:
		return
	_atmosphere.update(_client_clock.world_time_seconds())
	if not _selected_agent_id.is_empty():
		camera_rig.update_follow_target(world_presenter.agent_focus_position(_selected_agent_id))
	_status_update_elapsed += delta
	if _status_update_elapsed >= 0.5:
		_status_update_elapsed = 0.0
		var time := Time.get_datetime_dict_from_unix_time(int(_client_clock.world_time_seconds()))
		_set_status(
			"%02d:%02d · %s · %d RESIDENTS"
			% [
				int(time.get("hour", 0)),
				int(time.get("minute", 0)),
				"LIVE" if _client_clock.is_running() else "PAUSED",
				world_presenter.agent_count(),
			]
		)


func _exit_tree() -> void:
	if OS.has_feature("web") and _host_window and _host_message_callback:
		_host_window.removeEventListener("message", _host_message_callback)


func _connect_web_bridge() -> void:
	_host_window = JavaScriptBridge.get_interface("window")
	_host_message_callback = JavaScriptBridge.create_callback(_on_web_message)
	_host_window.addEventListener("message", _host_message_callback)


func _requested_scenario_id() -> String:
	var candidate := _query_parameter("scenario_id")
	if not candidate.is_empty() and not ScenarioSceneRegistry.resolve(candidate).is_empty():
		return candidate
	return ScenarioSceneRegistry.DEFAULT_SCENARIO_ID


func _is_embedded() -> bool:
	return _query_parameter("embedded") == "1"


func _query_parameter(parameter_name: String) -> String:
	if not OS.has_feature("web"):
		return ""
	var window := JavaScriptBridge.get_interface("window")
	if window == null:
		return ""
	var query := str(window.location.search).trim_prefix("?")
	for component: String in query.split("&", false):
		var pair := component.split("=", true, 1)
		if pair.size() == 2 and pair[0] == parameter_name:
			return str(pair[1]).uri_decode()
	return ""


func _on_web_message(arguments: Array) -> void:
	if arguments.is_empty():
		return
	var event: JavaScriptObject = arguments[0]
	var raw_message := str(event.data)
	apply_host_message(raw_message)


func apply_host_message(raw_message: String) -> Dictionary:
	var decoded := WorldProtocolCodec.decode_host_message(raw_message)
	if not decoded.get("ok", false):
		_set_status("MESSAGE REJECTED")
		return decoded

	var envelope := decoded["envelope"] as Dictionary
	var sequence := int(envelope["sequence"])
	if sequence <= _last_host_sequence:
		return {"ok": false, "error": {"code": "stale_sequence"}}

	var message_run_id := str(envelope["run_id"])
	var message_type := str(envelope["type"])
	var payload := envelope.get("payload", {}) as Dictionary
	if message_type == "initialize":
		if payload.get("map_id") != _map_id:
			_set_status("MAP VERSION MISMATCH")
			return {"ok": false, "error": {"code": "map_mismatch"}}
		_active_run_id = message_run_id
		_last_host_sequence = sequence
		_set_status("HOST CONNECTED")
		return {"ok": true}
	if message_run_id != _active_run_id:
		return {"ok": false, "error": {"code": "run_mismatch"}}

	_last_host_sequence = sequence
	match message_type:
		"world_snapshot":
			if payload.get("map_id") != _map_id or payload.get("map_content_hash") != _map_content_hash:
				_set_status("MAP SNAPSHOT MISMATCH")
				return {"ok": false, "error": {"code": "map_snapshot_mismatch"}}
			_client_clock.synchronize(
				str(payload.get("world_time", "")),
				str(payload.get("run_status", "paused")),
				float(payload.get("simulation_speed", 1.0)),
			)
			world_presenter.apply_snapshot(payload)
			_object_presenter.apply_states(payload.get("object_states", []))
			world_presenter.set_presentation_paused(not _client_clock.is_running())
		"focus_entity":
			if payload.get("kind") == "agent":
				_selected_agent_id = str(payload.get("id", ""))
				if world_presenter.focus_agent(_selected_agent_id):
					camera_rig.focus_position(
						world_presenter.agent_focus_position(_selected_agent_id), true
					)
		"run_status_changed":
			_client_clock.set_status(str(payload.get("status", "paused")))
			world_presenter.set_presentation_paused(not _client_clock.is_running())
		"simulation_speed_changed":
			_client_clock.set_speed(float(payload.get("simulation_speed", 1.0)))
		"world_event_batch":
			pass
		"dispose":
			_set_status("HOST DISCONNECTED")
		_:
			pass
	return {"ok": true}


func _on_agent_selected(agent_id: String) -> void:
	_selected_agent_id = agent_id
	camera_rig.focus_position(world_presenter.agent_focus_position(agent_id), true)
	_post_to_host("selection_changed", {"kind": "agent", "id": agent_id})


func _post_to_host(message_type: String, payload: Dictionary) -> void:
	_client_sequence += 1
	if not OS.has_feature("web") or not _host_window:
		return
	var encoded := WorldProtocolCodec.encode_client_message(
		message_type,
		_active_run_id,
		_client_sequence,
		payload,
	)
	_host_window.parent.postMessage(encoded, _host_window.location.origin)


func _set_status(message: String) -> void:
	if is_instance_valid(status_label):
		status_label.text = "GODOT WORLD · %s" % message


func _load_local_fixture() -> void:
	var file := FileAccess.open("res://tests/fixtures/world_snapshot.json", FileAccess.READ)
	if file == null:
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if parsed is Dictionary:
		world_presenter.apply_snapshot(parsed)
