extends Node

const READY_RUN_ID := "phase-zero"
const MAP_ID := "campus-world-v2"

@onready var world_presenter: WorldPresenter = $WorldRoot/Agents
@onready var world_map: Node3D = $WorldRoot/Map
@onready var camera: Camera3D = $WorldRoot/CameraRig/Camera3D
@onready var status_label: Label = $Overlay/StatusPanel/StatusLabel

var _host_window: JavaScriptObject
var _host_message_callback: JavaScriptObject
var _active_run_id := READY_RUN_ID
var _last_host_sequence := -1
var _client_sequence := 0
var _map_content_hash := ""
var _client_clock := ClientClock.new()


func _ready() -> void:
	camera.look_at(Vector3(0.0, 0.5, 0.0), Vector3.UP)
	world_presenter.agent_selected.connect(_on_agent_selected)
	var map_result := WorldMapExporter.new().build_document(world_map, MAP_ID)
	if not map_result.get("ok", false):
		_set_status("地图契约无效")
		push_error("Runtime world map is invalid: %s" % "; ".join(map_result.get("errors", [])))
		return
	_map_content_hash = str(map_result["document"]["content_hash"])
	if OS.has_feature("web"):
		_connect_web_bridge()
	else:
		_load_local_fixture()
	_set_status("等待宿主快照")
	_post_to_host("ready", {
		"engine_version": Engine.get_version_info().get("string", "unknown"),
		"capabilities": ["world_snapshot", "selection_changed"],
		"map_id": MAP_ID,
		"map_content_hash": _map_content_hash,
	})


func _exit_tree() -> void:
	if OS.has_feature("web") and _host_window and _host_message_callback:
		_host_window.removeEventListener("message", _host_message_callback)


func _connect_web_bridge() -> void:
	_host_window = JavaScriptBridge.get_interface("window")
	_host_message_callback = JavaScriptBridge.create_callback(_on_web_message)
	_host_window.addEventListener("message", _host_message_callback)


func _on_web_message(arguments: Array) -> void:
	if arguments.is_empty():
		return
	var event: JavaScriptObject = arguments[0]
	var raw_message := str(event.data)
	apply_host_message(raw_message)


func apply_host_message(raw_message: String) -> Dictionary:
	var decoded := WorldProtocolCodec.decode_host_message(raw_message)
	if not decoded.get("ok", false):
		_set_status("协议消息被拒绝")
		return decoded

	var envelope := decoded["envelope"] as Dictionary
	var sequence := int(envelope["sequence"])
	if sequence <= _last_host_sequence:
		return {"ok": false, "error": {"code": "stale_sequence"}}

	var message_run_id := str(envelope["run_id"])
	var message_type := str(envelope["type"])
	var payload := envelope.get("payload", {}) as Dictionary
	if message_type == "initialize":
		if payload.get("map_id") != MAP_ID:
			_set_status("地图版本不匹配")
			return {"ok": false, "error": {"code": "map_mismatch"}}
		_active_run_id = message_run_id
		_last_host_sequence = sequence
		_set_status("宿主已连接")
		return {"ok": true}
	if message_run_id != _active_run_id:
		return {"ok": false, "error": {"code": "run_mismatch"}}

	_last_host_sequence = sequence
	match message_type:
		"world_snapshot":
			if payload.get("map_id") != MAP_ID or payload.get("map_content_hash") != _map_content_hash:
				_set_status("地图快照不匹配")
				return {"ok": false, "error": {"code": "map_snapshot_mismatch"}}
			_client_clock.synchronize(
				str(payload.get("world_time", "")),
				str(payload.get("run_status", "paused")),
				float(payload.get("simulation_speed", 1.0)),
			)
			world_presenter.apply_snapshot(payload)
			world_presenter.set_presentation_paused(not _client_clock.is_running())
			_set_status("已同步 %s 位居民" % world_presenter.agent_count())
		"focus_entity":
			if payload.get("kind") == "agent":
				world_presenter.focus_agent(str(payload.get("id", "")))
		"run_status_changed":
			_client_clock.set_status(str(payload.get("status", "paused")))
			world_presenter.set_presentation_paused(not _client_clock.is_running())
		"simulation_speed_changed":
			_client_clock.set_speed(float(payload.get("simulation_speed", 1.0)))
		"dispose":
			_set_status("宿主已断开")
		_:
			pass
	return {"ok": true}


func _on_agent_selected(agent_id: String) -> void:
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
		status_label.text = "GODOT LAB · %s" % message


func _load_local_fixture() -> void:
	var file := FileAccess.open("res://tests/fixtures/world_snapshot.json", FileAccess.READ)
	if file == null:
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if parsed is Dictionary:
		world_presenter.apply_snapshot(parsed)
