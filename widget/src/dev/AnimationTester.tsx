import { FPS_RANGE } from '../character/animations.config'
import type { AnimationName } from '../character/manifest'

type TesterProps = {
  names: readonly AnimationName[]
  fps: number
  randomIdle: boolean
  onPlay: (name: AnimationName) => void
  onFps: (fps: number) => void
  onRandom: (on: boolean) => void
}

export function AnimationTester({ names, fps, randomIdle, onPlay, onFps, onRandom }: TesterProps) {
  return (
    <section className="tester" data-interactive="true">
      <div className="tester-row">
        {names.map((name) => (
          <button key={name} type="button" onClick={() => onPlay(name)}>
            {name}
          </button>
        ))}
      </div>
      <label className="tester-fps">
        fps {fps}
        <input
          type="range"
          min={FPS_RANGE.min}
          max={FPS_RANGE.max}
          value={fps}
          onChange={(event) => onFps(Number(event.target.value))}
        />
      </label>
      <label className="tester-fps">
        <input
          type="checkbox"
          checked={randomIdle}
          onChange={(event) => onRandom(event.target.checked)}
        />
        random idle
      </label>
    </section>
  )
}
