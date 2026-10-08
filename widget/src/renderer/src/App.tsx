import { useEffect, useState } from 'react'
import { Character } from './character/Character'
import { useCharacterMachine } from '../../character/useCharacterMachine'
import { AnimationTester } from '../../dev/AnimationTester'
import { BASE_FPS } from '../../character/animations.config'
import { useCharacterState } from './hooks/useCharacterState'
import { useMission } from './hooks/useMission'
import { createMission, DEMO_GOAL, replayMission } from './lib/api'
import { signInAnonymously } from './lib/supabase'
import { chooseConfirm, ResearchPath, Speech, startNext } from './ui/Panels'

export function App() {
  const [userId, setUserId] = useState<string | null>(null)
  const [missionId, setMissionId] = useState<string | null>(null)
  const [asking, setAsking] = useState(false)
  const [goal, setGoal] = useState('')
  const [menu, setMenu] = useState(false)
  const [error, setError] = useState('')
  const { bundle } = useMission(missionId)
  const remote = useCharacterState(
    userId,
    bundle?.character?.animation ?? null,
    bundle?.character?.speech ?? '',
  )
  const character = useCharacterMachine(remote)
  const demo = import.meta.env.VITE_DEMO_MODE === 'true'

  useEffect(() => {
    void signInAnonymously().then((id) => setUserId(id))
  }, [])

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      const hit = document.elementFromPoint(event.clientX, event.clientY)
      window.reborn?.setInteractive?.(Boolean(hit?.closest('[data-interactive]')))
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'd') {
        event.preventDefault()
        void begin(DEMO_GOAL)
      }
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('keydown', onKey)
    }
  }, [userId])

  async function begin(nextGoal: string) {
    setError('')
    try {
      const id = await createMission(nextGoal, userId ?? undefined)
      setMissionId(id)
      setAsking(false)
      setMenu(false)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Could not start')
    }
  }

  const pendingConfirm = bundle?.events.at(-1)?.type === 'confirm_needed' ? bundle.events.at(-1) : null

  return (
    <main className="stage">
      <div className="ground">
        {character.speech ? <Speech text={character.speech} /> : null}
        <div
          onClick={() => setAsking(true)}
          onContextMenu={(event) => {
            event.preventDefault()
            setMenu(true)
          }}
        >
          <Character
            animation={character.animation}
            flipX={character.flipX}
            x={character.x}
            playId={character.playId}
            oneshot={character.oneshot}
            dropping={character.dropping}
            dragging={character.dragging}
            fps={character.fps}
            onClipDone={character.onClipDone}
            onLanded={character.onLanded}
            onDragStart={character.onDragStart}
            onDragEnd={character.onDragEnd}
          />
        </div>
        {asking ? (
          <form
            className="ask"
            data-interactive="true"
            onSubmit={(event) => {
              event.preventDefault()
              void begin(goal)
            }}
          >
            <label>
              What do you want to learn?
              <input value={goal} onChange={(event) => setGoal(event.target.value)} autoFocus />
            </label>
            <button type="submit">Start</button>
          </form>
        ) : null}
        {menu ? (
          <nav className="menu" data-interactive="true">
            <button type="button" onClick={() => character.togglePause()}>
              {character.paused ? 'Resume' : 'Pause'}
            </button>
            <button type="button" onClick={() => void begin(DEMO_GOAL)}>
              Demo mode
            </button>
            <button
              type="button"
              onClick={() => {
                if (missionId) void replayMission(missionId)
              }}
            >
              Replay
            </button>
            <button type="button" onClick={() => window.reborn?.quit?.()}>
              Quit
            </button>
          </nav>
        ) : null}
        {error ? <p className="speech">{error}</p> : null}
      </div>
      {demo ? (
        <AnimationTester
          names={character.names}
          fps={character.fps ?? BASE_FPS}
          randomIdle={character.randomIdle}
          onPlay={character.play}
          onFps={character.setFps}
          onRandom={character.setRandomIdle}
        />
      ) : null}
      {bundle ? (
        <ResearchPath
          bundle={bundle}
          onNext={() => {
            if (missionId) void startNext(missionId)
          }}
        />
      ) : null}
      {pendingConfirm && missionId ? (
        <div className="modal">
          {pendingConfirm.message}
          <button type="button" onClick={() => void chooseConfirm(missionId, true)}>
            Approve
          </button>
          <button type="button" onClick={() => void chooseConfirm(missionId, false)}>
            Reject
          </button>
        </div>
      ) : null}
    </main>
  )
}
