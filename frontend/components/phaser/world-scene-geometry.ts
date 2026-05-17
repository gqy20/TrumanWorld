import type { SceneLocation } from "@/lib/world-scene-adapter";

import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  SCENE_PADDING_X,
  SCENE_PADDING_Y,
} from "./world-scene-style";

export type CanvasPoint = {
  x: number;
  y: number;
};

export function mapWorldToCanvas(
  x: number,
  y: number,
  locations: SceneLocation[],
): CanvasPoint {
  if (locations.length === 0) {
    return { x: CANVAS_WIDTH / 2, y: CANVAS_HEIGHT / 2 };
  }

  const xs = locations.map((location) => location.x);
  const ys = locations.map((location) => location.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = maxX - minX;
  const height = maxY - minY;
  const normalizedX = width === 0 ? 0.5 : (x - minX) / width;
  const normalizedY = height === 0 ? 0.5 : (y - minY) / height;

  return {
    x: SCENE_PADDING_X + normalizedX * (CANVAS_WIDTH - SCENE_PADDING_X * 2),
    y: SCENE_PADDING_Y + normalizedY * (CANVAS_HEIGHT - SCENE_PADDING_Y * 2),
  };
}

export function getAgentPosition(
  location: SceneLocation,
  slotIndex: number,
  locations: SceneLocation[],
): CanvasPoint {
  const center = mapWorldToCanvas(location.x, location.y, locations.length > 0 ? locations : [location]);
  const columns = 3;
  const col = slotIndex % columns;
  const row = Math.floor(slotIndex / columns);
  const offsetX = (col - 1) * 18;
  const offsetY = 34 + row * 18;

  return {
    x: center.x + offsetX,
    y: center.y + offsetY,
  };
}
