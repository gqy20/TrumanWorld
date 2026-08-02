class_name WorldProtocolCodec
extends RefCounted

const PROTOCOL_VERSION := 1
const HOST_MESSAGE_TYPES := {
	"initialize": true,
	"world_snapshot": true,
	"world_event_batch": true,
	"run_status_changed": true,
	"simulation_speed_changed": true,
	"focus_entity": true,
	"set_quality": true,
	"dispose": true,
}


static func decode_host_message(raw_message: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(raw_message)
	if not parsed is Dictionary:
		return _failure("invalid_json", "Host message must be a JSON object")

	var envelope := parsed as Dictionary
	if envelope.get("protocol_version") != PROTOCOL_VERSION:
		return _failure("protocol_mismatch", "Unsupported protocol version")
	if not envelope.get("type") is String:
		return _failure("invalid_type", "Message type must be a string")
	if not HOST_MESSAGE_TYPES.has(envelope["type"]):
		return _failure("unknown_type", "Host message type is not allowed")
	if not envelope.get("run_id") is String:
		return _failure("invalid_run_id", "run_id must be a string")
	if not envelope.get("sequence") is int and not envelope.get("sequence") is float:
		return _failure("invalid_sequence", "sequence must be numeric")
	if not envelope.get("payload", {}) is Dictionary:
		return _failure("invalid_payload", "payload must be an object")

	return {"ok": true, "envelope": envelope}


static func encode_client_message(
	message_type: String,
	run_id: String,
	sequence: int,
	payload: Dictionary,
) -> String:
	return JSON.stringify({
		"protocol_version": PROTOCOL_VERSION,
		"message_id": "godot-%s-%s" % [Time.get_ticks_msec(), sequence],
		"run_id": run_id,
		"sequence": sequence,
		"sent_at": Time.get_datetime_string_from_system(true),
		"type": message_type,
		"payload": payload,
	})


static func _failure(code: String, message: String) -> Dictionary:
	return {"ok": false, "error": {"code": code, "message": message}}
