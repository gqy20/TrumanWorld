import { GodotBridge } from "../godot-bridge";

describe("GodotBridge", () => {
  test("posts versioned messages to the iframe", () => {
    const iframe = document.createElement("iframe");
    document.body.appendChild(iframe);
    const postMessage = jest.spyOn(iframe.contentWindow!, "postMessage").mockImplementation();
    const bridge = new GodotBridge(
      iframe,
      "phase-zero",
      window.location.origin,
      jest.fn(),
      jest.fn(),
    );

    expect(bridge.post("initialize", { map_id: "phase-zero-plaza" })).toBe(true);
    expect(postMessage).toHaveBeenCalledTimes(1);
    const [encoded, origin] = postMessage.mock.calls[0];
    expect(origin).toBe(window.location.origin);
    expect(JSON.parse(String(encoded))).toMatchObject({
      protocol_version: 1,
      run_id: "phase-zero",
      sequence: 1,
      type: "initialize",
    });
  });

  test("accepts same-origin messages from the hosted iframe", () => {
    const iframe = document.createElement("iframe");
    document.body.appendChild(iframe);
    const onMessage = jest.fn();
    const bridge = new GodotBridge(
      iframe,
      "phase-zero",
      window.location.origin,
      onMessage,
      jest.fn(),
    );
    bridge.start();

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: window.location.origin,
        source: iframe.contentWindow,
        data: JSON.stringify({
          protocol_version: 1,
          message_id: "godot-1",
          run_id: "phase-zero",
          sequence: 1,
          sent_at: "2026-08-03T10:00:00Z",
          type: "selection_changed",
          payload: { kind: "agent", id: "mei" },
        }),
      }),
    );

    expect(onMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: "selection_changed", payload: { kind: "agent", id: "mei" } }),
    );
    bridge.stop();
  });

  test("ignores messages from another origin", () => {
    const iframe = document.createElement("iframe");
    document.body.appendChild(iframe);
    const onMessage = jest.fn();
    const bridge = new GodotBridge(
      iframe,
      "phase-zero",
      window.location.origin,
      onMessage,
      jest.fn(),
    );
    bridge.start();

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://example.invalid",
        source: iframe.contentWindow,
        data: "{}",
      }),
    );

    expect(onMessage).not.toHaveBeenCalled();
    bridge.stop();
  });
});
