import type { AnimationName } from '../../../character/manifest'

export type CharacterState = {
  animation: AnimationName
  speech: string
  paused: boolean
  x: number
}

export type CharacterEvent =
  | { type: 'remote'; animation: string; speech: string }
  | { type: 'idle' }
  | { type: 'pause' }
  | { type: 'move'; x: number }

const IDLE: AnimationName[] = ['idle_sit', 'idle_blink', 'sleep', 'walk_left', 'walk_right']

const KNOWN = new Set<string>([
  'idle_sit',
  'idle_blink',
  'walk_left',
  'walk_right',
  'run',
  'sleep',
  'perk_up',
  'think',
  'lightbulb',
  'dig',
  'jump_happy',
  'celebrate',
  'confused',
  'walk_to_edge',
  'point',
])

export const initialCharacter: CharacterState = {
  animation: 'idle_sit',
  speech: '',
  paused: false,
  x: 0,
}

function asAnimation(name: string): AnimationName {
  return KNOWN.has(name) ? (name as AnimationName) : 'idle_sit'
}

export function reduceCharacter(state: CharacterState, event: CharacterEvent): CharacterState {
  if (event.type === 'pause') return { ...state, paused: !state.paused }
  if (event.type === 'move') return { ...state, x: event.x }
  if (state.paused) return state
  if (event.type === 'remote') {
    return { ...state, animation: asAnimation(event.animation), speech: event.speech }
  }
  const next = IDLE[Math.floor(Math.random() * IDLE.length)] ?? 'idle_sit'
  return { ...state, animation: next }
}
