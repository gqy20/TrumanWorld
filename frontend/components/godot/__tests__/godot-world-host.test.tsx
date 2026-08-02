import { render, screen, waitFor } from "@testing-library/react";

import { GodotWorldHost } from "../godot-world-host";

function godotMessage(type: string, sequence: number, payload: Record<string, unknown>) {
  return JSON.stringify({
    protocol_version: 1,
    message_id: `godot-${sequence}`,
    run_id: "phase-zero",
    sequence,
    sent_at: "2026-08-03T10:00:00Z",
    type,
    payload,
  });
}

describe("GodotWorldHost", () => {
  test("initializes the fixture after Godot is ready and receives selection", async () => {
    render(<GodotWorldHost readyTimeoutMs={30_000} />);
    const iframe = screen.getByTitle("Godot 具身世界技术验证") as HTMLIFrameElement;
    const postMessage = jest.spyOn(iframe.contentWindow!, "postMessage").mockImplementation();

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: window.location.origin,
        source: iframe.contentWindow,
        data: godotMessage("ready", 1, {
          engine_version: "4.7.1",
          map_id: "campus-world-v2",
          map_content_hash:
            "sha256:5a42cca0743a0bfb398913d66d0ca0112d3156c2441d7baac1ba5e049fbca9a6",
        }),
      }),
    );

    await waitFor(() => expect(screen.getByText("Bridge ready")).toBeInTheDocument());
    expect(postMessage).toHaveBeenCalledTimes(2);
    expect(postMessage.mock.calls.map(([value]) => JSON.parse(String(value)).type)).toEqual([
      "initialize",
      "world_snapshot",
    ]);

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: window.location.origin,
        source: iframe.contentWindow,
        data: godotMessage("selection_changed", 2, { kind: "agent", id: "chen" }),
      }),
    );

    await waitFor(() => expect(screen.getByText("Chen", { selector: "strong" })).toBeInTheDocument());
  });
});
