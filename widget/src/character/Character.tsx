import { useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  BASE_FPS,
  CANVAS,
  MOTION,
  PARTICLE_MS,
  oneShotMs,
  type MotionPreset,
} from './animations.config'
import { characterManifest, type AnimationName } from './manifest'

type CharacterProps = {
  animation: AnimationName
  flipX: boolean
  x: number
  playId: number
  oneshot: boolean
  dropping: boolean
  dragging: boolean
  fps: number | null
  onClipDone: () => void
  onLanded: () => void
  onDragStart: () => void
  onDragEnd: (offset: number) => void
}

export function Character({
  animation,
  flipX,
  x,
  playId,
  oneshot,
  dropping,
  dragging,
  fps,
  onClipDone,
  onLanded,
  onDragStart,
  onDragEnd,
}: CharacterProps) {
  const clip = characterManifest[animation]
  const rate = fps ?? clip.fps ?? BASE_FPS
  const preset = dragging ? MOTION.drag : dropping ? MOTION.drop : (MOTION[animation] ?? MOTION.idle_sit)
  const duration = oneshot ? oneShotMs(rate) / 1000 : preset.duration

  useEffect(() => {
    if (!oneshot) return
    const timer = window.setTimeout(onClipDone, oneShotMs(rate))
    return () => window.clearTimeout(timer)
  }, [oneshot, playId, rate, onClipDone])

  return (
    <motion.div
      className="actor"
      data-interactive="true"
      style={{ x, width: CANVAS.width, height: CANVAS.height }}
      drag="x"
      dragMomentum={false}
      onDragStart={onDragStart}
      onDragEnd={(_event, info) => onDragEnd(info.offset.x)}
    >
      <motion.div
        className="sprite"
        animate={animateOf(preset)}
        transition={{
          duration,
          repeat: preset.repeat === 'infinite' ? Infinity : preset.repeat,
          repeatType: preset.mirror ? 'mirror' : undefined,
          ease: 'easeInOut',
        }}
        style={{ scaleX: flipX ? -1 : 1, transformOrigin: 'bottom center' }}
        onAnimationComplete={() => {
          if (dropping) onLanded()
        }}
      >
        <img
          className="frame"
          src={clip.frames[0]}
          width={CANVAS.width}
          height={CANVAS.height}
          alt=""
          draggable={false}
        />
      </motion.div>
      <Particles animation={animation} />
    </motion.div>
  )
}

function animateOf(preset: MotionPreset) {
  return {
    y: preset.y ?? 0,
    scaleY: preset.scaleY ?? 1,
    rotate: preset.rotate ?? 0,
  }
}

function Particles({ animation }: { animation: AnimationName }) {
  const style = { ['--particle-ms' as string]: `${PARTICLE_MS}ms` }
  if (animation === 'sleep') return <span className="particle zzz" style={style}>z</span>
  if (animation === 'confused') return <span className="particle mark" style={style}>?</span>
  if (animation === 'think' || animation === 'dig' || animation === 'dig2') {
    return <span className="particle dots" style={style}>...</span>
  }
  if (animation === 'celebrate' || animation === 'cheer' || animation === 'jump_happy') {
    return (
      <span className="particle confetti" style={style} aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
    )
  }
  if (animation === 'heart' || animation === 'cheeks') return <span className="particle heart" style={style}>♥</span>
  if (animation === 'lightbulb' || animation === 'playful') {
    return <span className="particle spark" style={style}>✦</span>
  }
  return null
}
