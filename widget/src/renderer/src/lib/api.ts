const backendUrl = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000'

export const DEMO_GOAL = "I want to understand the paper 'Attention Is All You Need'"

// Centralizing requests prevents one UI feature from accidentally omitting the launch credential.
export function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  headers.set('X-REBORN-Token', window.reborn?.token || import.meta.env.VITE_REBORN_TOKEN || '')
  return fetch(input, { ...init, headers })
}

// A separate endpoint lets the backend recognize navigation without turning it into a learning mission.
export async function executeCommand(command: string): Promise<{ handled: boolean; message?: string }> {
  const response = await apiFetch(`${backendUrl}/commands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command }),
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? 'Could not run command')
  }
  return (await response.json()) as { handled: boolean; message?: string }
}

export async function createMission(goal: string, userId?: string): Promise<string> {
  const response = await apiFetch(`${backendUrl}/missions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal, user_id: userId }),
  })
  if (!response.ok) throw new Error(`Could not start mission (${response.status})`)
  const body = (await response.json()) as { id: string }
  return body.id
}

export async function nextConcept(missionId: string): Promise<void> {
  const response = await apiFetch(`${backendUrl}/missions/${missionId}/next`, { method: 'POST' })
  if (!response.ok) throw new Error('Could not open the next concept')
}

export async function replayMission(missionId: string): Promise<void> {
  await apiFetch(`${backendUrl}/missions/${missionId}/replay`, { method: 'POST' })
}

export async function cancelMission(missionId: string): Promise<void> {
  // The request flips the server-side event checked immediately before any next UI action.
  const response = await apiFetch(`${backendUrl}/missions/${missionId}/cancel`, { method: 'POST' })
  if (!response.ok) throw new Error('Could not cancel mission')
}

export async function confirmMission(missionId: string, approved: boolean): Promise<void> {
  await apiFetch(`${backendUrl}/missions/${missionId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved }),
  })
}

/** Read non-browser app grants from this backend session so users can inspect temporary access. */
export async function listAppApprovals(): Promise<string[]> {
  const response = await apiFetch(`${backendUrl}/permissions/apps`)
  if (!response.ok) throw new Error('Could not read app access')
  const body = (await response.json()) as { apps: string[] }
  return body.apps
}

/** Revoke an app's session-only interaction grant while keeping the default browser policy intact. */
export async function revokeAppApproval(appName: string): Promise<void> {
  const response = await apiFetch(`${backendUrl}/permissions/apps/${encodeURIComponent(appName)}`, { method: 'DELETE' })
  if (!response.ok) throw new Error('Could not revoke app access')
}

export async function readMission(missionId: string): Promise<MissionBundle> {
  const response = await apiFetch(`${backendUrl}/missions/${missionId}`)
  if (!response.ok) throw new Error('Mission not found')
  return (await response.json()) as MissionBundle
}

export async function readSnapshot(): Promise<{ compact: string; window?: { title?: string } }> {
  const response = await apiFetch(`${backendUrl}/debug/uia/snapshot`)
  if (!response.ok) return { compact: '' }
  return (await response.json()) as { compact: string; window?: { title?: string } }
}

export type MissionBundle = {
  mission: {
    id: string
    status: string
    goal: string
    target_title: string | null
  }
  concepts: Array<{
    id: string
    name: string
    status: 'pending' | 'active' | 'done'
    explanation: string
    order_index: number
    level: number
  }>
  resources: Array<{ id: string; title: string; url: string; concept_id: string | null }>
  world_state: { state: import('../types/database').WorldStateData } | null
  events: Array<{ id: number; type: string; message: string; created_at: string }>
  character: { animation: string; speech: string; mood: string } | null
}
