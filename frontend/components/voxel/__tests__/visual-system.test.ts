import { resolveWorldLightingProfile, WORLD_V2_PALETTE } from "../visual-system";
import {
  getVoxelMaterialClass,
  VOXEL_MATERIAL_CLASS_SPECS,
  VOXEL_MATERIAL_SPECS,
} from "../materials";

describe("3D V2 visual system", () => {
  it("uses the approved palette tokens", () => {
    expect(WORLD_V2_PALETTE).toMatchObject({
      moss: "#667C5B",
      brick: "#A45345",
      ember: "#D86F45",
      limewash: "#E7E7E1",
      night: "#172338",
    });
  });

  it("moves from a bright day exposure to a restrained night exposure", () => {
    const day = resolveWorldLightingProfile("noon");
    const night = resolveWorldLightingProfile("night");

    expect(day.exposure).toBeGreaterThan(night.exposure);
    expect(day.sunIntensity).toBeGreaterThan(night.sunIntensity);
    expect(night.windowEmissiveIntensity).toBeGreaterThan(day.windowEmissiveIntensity);
    expect(night.background).toBe(WORLD_V2_PALETTE.night);
  });

  it("keeps windows subdued by day and gently lit at the edges of the day", () => {
    const dawn = resolveWorldLightingProfile("dawn");
    const noon = resolveWorldLightingProfile("noon");
    const evening = resolveWorldLightingProfile("evening");

    expect(dawn.windowEmissiveIntensity).toBeGreaterThan(noon.windowEmissiveIntensity);
    expect(evening.windowEmissiveIntensity).toBeGreaterThan(dawn.windowEmissiveIntensity);
    expect(evening.windowEmissiveIntensity).toBeLessThan(1);
  });

  it("defaults safely when old scene data has no time period", () => {
    expect(resolveWorldLightingProfile()).toEqual(resolveWorldLightingProfile("noon"));
  });

  it("batches ordinary colors into one matte material class", () => {
    expect(getVoxelMaterialClass("grass")).toBe("matte");
    expect(getVoxelMaterialClass("roofRed")).toBe("matte");
    expect(getVoxelMaterialClass("wallWarm")).toBe("matte");
    expect(VOXEL_MATERIAL_CLASS_SPECS.matte.color).toBe(0xffffff);
    expect(VOXEL_MATERIAL_SPECS.grass.color).not.toBe(VOXEL_MATERIAL_SPECS.roofRed.color);
  });

  it("keeps rendering-sensitive materials in dedicated classes", () => {
    expect(getVoxelMaterialClass("glass")).toBe("glass");
    expect(getVoxelMaterialClass("water")).toBe("water");
    expect(getVoxelMaterialClass("highlight")).toBe("emissive");
    expect(VOXEL_MATERIAL_CLASS_SPECS.glass.emissiveIntensity).toBeGreaterThan(0);
  });
});
