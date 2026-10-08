import type { AnimationName } from './manifest'

export const CANVAS = { width: 240, height: 248 } as const

export const BASE_FPS = 8
export const FPS_RANGE = { min: 4, max: 24 } as const

export const IDLE_WAIT_MS = { min: 3000, max: 8000 } as const
export const SLEEP_ELIGIBLE_MS = 30_000
export const SLEEP_FORCE_MS = 60_000
export const LONG_RESEARCH_MS = 20_000
export const PARTICLE_MS = 1400

export const ONE_SHOTS: readonly AnimationName[] = [
  'perk_up',
  'jump_happy',
  'lightbulb',
  'point',
  'celebrate',
  'wave',
  'cheer',
]

export function oneShotMs(fps: number): number {
  return Math.round((1000 / fps) * 6)
}

export function idleWaitMs(roll: number): number {
  return IDLE_WAIT_MS.min + Math.round(roll * (IDLE_WAIT_MS.max - IDLE_WAIT_MS.min))
}

export function isOneShot(name: AnimationName): boolean {
  return ONE_SHOTS.includes(name)
}

type IdlePick = { name: AnimationName; weight: number; afterMs: number }

const IDLE_WEIGHTS: readonly IdlePick[] = [
  { name: 'idle_blink', weight: 40, afterMs: 0 },
  { name: 'walk', weight: 25, afterMs: 0 },
  { name: 'sleep', weight: 10, afterMs: SLEEP_ELIGIBLE_MS },
  { name: 'peek', weight: 10, afterMs: 0 },
  { name: 'roll', weight: 5, afterMs: 0 },
  { name: 'stretch', weight: 10, afterMs: 0 },
]

export function pickIdle(elapsedMs: number, roll: number): AnimationName {
  const pool = IDLE_WEIGHTS.filter((item) => elapsedMs >= item.afterMs)
  const total = pool.reduce((sum, item) => sum + item.weight, 0)
  let cursor = roll * total
  for (const item of pool) {
    cursor -= item.weight
    if (cursor <= 0) return item.name
  }
  return 'idle_blink'
}

export type MotionPreset = {
  y?: number[]
  scaleY?: number[]
  rotate?: number[]
  duration: number
  repeat: number | 'infinite'
  mirror: boolean
}

export const MOTION: Record<string, MotionPreset> = {
  idle_sit: { scaleY: [1, 1.045, 1], duration: 1.8, repeat: 'infinite', mirror: true },
  idle_blink: { scaleY: [1, 0.94, 1], duration: 0.28, repeat: 'infinite', mirror: true },
  sleep: { scaleY: [1, 1.03, 1], duration: 2.6, repeat: 'infinite', mirror: true },
  loaf: { scaleY: [1, 1.03, 1], duration: 2.2, repeat: 'infinite', mirror: true },
  walk: { y: [0, -8, 0], duration: 0.36, repeat: 'infinite', mirror: true },
  walk_left: { y: [0, -8, 0], duration: 0.36, repeat: 'infinite', mirror: true },
  walk_right: { y: [0, -8, 0], duration: 0.32, repeat: 'infinite', mirror: true },
  run: { y: [0, -12, 0], duration: 0.22, repeat: 'infinite', mirror: true },
  walk_to_edge: { y: [0, -4, 0], rotate: [0, -4, 0], duration: 0.5, repeat: 'infinite', mirror: true },
  perk_up: { scaleY: [1, 1.14, 1], duration: 0.45, repeat: 0, mirror: false },
  jump_happy: { y: [0, -28, 0], duration: 0.55, repeat: 0, mirror: false },
  celebrate: { y: [0, -24, 0], rotate: [-4, 4, 0], duration: 0.6, repeat: 0, mirror: false },
  cheer: { y: [0, -20, 0], duration: 0.5, repeat: 0, mirror: false },
  wave: { rotate: [0, -10, 6, 0], duration: 0.6, repeat: 0, mirror: false },
  point: { rotate: [0, -8, 0], duration: 0.45, repeat: 0, mirror: false },
  lightbulb: { y: [0, -10, 0], scaleY: [1, 1.08, 1], duration: 0.5, repeat: 0, mirror: false },
  think: { rotate: [-2, 2, -2], duration: 1.4, repeat: 'infinite', mirror: true },
  dig: { rotate: [-6, 6, -6], duration: 0.28, repeat: 'infinite', mirror: true },
  dig2: { rotate: [4, -6, 4], duration: 0.32, repeat: 'infinite', mirror: true },
  confused: { rotate: [-7, 7, -7], duration: 0.4, repeat: 'infinite', mirror: true },
  heart: { scaleY: [1, 1.06, 1], duration: 0.7, repeat: 'infinite', mirror: true },
  cheeks: { scaleY: [1, 1.05, 1], duration: 0.8, repeat: 'infinite', mirror: true },
  smile: { scaleY: [1, 1.04, 1], duration: 1.2, repeat: 'infinite', mirror: true },
  playful: { rotate: [-4, 4, -4], duration: 0.6, repeat: 'infinite', mirror: true },
  roll: { rotate: [-8, 8, -8], duration: 0.7, repeat: 'infinite', mirror: true },
  stretch: { scaleY: [1, 1.08, 1], duration: 1.1, repeat: 'infinite', mirror: true },
  peek: { y: [8, 0, 8], duration: 1.2, repeat: 'infinite', mirror: true },
  eat: { rotate: [-2, 2, -2], duration: 0.45, repeat: 'infinite', mirror: true },
  scarf: { scaleY: [1, 1.04, 1], duration: 1.6, repeat: 'infinite', mirror: true },
  hood: { scaleY: [1, 1.03, 1], duration: 1.8, repeat: 'infinite', mirror: true },
  box: { y: [0, -3, 0], duration: 1.4, repeat: 'infinite', mirror: true },
  drag: { scaleY: [1.04, 1.08, 1.04], duration: 0.35, repeat: 'infinite', mirror: true },
  drop: { y: [-12, 18, -6, 0], scaleY: [1.08, 0.82, 1.06, 1], duration: 0.48, repeat: 0, mirror: false },
}

export const IDLE_FAMILY: readonly AnimationName[] = [
  'idle_sit',
  'idle_blink',
  'sleep',
  'walk',
  'walk_left',
  'walk_right',
  'peek',
  'roll',
  'stretch',
  'smile',
  'playful',
  'loaf',
  'cheeks',
]

export function isIdleFamily(name: AnimationName): boolean {
  return IDLE_FAMILY.includes(name)
}
