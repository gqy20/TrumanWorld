import { act, render, screen, waitFor } from "@testing-library/react";

import { GodotWorldHost } from "../godot-world-host";

function godotMessage(
  type: string,
  sequence: number,
  payload: Record<string, unknown>,
  runId = "phase-zero",
) {
  return JSON.stringify({
    protocol_version: 1,
    message_id: `godot-${sequence}`,
    run_id: runId,
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
    expect(iframe.src).toContain("scenario_id=campus_world");
    expect(iframe.src).not.toContain("embedded=1");
    const postMessage = jest.spyOn(iframe.contentWindow!, "postMessage").mockImplementation();

    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: window.location.origin,
          source: iframe.contentWindow,
          data: godotMessage("ready", 1, {
            engine_version: "4.7.1",
            map_id: "campus-world-v2",
            map_content_hash:
            "sha256:e2a7e49020876c2fea7ec0850ba58ff955bd67a85a944835bffb02cffbc532da",
          }),
        }),
      );
    });

    await waitFor(() => expect(screen.getByText("Bridge ready")).toBeInTheDocument());
    expect(postMessage).toHaveBeenCalledTimes(2);
    expect(postMessage.mock.calls.map(([value]) => JSON.parse(String(value)).type)).toEqual([
      "initialize",
      "world_snapshot",
    ]);

    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: window.location.origin,
          source: iframe.contentWindow,
          data: godotMessage("selection_changed", 2, { kind: "agent", id: "chen" }),
        }),
      );
    });

    await waitFor(() => expect(screen.getByText("Chen", { selector: "strong" })).toBeInTheDocument());
    expect(screen.getByText(/Morning\. Are you heading to class\?/)).toBeInTheDocument();
    expect(screen.getAllByText("交谈中").length).toBeGreaterThan(0);
  });

  test("selects the registered Godot scene from the snapshot scenario", () => {
    render(
      <GodotWorldHost
        snapshot={{
          scenario_id: "narrative_world",
          map_id: "narrative-world-v1",
          map_content_hash: "sha256:narrative",
          tick: 0,
          world_time: "2026-03-02T06:00:00Z",
          run_status: "paused",
          simulation_speed: 1,
          agents: [],
          object_states: [],
          conversations: [],
        }}
      />,
    );
    const iframe = screen.getByTitle("Godot 具身世界技术验证") as HTMLIFrameElement;
    jest.spyOn(iframe.contentWindow!, "postMessage").mockImplementation();
    expect(iframe.src).toContain("scenario_id=narrative_world");
  });

  test("hides the Godot status panel only in the embedded world view", () => {
    render(<GodotWorldHost embedded />);
    const iframe = screen.getByTitle("3D 世界") as HTMLIFrameElement;
    jest.spyOn(iframe.contentWindow!, "postMessage").mockImplementation();
    expect(iframe).toHaveAttribute(
      "src",
      expect.stringContaining("embedded=1"),
    );
    expect(screen.getByLabelText("3D 相机操作")).toHaveTextContent(
      "WASD 移动·左键旋转·右键平移·滚轮缩放",
    );
  });

  test("loads an authoritative snapshot when a real run id is provided", async () => {
    const originalFetch = global.fetch;
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        map_id: "campus-world-v2",
        map_content_hash:
          "sha256:e2a7e49020876c2fea7ec0850ba58ff955bd67a85a944835bffb02cffbc532da",
        tick: 4,
        world_time: "2026-03-02T09:20:00Z",
        run_status: "running",
        simulation_speed: 1,
        agents: [],
        object_states: [],
        conversations: [],
      }),
    }) as jest.Mock;

    try {
      render(<GodotWorldHost runId="live-run" readyTimeoutMs={30_000} />);
      const iframe = screen.getByTitle("Godot 具身世界技术验证") as HTMLIFrameElement;
      const postMessage = jest.spyOn(iframe.contentWindow!, "postMessage").mockImplementation();

      await waitFor(() => expect(screen.getByText("campus-world-v2")).toBeInTheDocument());
      act(() => {
        window.dispatchEvent(
          new MessageEvent("message", {
            origin: window.location.origin,
            source: iframe.contentWindow,
            data: godotMessage(
              "ready",
              1,
              {
                engine_version: "4.7.1",
                map_id: "campus-world-v2",
                map_content_hash:
                "sha256:e2a7e49020876c2fea7ec0850ba58ff955bd67a85a944835bffb02cffbc532da",
              },
              "live-run",
            ),
          }),
        );
      });

      await waitFor(() => expect(screen.getByText("Bridge ready")).toBeInTheDocument());
      expect(postMessage.mock.calls.map(([value]) => JSON.parse(String(value)).type)).toEqual([
        "initialize",
        "world_snapshot",
      ]);
      expect(screen.getByText("Live Run · Phase 4")).toBeInTheDocument();
    } finally {
      global.fetch = originalFetch;
    }
  });
});
