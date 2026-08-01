import { resolveAgentAppearance } from "../agent-appearance";

describe("voxel agent appearance", () => {
  it("keeps an agent visually stable across renders", () => {
    expect(resolveAgentAppearance("agent-alice")).toEqual(resolveAgentAppearance("agent-alice"));
  });

  it("gives a cast more than one curated silhouette and palette", () => {
    const appearances = ["alice", "bob", "carol", "dave", "eve"].map(resolveAgentAppearance);
    expect(new Set(appearances.map((appearance) => appearance.torso)).size).toBeGreaterThan(1);
    expect(new Set(appearances.map((appearance) => appearance.accessory)).size).toBeGreaterThan(1);
  });
});
