import { useCallback, useEffect, useReducer } from 'react'
import {
  IDLE_FAMILY,
  LONG_RESEARCH_MS,
  SLEEP_FORCE_MS,
  idleWaitMs,
  isIdleFamily,
  isOneShot,
  pickIdle,
} from './animations.config'
import { animationNames, type AnimationName } from './manifest'
import type { LiveCharacter } from '../renderer/src/hooks/useCharacterState'

export type { AnimationName }

type Step = { anim: AnimationName; flip: boolean; reveal: boolean }
type Phase = 'idle' | 'oneshot' | 'hold' | 'drag' | 'drop'

type Machine = {
  animation: AnimationName
  flipX: boolean
  phase: Phase
  x: number
  playId: number
  queue: Step[]
  pendingSpeech: string
  visibleSpeech: string
  randomIdle: boolean
  fps: number | null
  paused: boolean
  offline: boolean
  forcedSleep: boolean
  researchEat: boolean
  lastEvent: number
  holdStarted: number
}

type Action =
  | { type: 'remote'; animation: string; speech: string; now: number }
  | { type: 'done'; now: number }
  | { type: 'idle-tick'; now: number; roll: number; side: 'left' | 'right' }
  | { type: 'clock'; now: number }
  | { type: 'drag-start'; now: number }
  | { type: 'drag-end'; offset: number; now: number }
  | { type: 'landed' }
  | { type: 'play'; name: AnimationName; now: number; side: 'left' | 'right' }
  | { type: 'fps'; fps: number }
  | { type: 'random'; on: boolean }
  | { type: 'pause' }
  | { type: 'offline'; value: boolean }

const KNOWN = new Set<string>(animationNames)

function asName(value: string): AnimationName {
  return KNOWN.has(value) ? (value as AnimationName) : 'idle_sit'
}

function flipFor(name: AnimationName, side: 'left' | 'right'): boolean {
  if (name === 'walk') return side === 'right'
  if (name === 'walk_right' || name === 'run') return true
  return false
}

function phaseFor(name: AnimationName): Phase {
  if (isOneShot(name)) return 'oneshot'
  if (isIdleFamily(name)) return 'idle'
  return 'hold'
}

function createMachine(now: number): Machine {
  return {
    animation: 'idle_sit',
    flipX: false,
    phase: 'idle',
    x: 0,
    playId: 1,
    queue: [],
    pendingSpeech: '',
    visibleSpeech: '',
    randomIdle: true,
    fps: null,
    paused: false,
    offline: false,
    forcedSleep: false,
    researchEat: false,
    lastEvent: now,
    holdStarted: now,
  }
}

function speak(state: Machine, anim: AnimationName, speech: string, flip: boolean, now: number): Machine {
  const queue: Step[] =
    anim === 'perk_up'
      ? [{ anim: 'perk_up', flip: false, reveal: true }]
      : [
          { anim: 'perk_up', flip: false, reveal: false },
          { anim, flip, reveal: true },
        ]
  return {
    ...state,
    animation: 'peek',
    flipX: false,
    phase: 'oneshot',
    queue,
    pendingSpeech: speech,
    playId: state.playId + 1,
    forcedSleep: false,
    researchEat: false,
    lastEvent: now,
    holdStarted: now,
  }
}

function playNow(state: Machine, anim: AnimationName, flip: boolean, now: number, speech = ''): Machine {
  return {
    ...state,
    animation: anim,
    flipX: flip,
    phase: phaseFor(anim),
    queue: [],
    pendingSpeech: '',
    visibleSpeech: speech,
    playId: state.playId + 1,
    forcedSleep: false,
    researchEat: false,
    lastEvent: now,
    holdStarted: now,
  }
}

