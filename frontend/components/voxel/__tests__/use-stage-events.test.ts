import { act, renderHook } from "@testing-library/react";

import { makeWorldSnapshot } from "@/test-utils/app/fixtures";
import { buildSceneWorld } from "@/lib/world-scene-adapter";

import {
  VOXEL_BUBBLE_TTL_MS,
  VOXEL_MOVE_TRAIL_TTL_MS,
  useActiveVoxelStageEvents,
} from "../use-stage-events";

describe("useActiveVoxelStageEvents", () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it("shows recent events once and expires each visual at its own TTL", () => {
    const world = buildSceneWorld(makeWorldSnapshot());
    const { result, rerender } = renderHook(
      ({ sceneWorld }) => useActiveVoxelStageEvents(sceneWorld),
      { initialProps: { sceneWorld: world } },
    );

    expect(result.current.bubbles.map((bubble) => bubble.id)).toEqual(["event-1"]);
    expect(result.current.moveTrails.map((trail) => trail.id)).toEqual(["event-2"]);

    act(() => jest.advanceTimersByTime(VOXEL_MOVE_TRAIL_TTL_MS));
    expect(result.current.moveTrails).toEqual([]);
    expect(result.current.bubbles).toHaveLength(1);

    act(() => jest.advanceTimersByTime(VOXEL_BUBBLE_TTL_MS - VOXEL_MOVE_TRAIL_TTL_MS));
    expect(result.current.bubbles).toEqual([]);

    rerender({ sceneWorld: { ...world } });
    expect(result.current).toEqual({ bubbles: [], moveTrails: [] });

    rerender({ sceneWorld: { ...world, runId: "run-2" } });
    expect(result.current.bubbles.map((bubble) => bubble.id)).toEqual(["event-1"]);
    expect(result.current.moveTrails.map((trail) => trail.id)).toEqual(["event-2"]);
  });

  it("reveals a newly polled event and clears timers on unmount", () => {
    const world = buildSceneWorld(makeWorldSnapshot());
    const { result, rerender, unmount } = renderHook(
      ({ sceneWorld }) => useActiveVoxelStageEvents(sceneWorld),
      { initialProps: { sceneWorld: world } },
    );
    const nextBubble = {
      ...world.bubbles[0],
      id: "event-3",
      text: "See you at the library",
    };

    rerender({
      sceneWorld: {
        ...world,
        bubbles: [nextBubble, ...world.bubbles],
      },
    });

    expect(result.current.bubbles.map((bubble) => bubble.id)).toEqual([
      "event-3",
      "event-1",
    ]);
    expect(jest.getTimerCount()).toBeGreaterThan(0);

    unmount();
    expect(jest.getTimerCount()).toBe(0);
  });
});
