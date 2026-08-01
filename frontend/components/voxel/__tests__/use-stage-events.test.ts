import { act, renderHook } from "@testing-library/react";

import { makeWorldSnapshot } from "@/test-utils/app/fixtures";
import { buildSceneWorld, type SceneWorld } from "@/lib/world-scene-adapter";

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

  it("does not replay an event that temporarily leaves the recent window", () => {
    const world = buildSceneWorld(makeWorldSnapshot());
    const { result, rerender } = renderHook(
      ({ sceneWorld }) => useActiveVoxelStageEvents(sceneWorld),
      { initialProps: { sceneWorld: world } },
    );
    const nextTrail = { ...world.moveTrails[0], id: "movement-3" };

    rerender({ sceneWorld: { ...world, moveTrails: [nextTrail, ...world.moveTrails] } });
    expect(result.current.moveTrails.map((trail) => trail.id)).toEqual(["movement-3"]);

    act(() => jest.advanceTimersByTime(VOXEL_MOVE_TRAIL_TTL_MS));
    rerender({ sceneWorld: { ...world, moveTrails: [] } });
    rerender({ sceneWorld: { ...world, moveTrails: [nextTrail] } });

    expect(result.current.moveTrails).toEqual([]);
  });

  it("does not replay an authoritative movement after the agent arrives", () => {
    const world = buildSceneWorld(makeWorldSnapshot());
    const movement = { ...world.moveTrails[0], id: "movement-arriving", isActive: true };
    const activeWorld: SceneWorld = {
      ...world,
      activeMovements: [movement],
      moveTrails: [],
    };
    const { result, rerender } = renderHook(
      ({ sceneWorld }) => useActiveVoxelStageEvents(sceneWorld),
      { initialProps: { sceneWorld: activeWorld } },
    );

    rerender({
      sceneWorld: { ...world, activeMovements: [], moveTrails: [movement] },
    });

    expect(result.current.moveTrails).toEqual([]);
  });
});
