"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type {
  SceneBubble,
  SceneMoveTrail,
  SceneWorld,
} from "@/lib/world-scene-adapter";

export type ActiveVoxelStageEvents = {
  bubbles: SceneBubble[];
  moveTrails: SceneMoveTrail[];
};

export const VOXEL_BUBBLE_TTL_MS = 9000;
export const VOXEL_MOVE_TRAIL_TTL_MS = 7000;

const MAX_ACTIVE_BUBBLES = 2;
const MAX_ACTIVE_MOVE_TRAILS = 1;

export function useActiveVoxelStageEvents(sceneWorld: SceneWorld): ActiveVoxelStageEvents {
  const [activeKeys, setActiveKeys] = useState<Set<string>>(() => new Set());
  const seenKeysRef = useRef<Set<string>>(new Set());
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const runIdRef = useRef(sceneWorld.runId);

  useEffect(() => {
    if (runIdRef.current === sceneWorld.runId) return;
    timersRef.current.forEach((timer) => clearTimeout(timer));
    timersRef.current.clear();
    seenKeysRef.current.clear();
    runIdRef.current = sceneWorld.runId;
    setActiveKeys(new Set());
  }, [sceneWorld.runId]);

  useEffect(() => {
    const visibleCandidates = [
      ...sceneWorld.bubbles.slice(0, MAX_ACTIVE_BUBBLES).map((bubble) => ({
        key: eventKey("bubble", bubble.id),
        ttlMs: VOXEL_BUBBLE_TTL_MS,
      })),
      ...sceneWorld.moveTrails.slice(0, MAX_ACTIVE_MOVE_TRAILS).map((trail) => ({
        key: eventKey("move", trail.id),
        ttlMs: VOXEL_MOVE_TRAIL_TTL_MS,
      })),
    ];
    const unseenCandidates = visibleCandidates.filter(
      (candidate) => !seenKeysRef.current.has(candidate.key),
    );

    seenKeysRef.current = new Set([
      ...sceneWorld.bubbles.map((bubble) => eventKey("bubble", bubble.id)),
      ...sceneWorld.moveTrails.map((trail) => eventKey("move", trail.id)),
    ]);
    if (unseenCandidates.length === 0) return;

    setActiveKeys((current) => {
      const next = new Set(current);
      unseenCandidates.forEach((candidate) => next.add(candidate.key));
      return next;
    });

    unseenCandidates.forEach((candidate) => {
      const timer = setTimeout(() => {
        setActiveKeys((current) => {
          if (!current.has(candidate.key)) return current;
          const next = new Set(current);
          next.delete(candidate.key);
          return next;
        });
        timersRef.current.delete(candidate.key);
      }, candidate.ttlMs);
      timersRef.current.set(candidate.key, timer);
    });
  }, [sceneWorld.bubbles, sceneWorld.moveTrails, sceneWorld.runId]);

  useEffect(
    () => () => {
      timersRef.current.forEach((timer) => clearTimeout(timer));
      timersRef.current.clear();
    },
    [],
  );

  return useMemo(
    () => ({
      bubbles: sceneWorld.bubbles
        .slice(0, MAX_ACTIVE_BUBBLES)
        .filter((bubble) => activeKeys.has(eventKey("bubble", bubble.id))),
      moveTrails: sceneWorld.moveTrails
        .slice(0, MAX_ACTIVE_MOVE_TRAILS)
        .filter((trail) => activeKeys.has(eventKey("move", trail.id))),
    }),
    [activeKeys, sceneWorld.bubbles, sceneWorld.moveTrails],
  );
}

function eventKey(kind: "bubble" | "move", id: string): string {
  return `${kind}:${id}`;
}
