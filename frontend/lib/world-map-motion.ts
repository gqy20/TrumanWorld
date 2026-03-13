export type HeatGlowMotionProps = {
  initial: {
    opacity: number;
    scale: number;
  };
  animate: {
    opacity: [number, number, number];
    scale: [number, number, number];
  };
  transition: {
    duration: number;
    repeat: number;
    ease: "easeInOut";
  };
};

export type HeatRingMotionProps = {
  initial: {
    opacity: number;
    rotate: number;
  };
  animate: {
    opacity: number;
    rotate: number;
  };
  transition: {
    rotate: {
      duration: number;
      repeat: number;
      ease: "linear";
    };
    opacity: {
      duration: number;
    };
  };
};

export function buildHeatGlowMotionProps(nodeHeat: number): HeatGlowMotionProps {
  const opacity: [number, number, number] = [
    0.4 + nodeHeat * 0.3,
    0.6 + nodeHeat * 0.3,
    0.4 + nodeHeat * 0.3,
  ];

  return {
    initial: {
      opacity: opacity[0],
      scale: 1,
    },
    animate: {
      opacity,
      scale: [1, 1.05, 1],
    },
    transition: {
      duration: 3 - nodeHeat,
      repeat: Infinity,
      ease: "easeInOut",
    },
  };
}

export function buildHeatRingMotionProps(nodeHeat: number): HeatRingMotionProps {
  const opacity = 0.6 + nodeHeat * 0.4;

  return {
    initial: {
      opacity,
      rotate: 0,
    },
    animate: {
      opacity,
      rotate: 360,
    },
    transition: {
      rotate: { duration: 20, repeat: Infinity, ease: "linear" },
      opacity: { duration: 0.5 },
    },
  };
}
