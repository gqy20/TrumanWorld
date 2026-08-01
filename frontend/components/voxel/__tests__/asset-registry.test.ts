import { readFileSync } from "node:fs";
import path from "node:path";

import {
  getReadyWorldAsset,
  resolveReadyWorldAsset,
  WORLD_ASSET_REGISTRY,
} from "../asset-registry";

describe("golden-slice asset registry", () => {
  it("has unique ids and valid glTF paths", () => {
    const ids = WORLD_ASSET_REGISTRY.map((asset) => asset.id);

    expect(new Set(ids).size).toBe(ids.length);
    expect(WORLD_ASSET_REGISTRY.every((asset) => asset.uri.endsWith(".glb"))).toBe(true);
    expect(WORLD_ASSET_REGISTRY.every((asset) => asset.maxTriangles > 0)).toBe(true);
  });

  it("serves only ready assets to matching locations", () => {
    expect(getReadyWorldAsset("cafe.corner")?.status).toBe("ready");
    expect(resolveReadyWorldAsset("cafe")?.id).toBe("cafe.corner");
    expect(resolveReadyWorldAsset("home")?.id).toBe("home.row");
    expect(resolveReadyWorldAsset("park")?.id).toBe("park.old-oak");
    expect(resolveReadyWorldAsset("unknown")).toBeNull();
    expect(getReadyWorldAsset("civic.clock")).toBeNull();
  });

  it("ships a valid and compact binary glTF for every ready asset", () => {
    const readyAssets = WORLD_ASSET_REGISTRY.filter((asset) => asset.status === "ready");

    expect(readyAssets.length).toBeGreaterThan(0);
    for (const asset of readyAssets) {
      const file = readFileSync(path.join(process.cwd(), "public", asset.uri.slice(1)));
      expect(file.subarray(0, 4).toString("ascii")).toBe("glTF");
      expect(file.readUInt32LE(4)).toBe(2);
      expect(file.byteLength).toBeLessThan(1_000_000);
    }
  });
});
