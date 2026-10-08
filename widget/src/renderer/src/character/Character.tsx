import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  characterManifest,
  isSheetClip,
  type AnimationName,
} from '../../../character/manifest'

type CharacterProps = {
  animation: AnimationName
  x: number
  onDragX: (x: number) => void
}

export function Character({ animation, x, onDragX }: CharacterProps) {
  const clip = characterManifest[animation]
  const [frame, setFrame] = useState(0)

  useEffect(() => {
    if (!clip) return
    const count = isSheetClip(clip) ? clip.frames : clip.frames.length
    if (count <= 1) return
    const timer = window.setInterval(() => {
      setFrame((current) => (clip.loop ? (current + 1) % count : Math.min(current + 1, count - 1)))
    }, 1000 / clip.fps)
    return () => window.clearInterval(timer)
  }, [clip])

  return (
    <motion.div
      className={`actor anim-${animation}`}
      data-interactive="true"
      animate={motionFor(animation)}
      transition={{ duration: animation === 'dig' ? 0.12 : 0.8, repeat: Infinity, repeatType: 'mirror', ease: 'easeInOut' }}
      style={{ x }}
      drag="x"
      dragMomentum={false}
      onDragEnd={(_event, info) => onDragX(x + info.offset.x)}
    >
      {clip && isSheetClip(clip) ? (
        <div
          className="sheet"
          style={{
            backgroundImage: `url(${clip.sheet})`,
            width: clip.frameWidth,
            height: clip.frameHeight,
            backgroundPositionX: -frame * clip.frameWidth,
          }}
        />
      ) : null}
      {clip && !isSheetClip(clip) ? (
        <img className="frame" src={clip.frames[frame] ?? clip.frames[0]} alt="" />
      ) : null}
      {!clip ? <Placeholder animation={animation} /> : null}
    </motion.div>
  )
}

function Placeholder({ animation }: { animation: AnimationName }) {
  return (
    <div className="blob">
      <span className="eye left" />
      <span className="eye right" />
      {animation === 'think' ? <span className="bubble-mini">...</span> : null}
      {animation === 'lightbulb' ? <span className="bulb" /> : null}
      {animation === 'sleep' ? <span className="zzz">z</span> : null}
      {animation === 'confused' ? <span className="mark">?</span> : null}
      {animation === 'celebrate' ? (
        <span className="confetti" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      ) : null}
    </div>
  )
}

function motionFor(animation: AnimationName) {
  if (animation === 'idle_sit' || animation === 'sleep') return { scale: [1, 1.05, 1] }
  if (animation === 'idle_blink') return { scaleY: [1, 0.92, 1] }
  if (animation === 'perk_up') return { scaleY: [1, 1.18, 1] }
  if (animation === 'dig') return { x: [-6, 6, -6] }
  if (animation === 'jump_happy' || animation === 'celebrate') return { y: [0, -28, 0] }
  if (animation === 'confused') return { rotate: [-6, 6, -6] }
  if (animation === 'point' || animation === 'walk_to_edge') return { rotate: [0, -8, 0], x: [0, 24, 0] }
  if (animation === 'walk_left') return { y: [0, -6, 0], scaleX: -1 }
  if (animation === 'walk_right' || animation === 'run') return { y: [0, -8, 0] }
  return { scale: [1, 1.04, 1] }
}
