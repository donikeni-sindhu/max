const backendUrl = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000'

export const DEMO_GOAL = "I want to understand the paper 'Attention Is All You Need'"

export async function createMission(goal: string, userId?: string): Promise<string> {
  const response = await fetch(`${backendUrl}/missions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal, user_id: userId }),
  })
  if (!response.ok) throw new Error(`Could not start mission (${response.status})`)
  const body = (await response.json()) as { id: string }
  return body.id
}

export async function nextConcept(missionId: string): Promise<void> {
  const response = await fetch(`${backendUrl}/missions/${missionId}/next`, { method: 'POST' })
  if (!response.ok) throw new Error('Could not open the next concept')
}

export async function replayMission(missionId: string): Promise<void> {
  await fetch(`${backendUrl}/missions/${missionId}/replay`, { method: 'POST' })
}

export async function confirmMission(missionId: string, approved: boolean): Promise<void> {
  await fetch(`${backendUrl}/missions/${missionId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved }),
  })
}

export async function readMission(missionId: string): Promise<MissionBundle> {
  const response = await fetch(`${backendUrl}/missions/${missionId}`)
  if (!response.ok) throw new Error('Mission not found')
  return (await response.json()) as MissionBundle
}

export async function readSnapshot(): Promise<{ compact: string; window?: { title?: string } }> {
  const response = await fetch(`${backendUrl}/debug/uia/snapshot`)
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
