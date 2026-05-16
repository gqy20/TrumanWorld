import {
  getAgentMarker,
  getArrowAngleDegrees,
  getConfiguredAgentTextureKey,
  getConfiguredLocationTextureKey,
  getLocationGlyph,
  getStagePalette,
  mergeStagePalette,
  parseRgbaColor,
} from "../world-scene-style";

describe("world scene style helpers", () => {
  it("parses rgb and rgba colors into Phaser numeric colors", () => {
    expect(parseRgbaColor("rgb(15, 23, 42)")).toBe(0x0f172a);
    expect(parseRgbaColor("rgba(220, 252, 231, 0.8)")).toBe(0xdcfce7);
    expect(parseRgbaColor("not-a-color")).toBe(0xffffff);
  });

  it("resolves semantic glyphs, markers, and texture keys", () => {
    expect(getLocationGlyph("cafe")).toBe("C");
    expect(getLocationGlyph("unknown")).toBe("L");
    expect(getAgentMarker("talking")).toBe("~");
    expect(getAgentMarker("idle")).toBe(".");
    expect(getConfiguredLocationTextureKey("shop", "cafe")).toBe("pixel-building-shop-cafe");
    expect(getConfiguredAgentTextureKey("default", "moving")).toBe("pixel-agent-default-moving");
  });

  it("merges configured stage palette values over the theme fallback", () => {
    const fallback = getStagePalette("campus_night");
    expect(mergeStagePalette(fallback, { headerColor: "rgb(14, 165, 233)" })).toEqual({
      ...fallback,
      headerColor: 0x0ea5e9,
    });
  });

  it("computes arrow angle in degrees from two points", () => {
    expect(getArrowAngleDegrees(0, 0, 10, 0)).toBe(90);
    expect(getArrowAngleDegrees(0, 0, 0, 10)).toBe(180);
  });
});
