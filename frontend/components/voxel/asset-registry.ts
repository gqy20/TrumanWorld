export type WorldAssetKind = "building" | "character" | "landmark" | "prop" | "vegetation";
export type WorldAssetStatus = "planned" | "ready";

export type WorldAssetDefinition = {
  id: string;
  kind: WorldAssetKind;
  uri: `/world/${string}.glb`;
  status: WorldAssetStatus;
  fallbackPrefab: string;
  maxTriangles: number;
  variants: readonly string[];
  locationTypes?: readonly string[];
  visualPresets?: readonly string[];
  authoredSize: { width: number; depth: number };
  scaleTo: "footprint" | "plot";
};

/** Golden-slice contract. Planned entries never trigger a network request. */
export const WORLD_ASSET_REGISTRY: readonly WorldAssetDefinition[] = [
  {
    id: "cafe.corner",
    kind: "building",
    uri: "/world/buildings/cafe-corner.glb",
    status: "ready",
    fallbackPrefab: "cafe",
    maxTriangles: 18_000,
    variants: ["limewash", "brick"],
    locationTypes: ["cafe"],
    visualPresets: ["cafe"],
    authoredSize: { width: 1.5, depth: 1.4 },
    scaleTo: "footprint",
  },
  {
    id: "home.row",
    kind: "building",
    uri: "/world/buildings/home-row.glb",
    status: "ready",
    fallbackPrefab: "home",
    maxTriangles: 14_000,
    variants: ["moss", "slate", "brick"],
    locationTypes: ["home", "dorm", "apartment"],
    visualPresets: ["home", "house", "dorm", "apartment"],
    authoredSize: { width: 1.5, depth: 1.4 },
    scaleTo: "footprint",
  },
  {
    id: "office.midrise",
    kind: "building",
    uri: "/world/buildings/office-midrise.glb",
    status: "ready",
    fallbackPrefab: "office",
    maxTriangles: 18_000,
    variants: ["moss", "slate"],
    locationTypes: ["office", "tower"],
    visualPresets: ["office", "tower"],
    authoredSize: { width: 1.42, depth: 1.42 },
    scaleTo: "footprint",
  },
  {
    id: "clinic.corner",
    kind: "building",
    uri: "/world/buildings/clinic-corner.glb",
    status: "ready",
    fallbackPrefab: "hospital",
    maxTriangles: 16_000,
    variants: ["limewash", "moss"],
    locationTypes: ["hospital", "clinic"],
    visualPresets: ["hospital", "clinic"],
    authoredSize: { width: 1.47, depth: 1.47 },
    scaleTo: "footprint",
  },
  {
    id: "park.old-oak",
    kind: "vegetation",
    uri: "/world/vegetation/old-oak.glb",
    status: "ready",
    fallbackPrefab: "green",
    maxTriangles: 7_500,
    variants: ["summer"],
    locationTypes: ["park", "grove", "quad"],
    visualPresets: ["park", "grove", "quad"],
    authoredSize: { width: 1.8, depth: 1.8 },
    scaleTo: "plot",
  },
  { id: "civic.clock", kind: "landmark", uri: "/world/landmarks/civic-clock.glb", status: "planned", fallbackPrefab: "clock", maxTriangles: 8_000, variants: ["brick"], authoredSize: { width: 1, depth: 1 }, scaleTo: "footprint" },
  { id: "street.furniture", kind: "prop", uri: "/world/props/street-furniture.glb", status: "planned", fallbackPrefab: "street", maxTriangles: 6_000, variants: ["bench", "lamp", "bicycle", "sign"], authoredSize: { width: 1, depth: 1 }, scaleTo: "footprint" },
  { id: "resident.base", kind: "character", uri: "/world/characters/resident-base.glb", status: "planned", fallbackPrefab: "agent", maxTriangles: 9_000, variants: ["adult-a", "adult-b", "adult-c"], authoredSize: { width: 1, depth: 1 }, scaleTo: "footprint" },
] as const;

export function getReadyWorldAsset(id: string): WorldAssetDefinition | null {
  return WORLD_ASSET_REGISTRY.find((asset) => asset.id === id && asset.status === "ready") ?? null;
}

export function resolveReadyWorldAsset(
  locationType: string,
  visualPreset?: string,
): WorldAssetDefinition | null {
  const normalizedType = locationType.toLowerCase();
  const normalizedPreset = visualPreset?.toLowerCase();
  return (
    WORLD_ASSET_REGISTRY.find(
      (asset) =>
        asset.status === "ready" &&
        (asset.locationTypes?.includes(normalizedType) ||
          (normalizedPreset && asset.visualPresets?.includes(normalizedPreset))),
    ) ?? null
  );
}
