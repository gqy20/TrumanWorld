import type { SceneLocation } from "@/lib/world-scene-adapter";

import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
} from "./world-scene-style";
import { getTownEntrancePoint, getTownLocationPoint } from "./town-layout";

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

  const matchingLocation = locations.find((location) => location.x === x && location.y === y);
  return matchingLocation
    ? getTownLocationPoint(matchingLocation, locations)
    : { x: CANVAS_WIDTH / 2, y: CANVAS_HEIGHT / 2 };
}

export function getAgentPosition(
  location: SceneLocation,
  slotIndex: number,
  locations: SceneLocation[],
): CanvasPoint {
  const center = getTownEntrancePoint(location, locations.length > 0 ? locations : [location]);
  const columns = 4;
  const col = slotIndex % columns;
  const row = Math.floor(slotIndex / columns);
  const offsetX = -24 + col * 16 + row * 6;
  const offsetY = 34 + row * 18;

  return {
    x: center.x + offsetX,
    y: center.y + offsetY,
  };
}
