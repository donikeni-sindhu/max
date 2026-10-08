import { BASE_FPS } from './animations.config'
import box from '../assets/character/box.png'
import celebrate from '../assets/character/celebrate.png'
import cheeks from '../assets/character/cheeks.png'
import cheer from '../assets/character/cheer.png'
import confused from '../assets/character/confused.png'
import dig from '../assets/character/dig.png'
import dig2 from '../assets/character/dig2.png'
import eat from '../assets/character/eat.png'
import heart from '../assets/character/heart.png'
import hood from '../assets/character/hood.png'
import idleBlink from '../assets/character/idle_blink.png'
import idleSit from '../assets/character/idle_sit.png'
import jumpHappy from '../assets/character/jump_happy.png'
import lightbulb from '../assets/character/lightbulb.png'
import loaf from '../assets/character/loaf.png'
import peek from '../assets/character/peek.png'
import perkUp from '../assets/character/perk_up.png'
import playful from '../assets/character/playful.png'
import point from '../assets/character/point.png'
import roll from '../assets/character/roll.png'
import scarf from '../assets/character/scarf.png'
import sleep from '../assets/character/sleep.png'
import smile from '../assets/character/smile.png'
import stretch from '../assets/character/stretch.png'
import think from '../assets/character/think.png'
import walk from '../assets/character/walk.png'
import walkToEdge from '../assets/character/walk_to_edge.png'
import wave from '../assets/character/wave.png'

export type AnimationName =
  | 'idle_sit'
  | 'idle_blink'
  | 'perk_up'
  | 'jump_happy'
  | 'celebrate'
  | 'sleep'
  | 'walk'
  | 'walk_left'
  | 'walk_right'
  | 'run'
  | 'think'
  | 'lightbulb'
  | 'dig'
  | 'dig2'
  | 'confused'
  | 'walk_to_edge'
  | 'point'
  | 'wave'
  | 'cheer'
  | 'heart'
  | 'cheeks'
  | 'roll'
  | 'box'
  | 'loaf'
  | 'stretch'
  | 'eat'
  | 'scarf'
  | 'hood'
  | 'peek'
  | 'smile'
  | 'playful'

export type FrameClip = {
  frames: string[]
  fps: number
  loop: boolean
  flipX?: boolean
  anchor: { x: number; y: number }
}

const anchor = { x: 0.5, y: 1 } as const

function pose(src: string, loop: boolean, fps = BASE_FPS, flipX = false): FrameClip {
  return { frames: [src], fps, loop, flipX, anchor }
}

export const characterManifest: Record<AnimationName, FrameClip> = {
  idle_sit: pose(idleSit, true),
  idle_blink: pose(idleBlink, true),
  perk_up: pose(perkUp, false),
  jump_happy: pose(jumpHappy, false),
  celebrate: pose(celebrate, false),
  sleep: pose(sleep, true, 4),
  walk: pose(walk, true, 10),
  walk_left: pose(walk, true, 10, false),
  walk_right: pose(walk, true, 10, true),
  run: pose(walk, true, 16, true),
  think: pose(think, true),
  lightbulb: pose(lightbulb, false),
  dig: pose(dig, true, 10),
  dig2: pose(dig2, true, 10),
  confused: pose(confused, true),
  walk_to_edge: pose(walkToEdge, true, 10),
  point: pose(point, false),
  wave: pose(wave, false),
  cheer: pose(cheer, false),
  heart: pose(heart, true),
  cheeks: pose(cheeks, true),
  roll: pose(roll, true),
  box: pose(box, true),
  loaf: pose(loaf, true, 4),
  stretch: pose(stretch, true),
  eat: pose(eat, true),
  scarf: pose(scarf, true),
  hood: pose(hood, true),
  peek: pose(peek, true),
  smile: pose(smile, true),
  playful: pose(playful, true),
}

export const animationNames = Object.keys(characterManifest) as AnimationName[]

export function clipFor(name: string): FrameClip | null {
  if (name in characterManifest) return characterManifest[name as AnimationName]
  return null
}
