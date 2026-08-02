import {
  advanceVoxelLocomotion,
  buildVoxelMotionPath,
  calculateVoxelAvoidanceOffset,
  calculateVoxelGaitStrength,
  calculateVoxelLookAheadDistance,
  calculateVoxelStridePhase,
  findNearestVoxelPathDistance,
  resolveVoxelJunctionSpeedScales,
  resolveVoxelWalkingSpeed,
  offsetVoxelMotionSample,
  sampleVoxelMotionPath,
  sampleVoxelMotionPathAtDistance,
} from "../agent-motion";

describe("voxel agent motion", () => {
  it("samples connected segments by travelled distance instead of segment count", () => {
    const path = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 1, y: 0, z: 0 },
      { x: 1, y: 0, z: 3 },
    ]);

    const midpoint = sampleVoxelMotionPath(path, 0.5);
    expect(path.totalLength).toBeCloseTo(3.94, 1);
    expect(midpoint.position.x).toBeCloseTo(1, 2);
    expect(midpoint.position.z).toBeCloseTo(1.05, 1);
    expect(midpoint.tangent.z).toBeGreaterThan(0.99);
  });

  it("rounds right-angle corners without leaving the road corridor", () => {
    const path = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 1, y: 0, z: 0 },
      { x: 1, y: 0, z: 1 },
    ]);

    expect(path.points.length).toBeGreaterThan(3);
    expect(path.points).not.toContainEqual({ x: 1, y: 0, z: 0 });
    expect(path.points.every((point) => point.x >= 0 && point.x <= 1)).toBe(true);
    expect(path.points.every((point) => point.z >= 0 && point.z <= 1)).toBe(true);
  });

  it("accelerates by physical distance and brakes before the destination", () => {
    const path = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 10, y: 0, z: 0 },
    ]);
    const started = advanceVoxelLocomotion(path, { distance: 0, speed: 0 }, 0.1, {
      maxSpeed: 1.5,
    });
    const braking = advanceVoxelLocomotion(path, { distance: 9.9, speed: 1.5 }, 0.1, {
      maxSpeed: 1.5,
    });

    expect(started.speed).toBeCloseTo(0.28);
    expect(started.distance).toBeCloseTo(0.014);
    expect(braking.speed).toBeLessThan(1.5);
    expect(braking.distance).toBeLessThanOrEqual(path.totalLength);
  });

  it("deduplicates adjacent points and clamps samples to the path endpoints", () => {
    const path = buildVoxelMotionPath([
      { x: 2, y: 0, z: 1 },
      { x: 2, y: 0, z: 1 },
      { x: 4, y: 0, z: 1 },
    ]);

    expect(path.points).toHaveLength(2);
    expect(sampleVoxelMotionPath(path, -1).position).toEqual({ x: 2, y: 0, z: 1 });
    expect(sampleVoxelMotionPath(path, 2).position).toEqual({ x: 4, y: 0, z: 1 });
  });

  it("ties gait phase and amplitude to travelled distance and velocity", () => {
    expect(calculateVoxelGaitStrength(0, 1.5)).toBe(0);
    expect(calculateVoxelGaitStrength(1.5, 1.5)).toBe(1);
    expect(calculateVoxelStridePhase(0.52)).toBeCloseTo(Math.PI * 2);
  });

  it("uses stable individual walking speeds and a bounded turn preview", () => {
    expect(resolveVoxelWalkingSpeed("agent-1")).toBe(resolveVoxelWalkingSpeed("agent-1"));
    expect(resolveVoxelWalkingSpeed("agent-1")).toBeGreaterThanOrEqual(1.35);
    expect(resolveVoxelWalkingSpeed("agent-1")).toBeLessThanOrEqual(1.65);
    expect(resolveVoxelWalkingSpeed("agent-1", 2)).toBeGreaterThanOrEqual(1.8);
    expect(resolveVoxelWalkingSpeed("agent-1", 2)).toBeLessThanOrEqual(2.2);
    expect(calculateVoxelLookAheadDistance(0)).toBe(0.14);
    expect(calculateVoxelLookAheadDistance(20)).toBe(0.4);
  });

  it("samples exact travelled distance and caps long frame gaps", () => {
    const path = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 4, y: 0, z: 0 },
    ]);
    expect(sampleVoxelMotionPathAtDistance(path, 1.25).position.x).toBeCloseTo(1.25);
    const normalFrame = advanceVoxelLocomotion(path, { distance: 0, speed: 0 }, 0.1, {
      maxSpeed: 1.5,
    });
    const backgroundTabFrame = advanceVoxelLocomotion(
      path,
      { distance: 0, speed: 0 },
      8,
      { maxSpeed: 1.5 },
    );
    expect(backgroundTabFrame).toEqual(normalFrame);
  });

  it("arrives without overshoot and settles at zero velocity", () => {
    const path = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 3, y: 0, z: 0 },
    ]);
    let state = { distance: 0, speed: 0 };
    const speeds: number[] = [];
    for (let frame = 0; frame < 300 && state.distance < path.totalLength; frame += 1) {
      state = advanceVoxelLocomotion(path, state, 1 / 60, { maxSpeed: 1.5 });
      speeds.push(state.speed);
    }

    expect(state.distance).toBe(path.totalLength);
    expect(state.speed).toBe(0);
    expect(Math.max(...speeds)).toBeGreaterThan(1.4);
    expect(speeds.at(-2)).toBeLessThan(0.5);
  });

  it("catches up to authoritative simulation progress without teleporting", () => {
    const path = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 5, y: 0, z: 0 },
    ]);
    const regular = advanceVoxelLocomotion(path, { distance: 1, speed: 1.4 }, 0.1, {
      maxSpeed: 1.5,
    });
    const catchingUp = advanceVoxelLocomotion(path, { distance: 1, speed: 1.4 }, 0.1, {
      authoritativeDistance: 3,
      maxSpeed: 1.5,
    });

    expect(catchingUp.distance).toBeGreaterThanOrEqual(regular.distance);
    expect(catchingUp.distance - 1).toBeLessThan(0.2);
  });

  it("fades lane and following offsets at entrances and keeps them on the road", () => {
    const path = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 0, y: 0, z: 4 },
    ]);
    const start = offsetVoxelMotionSample(
      path,
      0,
      sampleVoxelMotionPathAtDistance(path, 0),
      0.12,
      0.42,
    );
    const middle = offsetVoxelMotionSample(
      path,
      2,
      sampleVoxelMotionPathAtDistance(path, 2),
      0.12,
      0.42,
    );
    const end = offsetVoxelMotionSample(
      path,
      4,
      sampleVoxelMotionPathAtDistance(path, 4),
      0.12,
      0.42,
    );

    expect(start.position).toEqual({ x: 0, y: 0, z: 0 });
    expect(middle.position.x).toBeCloseTo(0.12);
    expect(middle.position.z).toBeCloseTo(1.58);
    expect(end.position).toEqual({ x: 0, y: 0, z: 4 });
  });

  it("releases following distance before lane offset when a group reaches an entrance", () => {
    const path = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 0, y: 0, z: 5 },
    ]);
    const nearEntrance = offsetVoxelMotionSample(
      path,
      4.25,
      sampleVoxelMotionPathAtDistance(path, 4.25),
      0.18,
      0.42,
    );

    expect(nearEntrance.position.x).toBeCloseTo(0.18);
    expect(nearEntrance.position.z).toBeGreaterThan(3.9);
  });

  it("projects junction markers onto the rounded path distance", () => {
    const path = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 2, y: 0, z: 0 },
      { x: 2, y: 0, z: 2 },
    ]);

    const distance = findNearestVoxelPathDistance(path, { x: 2, y: 0, z: 0 });
    const projected = sampleVoxelMotionPathAtDistance(path, distance).position;
    expect(projected.x).toBeGreaterThan(1.8);
    expect(projected.z).toBeLessThan(0.2);
  });

  it("gives one formation stable junction priority and lets the crossing party clear", () => {
    const approaching = [
      {
        agentId: "eastbound",
        distance: 1.4,
        formationId: "formation:b",
        junctions: [{ id: "junction:center", distance: 2 }],
      },
      {
        agentId: "northbound",
        distance: 1.4,
        formationId: "formation:a",
        junctions: [{ id: "junction:center", distance: 2 }],
      },
    ];
    const scales = resolveVoxelJunctionSpeedScales(approaching);
    expect(scales.get("northbound")).toBe(1);
    expect(scales.get("eastbound")).toBeLessThan(1);

    const crossing = resolveVoxelJunctionSpeedScales([
      approaching[1],
      { ...approaching[0], distance: 2.1 },
    ]);
    expect(crossing.get("eastbound")).toBe(1);
    expect(crossing.get("northbound")).toBeLessThan(1);
  });

  it("treats companions as one junction party instead of making them yield to each other", () => {
    const scales = resolveVoxelJunctionSpeedScales([
      {
        agentId: "friend-a",
        distance: 1.5,
        formationId: "friends",
        junctions: [{ id: "junction:center", distance: 2 }],
      },
      {
        agentId: "friend-b",
        distance: 1.1,
        formationId: "friends",
        junctions: [{ id: "junction:center", distance: 2 }],
      },
    ]);
    expect(scales).toEqual(new Map([
      ["friend-a", 1],
      ["friend-b", 1],
    ]));
  });

  it("produces bounded, symmetric local avoidance without affecting distant residents", () => {
    const origin = { x: 0, y: 0, z: 0 };
    const first = calculateVoxelAvoidanceOffset("a", origin, [{ id: "b", position: origin }]);
    const second = calculateVoxelAvoidanceOffset("b", origin, [{ id: "a", position: origin }]);
    const distant = calculateVoxelAvoidanceOffset("a", origin, [
      { id: "b", position: { x: 2, y: 0, z: 0 } },
    ]);

    expect(first.x).toBeCloseTo(-second.x);
    expect(first.z).toBeCloseTo(-second.z);
    expect(Math.hypot(first.x, first.z)).toBeLessThanOrEqual(0.1);
    expect(distant).toEqual({ x: 0, y: 0, z: 0 });
  });

  it("puts opposing pedestrians on opposite physical sides of the road", () => {
    const forward = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 0, y: 0, z: 4 },
    ]);
    const reverse = buildVoxelMotionPath([
      { x: 0, y: 0, z: 4 },
      { x: 0, y: 0, z: 0 },
    ]);
    const forwardPosition = offsetVoxelMotionSample(
      forward,
      2,
      sampleVoxelMotionPathAtDistance(forward, 2),
      0.09,
      0,
    ).position;
    const reversePosition = offsetVoxelMotionSample(
      reverse,
      2,
      sampleVoxelMotionPathAtDistance(reverse, 2),
      0.09,
      0,
    ).position;

    expect(forwardPosition.x).toBeCloseTo(0.09);
    expect(reversePosition.x).toBeCloseTo(-0.09);
  });
});
