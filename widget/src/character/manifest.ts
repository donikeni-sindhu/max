export type AnimationName =
  | 'idle_sit'
  | 'idle_blink'
  | 'walk_left'
  | 'walk_right'
  | 'run'
  | 'sleep'
  | 'perk_up'
  | 'think'
  | 'lightbulb'
  | 'dig'
  | 'jump_happy'
  | 'celebrate'
  | 'confused'
  | 'walk_to_edge'
  | 'point'

export type FrameClip = {
  frames: string[]
  fps: number
  loop: boolean
  anchor?: { x: number; y: number }
}

export type SheetClip = {
  sheet: string
  frameWidth: number
  frameHeight: number
  frames: number
  fps: number
  loop: boolean
  anchor?: { x: number; y: number }
}

export const characterManifest: Record<AnimationName, FrameClip | SheetClip | null> = {
  idle_sit: null,
  idle_blink: null,
  walk_left: null,
  walk_right: null,
  run: null,
  sleep: null,
  perk_up: null,
  think: null,
  lightbulb: null,
  dig: null,
  jump_happy: null,
  celebrate: null,
  confused: null,
  walk_to_edge: null,
  point: null,
}

export function isSheetClip(clip: FrameClip | SheetClip): clip is SheetClip {
  return 'sheet' in clip
}
