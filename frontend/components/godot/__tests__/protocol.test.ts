import {
  createGodotEnvelope,
  decodeGodotClientMessage,
  GODOT_PROTOCOL_VERSION,
} from "../protocol";

describe("Godot protocol", () => {
  test("creates a versioned host envelope", () => {
    const envelope = createGodotEnvelope("initialize", "run-1", 3, { map_id: "map-1" });

    expect(envelope).toMatchObject({
      protocol_version: GODOT_PROTOCOL_VERSION,
      run_id: "run-1",
      sequence: 3,
      type: "initialize",
      payload: { map_id: "map-1" },
    });
  });

  test("decodes a valid Godot client message", () => {
    const decoded = decodeGodotClientMessage(
      JSON.stringify({
        protocol_version: 1,
        message_id: "godot-1",
        run_id: "phase-zero",
        sequence: 1,
        sent_at: "2026-08-03T10:00:00Z",
        type: "ready",
        payload: { engine_version: "4.7.1" },
      }),
    );

    expect(decoded.ok).toBe(true);
  });

  test.each([
    ["invalid_json", "{"],
    [
      "protocol_mismatch",
      {
        protocol_version: 2,
        message_id: "godot-1",
        run_id: "phase-zero",
        sequence: 1,
        sent_at: "2026-08-03T10:00:00Z",
        type: "ready",
        payload: {},
      },
    ],
    [
      "unknown_type",
      {
        protocol_version: 1,
        message_id: "godot-1",
        run_id: "phase-zero",
        sequence: 1,
        sent_at: "2026-08-03T10:00:00Z",
        type: "execute_script",
        payload: {},
      },
    ],
  ])("rejects %s", (expectedError, value) => {
    const decoded = decodeGodotClientMessage(value);

    expect(decoded).toEqual({ ok: false, error: expectedError });
  });
});
