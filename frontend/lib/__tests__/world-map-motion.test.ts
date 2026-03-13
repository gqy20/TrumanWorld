import { buildHeatGlowMotionProps, buildHeatRingMotionProps } from '@/lib/world-map-motion'

describe('world map motion helpers', () => {
  it('defines initial opacity for heat glow animations', () => {
    const motion = buildHeatGlowMotionProps(0.5)

    expect(motion.initial).toEqual({
      opacity: [0.55, 0.75, 0.55][0],
      scale: 1,
    })
    expect(motion.animate.opacity).toEqual([0.55, 0.75, 0.55])
  })

  it('defines initial opacity for heat ring animations', () => {
    const motion = buildHeatRingMotionProps(0.5)

    expect(motion.initial).toEqual({
      opacity: 0.8,
      rotate: 0,
    })
    expect(motion.animate.opacity).toBe(0.8)
    expect(motion.animate.rotate).toBe(360)
  })
})
