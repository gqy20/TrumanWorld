import type { SceneLocation } from "@/lib/world-scene-adapter";

import { getAgentPosition, mapWorldToCanvas } from "../world-scene-geometry";
import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  ISO_ORIGIN_X,
  ISO_ORIGIN_Y,
  ISO_TILE_HEIGHT,
  ISO_TILE_WIDTH,
} from "../world-scene-style";

function location(id: string, x: number, y: number, locationType = "plaza"): SceneLocation {
  return {
    id,
    name: id,
    locationType,
    visual: {},
    x,
    y,
    capacity: 4,
    occupantCount: 0,
    heat: 0,
  };
}

describe("world scene geometry helpers", () => {
  it("maps empty worlds to the canvas center", () => {
    expect(mapWorldToCanvas(10, 20, [])).toEqual({
      x: CANVAS_WIDTH / 2,
      y: CANVAS_HEIGHT / 2,
    });
  });

  it("maps location types into fixed town districts instead of raw coordinate bounds", () => {
    const locations = [location("central", 0, 0, "plaza"), location("cafe", 10, 20, "cafe")];

    expect(mapWorldToCanvas(0, 0, locations)).toEqual({
      x: ISO_ORIGIN_X,
      y: ISO_ORIGIN_Y + ISO_TILE_HEIGHT * 3,
    });
    expect(mapWorldToCanvas(10, 20, locations)).toEqual({
      x: ISO_ORIGIN_X - ISO_TILE_WIDTH * 1.5,
      y: ISO_ORIGIN_Y + ISO_TILE_HEIGHT * 4.5,
    });
  });

  it("falls back to the canvas center for unknown raw coordinates", () => {
    const locations = [location("a", 5, 0), location("b", 5, 10)];

    expect(mapWorldToCanvas(99, 99, locations)).toEqual({
      x: CANVAS_WIDTH / 2,
      y: CANVAS_HEIGHT / 2,
    });
  });

  it("places agents in four columns below their location", () => {
    const locations = [location("home", 0, 0, "home"), location("office", 10, 10, "office")];

    expect(getAgentPosition(locations[0], 0, locations)).toEqual({
      x: ISO_ORIGIN_X - ISO_TILE_WIDTH * 2 - 20,
      y: ISO_ORIGIN_Y + ISO_TILE_HEIGHT * 3 + 32,
    });
    expect(getAgentPosition(locations[0], 4, locations)).toEqual({
      x: ISO_ORIGIN_X - ISO_TILE_WIDTH * 2 - 17,
      y: ISO_ORIGIN_Y + ISO_TILE_HEIGHT * 3 + 43,
    });
  });
});
