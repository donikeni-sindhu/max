import { useEffect, useState } from 'react'
import type { WorldStateData } from '../types/database'
import { confirmMission, nextConcept, type MissionBundle } from '../lib/api'

export function ResearchPath({
  bundle,
  onNext,
}: {
  bundle: MissionBundle
  onNext: () => void
}) {
  const [openState, setOpenState] = useState(false)
  const [debug, setDebug] = useState(false)
  const state = bundle.world_state?.state
  const summary = state?.summary
  const latest = bundle.events.at(-1)

  return (
    <section className="panel" data-interactive="true">
      <header>
        <strong>{bundle.mission.target_title ?? 'Research path'}</strong>
        <span className="chip">{latest?.message ?? bundle.mission.status}</span>
      </header>
      <ol className="path">
        {bundle.concepts.map((concept, index) => (
          <li key={concept.id} className={concept.status}>
            {index > 0 ? <span className="arrow">↓</span> : null}
            <span>
              {concept.name}
              <small> level {concept.level}</small>
            </span>
          </li>
        ))}
      </ol>
      <button type="button" onClick={onNext}>
        Start next concept
      </button>
      <button type="button" className="ghost" onClick={() => setOpenState((value) => !value)}>
        {openState ? 'Hide world state' : 'World state'}
      </button>
      {openState && state ? <WorldStateView state={state} /> : null}
      <button type="button" className="ghost" onClick={() => setDebug((value) => !value)}>
        {debug ? 'Hide debug' : 'Debug'}
      </button>
      {debug ? <DebugLog bundle={bundle} /> : null}
      {bundle.mission.status === 'complete' && summary ? (
        <article className="complete">
          <h2>Research Mission Complete</h2>
          <p>{summary.resources_explored} resources explored</p>
          <p>{summary.concepts_identified} concepts identified</p>
          <p>{summary.ready_to_read ? 'Ready to read the paper.' : 'Still learning.'}</p>
        </article>
      ) : null}
    </section>
  )
}

function WorldStateView({ state }: { state: WorldStateData }) {
  const view = {
    goal: state.goal,
    active_window: state.active_window ?? null,
    browser: state.browser,
    ui_summary: state.ui_summary ?? null,
    prerequisites: state.prerequisites,
    current_knowledge: state.current_knowledge,
    summary: state.summary ?? null,
  }
  return <pre>{JSON.stringify(view, null, 2)}</pre>
}

function DebugLog({ bundle }: { bundle: MissionBundle }) {
  const [compact, setCompact] = useState('')
  useEffect(() => {
    void fetch(`${import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000'}/debug/uia/snapshot`)
      .then((response) => response.json())
      .then((body: { compact?: string }) => setCompact(body.compact ?? ''))
      .catch(() => setCompact(''))
  }, [bundle.events.length])
  return (
    <div className="debug">
      <ul>
        {bundle.events.slice(-8).map((event) => (
          <li key={event.id}>
            {event.type}: {event.message}
          </li>
        ))}
      </ul>
      <pre>{compact || 'No UIA snapshot'}</pre>
    </div>
  )
}

export function Speech({ text }: { text: string }) {
  const [shown, setShown] = useState('')
  useEffect(() => {
    if (!text) {
      setShown('')
      return
    }
    let index = 0
    setShown('')
    const typer = window.setInterval(() => {
      index += 1
      setShown(text.slice(0, index))
      if (index >= text.length) window.clearInterval(typer)
    }, 18)
    const hide = window.setTimeout(() => setShown(''), 4000 + text.length * 18)
    return () => {
      window.clearInterval(typer)
      window.clearTimeout(hide)
    }
  }, [text])
  if (!shown) return null
  return (
    <p className="speech" data-interactive="true">
      {shown}
    </p>
  )
}

export function ConfirmDialog({
  message,
  onChoose,
}: {
  message: string
  onChoose: (approved: boolean) => void
}) {
  return (
    <div className="confirm" data-interactive="true" role="dialog">
      <p>{message}</p>
      <button type="button" onClick={() => onChoose(true)}>
        Approve
      </button>
      <button type="button" className="ghost" onClick={() => onChoose(false)}>
        Reject
      </button>
    </div>
  )
}

export async function chooseConfirm(missionId: string, approved: boolean) {
  await confirmMission(missionId, approved)
}

export async function startNext(missionId: string) {
  await nextConcept(missionId)
}
