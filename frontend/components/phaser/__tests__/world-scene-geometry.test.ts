import type { SceneLocation } from "@/lib/world-scene-adapter";

import { getAgentPosition, mapWorldToCanvas } from "../world-scene-geometry";
import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  SCENE_PADDING_X,
  SCENE_PADDING_Y,
} from "../world-scene-style";

function location(id: string, x: number, y: number): SceneLocation {
  return {
    id,
    name: id,
    locationType: "plaza",
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

  it("maps world coordinate bounds into padded canvas coordinates", () => {
    const locations = [location("left", 0, 0), location("right", 10, 20)];

    expect(mapWorldToCanvas(0, 0, locations)).toEqual({
      x: SCENE_PADDING_X,
      y: SCENE_PADDING_Y,
    });
    expect(mapWorldToCanvas(10, 20, locations)).toEqual({
      x: CANVAS_WIDTH - SCENE_PADDING_X,
      y: CANVAS_HEIGHT - SCENE_PADDING_Y,
    });
  });

  it("centers axes that have no world span", () => {
    const locations = [location("a", 5, 0), location("b", 5, 10)];

    expect(mapWorldToCanvas(5, 5, locations)).toEqual({
      x: CANVAS_WIDTH / 2,
      y: CANVAS_HEIGHT / 2,
    });
  });

  it("places agents in three columns below their location", () => {
    const locations = [location("home", 0, 0), location("office", 10, 10)];

    expect(getAgentPosition(locations[0], 0, locations)).toEqual({
      x: SCENE_PADDING_X - 18,
      y: SCENE_PADDING_Y + 34,
    });
    expect(getAgentPosition(locations[0], 3, locations)).toEqual({
      x: SCENE_PADDING_X - 18,
      y: SCENE_PADDING_Y + 52,
    });
  });
});
