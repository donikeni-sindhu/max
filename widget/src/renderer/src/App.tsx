import { useEffect, useState } from 'react'
import { Character } from './character/Character'
import { useCharacterMachine } from '../../character/useCharacterMachine'
import { AnimationTester } from '../../dev/AnimationTester'
import { BASE_FPS } from '../../character/animations.config'
import { useCharacterState } from './hooks/useCharacterState'
import { useMission } from './hooks/useMission'
import { cancelMission, createMission, DEMO_GOAL, executeCommand, listAppApprovals, replayMission, revokeAppApproval } from './lib/api'
import { signInAnonymously } from './lib/supabase'
import { chooseConfirm, ConfirmDialog, ResearchPath, Speech, startNext } from './ui/Panels'
import { isInteractiveTarget } from './ui/pointerTarget.mjs'

export function App() {
  const [userId, setUserId] = useState<string | null>(null)
  const [missionId, setMissionId] = useState<string | null>(null)
  const [asking, setAsking] = useState(false)
  const [goal, setGoal] = useState('')
  const [menu, setMenu] = useState(false)
  const [manageApps, setManageApps] = useState(false)
  const [approvedApps, setApprovedApps] = useState<string[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
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
      window.reborn?.setInteractive?.(isInteractiveTarget(hit))
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

  useEffect(() => {
    if (!menu || !manageApps) return
    // Refresh on open so the list reflects grants from this backend session, not stale widget state.
    void listAppApprovals().then(setApprovedApps).catch(() => setApprovedApps([]))
  }, [menu, manageApps])

  async function begin(nextGoal: string) {
    setError('')
    setNotice('')
    try {
      // Explicit browser commands bypass paper research; all other input keeps using the mission flow.
      const command = await executeCommand(nextGoal)
      if (command.handled) {
        setMissionId(null)
        setNotice(command.message ?? 'Command completed')
        setGoal('')
        setAsking(false)
        setMenu(false)
        return
      }
      const id = await createMission(nextGoal, userId ?? undefined)
      setMissionId(id)
      setAsking(false)
      setMenu(false)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Could not start')
    }
  }

  // Read approval state from mission data so later observer events cannot bury the prompt.
  const pendingConfirm = bundle?.world_state?.state.pending_confirmation ?? null

  return (
    <main className="stage">
      <button
        type="button"
        className="close-button"
        data-interactive="true"
        aria-label="Close REBORN"
        title="Close REBORN"
        onClick={() => window.reborn?.quit?.()}
      >
        ×
      </button>
      {demo ? (
        // The badge distinguishes canned demo responses from live research after the fallback path runs.
        <div className="demo-badge" role="status">DEMO MODE · Canned research responses</div>
      ) : null}
      <div className="ground">
        {character.speech ? <Speech text={character.speech} /> : null}
        <div
          data-interactive="true"
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
              What should I do?
              <input
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
                placeholder="Open YouTube or learn about transformers"
                autoFocus
              />
            </label>
            <button type="submit">Go</button>
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
            {missionId ? (
              // Expose cancellation in the same menu used to control a running mission.
              <button type="button" onClick={() => void cancelMission(missionId)}>
                Cancel mission
              </button>
            ) : null}
            <button type="button" onClick={() => setManageApps((value) => !value)}>
              {manageApps ? 'Hide app access' : 'App access'}
            </button>
            {manageApps ? (
              <section className="app-access" aria-label="Approved app access">
                {approvedApps.length ? approvedApps.map((appName) => (
                  <p key={appName}>
                    {appName} allowed this session
                    <button type="button" onClick={() => {
                      // Remove the backend grant first; update the visible list only after revocation succeeds.
                      void revokeAppApproval(appName).then(() => setApprovedApps((current) => current.filter((item) => item !== appName)))
                    }}>Revoke</button>
                  </p>
                )) : <p>No extra app access is approved.</p>}
              </section>
            ) : null}
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
        {notice ? <p className="speech" role="status">{notice}</p> : null}
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
      {bundle && missionId ? (
        <ResearchPath
          bundle={bundle}
          onNext={() => {
            if (missionId) void startNext(missionId)
          }}
        />
      ) : null}
      {pendingConfirm && missionId ? (
        <ConfirmDialog
          message={pendingConfirm}
          onChoose={(approved) => void chooseConfirm(missionId, approved)}
        />
      ) : null}
    </main>
  )
}