function reduce(state: Machine, action: Action): Machine {
  if (action.type === 'fps') return { ...state, fps: action.fps }
  if (action.type === 'random') return { ...state, randomIdle: action.on }
  if (action.type === 'offline') return { ...state, offline: action.value }
  if (action.type === 'pause') return { ...state, paused: !state.paused }
  if (action.type === 'landed') {
    if (state.phase !== 'drop') return state
    return { ...state, phase: 'idle', animation: 'idle_sit', flipX: false, playId: state.playId + 1 }
  }
  if (action.type === 'drag-start') {
    if (state.paused) return state
    return {
      ...state,
      phase: 'drag',
      animation: 'perk_up',
      flipX: false,
      forcedSleep: false,
      lastEvent: action.now,
      playId: state.playId + 1,
    }
  }
  if (action.type === 'drag-end') {
    if (state.phase !== 'drag') return state
    return {
      ...state,
      phase: 'drop',
      x: state.x + action.offset,
      lastEvent: action.now,
      playId: state.playId + 1,
    }
  }
  if (action.type === 'clock') {
    const digging =
      state.phase === 'hold' &&
      (state.animation === 'dig' || state.animation === 'dig2') &&
      action.now - state.holdStarted >= LONG_RESEARCH_MS
    if (digging && !state.researchEat) return { ...state, researchEat: true }
    if (state.forcedSleep || state.paused || state.phase !== 'idle') return state
    if (action.now - state.lastEvent < SLEEP_FORCE_MS) return state
    return { ...state, animation: 'sleep', flipX: false, forcedSleep: true, playId: state.playId + 1 }
  }
  if (action.type === 'idle-tick') {
    if (!state.randomIdle || state.paused || state.offline || state.forcedSleep || state.phase !== 'idle') {
      return state
    }
    const picked = pickIdle(action.now - state.lastEvent, action.roll)
    return {
      ...state,
      animation: picked,
      flipX: picked === 'walk' && action.side === 'right',
      playId: state.playId + 1,
    }
  }
  if (action.type === 'play') {
    return playNow(state, action.name, flipFor(action.name, action.side), action.now)
  }
  if (action.type === 'done') {
    if (state.phase !== 'oneshot') return state
    const [step, ...rest] = state.queue
    if (!step) {
      return {
        ...state,
        animation: 'idle_sit',
        flipX: false,
        phase: 'idle',
        queue: [],
        playId: state.playId + 1,
      }
    }
    return {
      ...state,
      animation: step.anim,
      flipX: step.flip,
      queue: rest,
      phase: phaseFor(step.anim),
      visibleSpeech: step.reveal ? state.pendingSpeech : state.visibleSpeech,
      pendingSpeech: step.reveal ? '' : state.pendingSpeech,
      playId: state.playId + 1,
      holdStarted: action.now,
      researchEat: false,
    }
  }
  if (state.paused) return state
  const anim = asName(action.animation)
  const flip = flipFor(anim, 'left')
  if (state.forcedSleep && !action.speech) {
    return {
      ...playNow(state, 'perk_up', false, action.now),
      queue: [{ anim, flip, reveal: false }],
      phase: 'oneshot',
    }
  }
  if (action.speech) return speak(state, anim, action.speech, flip, action.now)
  return playNow(state, anim, flip, action.now)
}

function shown(state: Machine): AnimationName {
  if (state.phase === 'drag') return 'perk_up'
  if (state.paused && state.phase !== 'drop') return 'hood'
  if (state.researchEat && (state.animation === 'dig' || state.animation === 'dig2')) return 'eat'
  if (state.offline && state.phase === 'idle') return 'box'
  return state.animation
}

export function useCharacterMachine(remote: LiveCharacter | null) {
  const [state, dispatch] = useReducer(reduce, Date.now(), createMachine)

  useEffect(() => {
    if (!remote?.animation) return
    dispatch({ type: 'remote', animation: remote.animation, speech: remote.speech, now: Date.now() })
  }, [remote?.animation, remote?.speech])

  useEffect(() => {
    if (!state.randomIdle || state.paused || state.offline || state.forcedSleep || state.phase !== 'idle') return
    const wait = idleWaitMs(Math.random())
    const timer = window.setTimeout(() => {
      dispatch({
        type: 'idle-tick',
        now: Date.now(),
        roll: Math.random(),
        side: Math.random() < 0.5 ? 'right' : 'left',
      })
    }, wait)
    return () => window.clearTimeout(timer)
  }, [state.randomIdle, state.paused, state.offline, state.forcedSleep, state.phase, state.animation, state.playId])

  useEffect(() => {
    const timer = window.setInterval(() => dispatch({ type: 'clock', now: Date.now() }), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    const base = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'
    let stop = false
    const ping = () => {
      fetch(`${base}/health`)
        .then((response) => {
          if (!stop) dispatch({ type: 'offline', value: !response.ok })
        })
        .catch(() => {
          if (!stop) dispatch({ type: 'offline', value: true })
        })
    }
    ping()
    const timer = window.setInterval(ping, 5000)
    return () => {
      stop = true
      window.clearInterval(timer)
    }
  }, [])

  const onClipDone = useCallback(() => dispatch({ type: 'done', now: Date.now() }), [])
  const onLanded = useCallback(() => dispatch({ type: 'landed' }), [])
  const onDragStart = useCallback(() => dispatch({ type: 'drag-start', now: Date.now() }), [])
  const onDragEnd = useCallback((offset: number) => {
    dispatch({ type: 'drag-end', offset, now: Date.now() })
  }, [])
  const play = useCallback((name: AnimationName) => {
    dispatch({
      type: 'play',
      name,
      now: Date.now(),
      side: Math.random() < 0.5 ? 'right' : 'left',
    })
  }, [])
  const setFps = useCallback((fps: number) => dispatch({ type: 'fps', fps }), [])
  const setRandomIdle = useCallback((on: boolean) => dispatch({ type: 'random', on }), [])
  const togglePause = useCallback(() => dispatch({ type: 'pause' }), [])

  const animation = shown(state)
  return {
    animation,
    flipX: animation === 'walk' ? state.flipX : flipFor(animation, 'left'),
    x: state.x,
    playId: state.playId,
    oneshot: state.phase === 'oneshot',
    dropping: state.phase === 'drop',
    dragging: state.phase === 'drag',
    fps: state.fps,
    speech: state.visibleSpeech,
    paused: state.paused,
    randomIdle: state.randomIdle,
    names: animationNames,
    onClipDone,
    onLanded,
    onDragStart,
    onDragEnd,
    play,
    setFps,
    setRandomIdle,
    togglePause,
    idleNames: IDLE_FAMILY,
  }
}
