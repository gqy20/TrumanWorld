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

  it("treats the initial snapshot as history and only reveals newly observed events", () => {
    const world = buildSceneWorld(makeWorldSnapshot());
    const { result, rerender } = renderHook(
      ({ sceneWorld }) => useActiveVoxelStageEvents(sceneWorld),
      { initialProps: { sceneWorld: world } },
    );

    expect(result.current).toEqual({ bubbles: [], moveTrails: [] });

    const nextBubble = { ...world.bubbles[0], id: "event-3" };
    const nextTrail = { ...world.moveTrails[0], id: "event-4" };
    rerender({
      sceneWorld: {
        ...world,
        bubbles: [nextBubble, ...world.bubbles],
        moveTrails: [nextTrail, ...world.moveTrails],
      },
    });

    expect(result.current.bubbles.map((bubble) => bubble.id)).toEqual(["event-3"]);
    expect(result.current.moveTrails.map((trail) => trail.id)).toEqual(["event-4"]);

    act(() => jest.advanceTimersByTime(VOXEL_MOVE_TRAIL_TTL_MS));
    expect(result.current.moveTrails).toEqual([]);
    expect(result.current.bubbles).toHaveLength(1);

    act(() => jest.advanceTimersByTime(VOXEL_BUBBLE_TTL_MS - VOXEL_MOVE_TRAIL_TTL_MS));
    expect(result.current.bubbles).toEqual([]);

    rerender({ sceneWorld: { ...world, bubbles: [nextBubble], moveTrails: [nextTrail] } });
    expect(result.current).toEqual({ bubbles: [], moveTrails: [] });

    rerender({ sceneWorld: { ...world, runId: "run-2" } });
    expect(result.current).toEqual({ bubbles: [], moveTrails: [] });
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

    expect(result.current.bubbles.map((bubble) => bubble.id)).toEqual(["event-3"]);
    expect(jest.getTimerCount()).toBeGreaterThan(0);

    unmount();
    expect(jest.getTimerCount()).toBe(0);
  });
});
