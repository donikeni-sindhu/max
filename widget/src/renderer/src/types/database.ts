export type MissionStatus =
  | 'created'
  | 'planning'
  | 'researching'
  | 'learning'
  | 'complete'
  | 'failed'
  | 'cancelled'

export type ConceptStatus = 'pending' | 'active' | 'done'
export type ConceptLevel = 1 | 2 | 3

export const DEMO_USER_ID = '11111111-1111-4111-8111-111111111111'
export const DEMO_MISSION_ID = '22222222-2222-4222-8222-222222222222'

export type BrowserState = {
  open: boolean
  url: string | null
  title: string | null
  tab: string | null
  tabs?: string[]
  active_tab?: string | null
}

export type ActiveWindow = {
  title: string | null
  process: string | null
  pid: number | null
}

export type UiSummary = {
  element_count: number
  key_elements: string[]
}

export type MissionSummary = {
  resources_explored: number
  concepts_identified: number
  ready_to_read: boolean
}

export type TargetPaper = {
  title: string | null
  url: string | null
}

export type PdfState = {
  url: string | null
  title: string | null
}

export type WorldResource = {
  title: string
  url: string
  source: string | null
  score: number | null
  selected: boolean
}

export type WorldStateData = {
  goal: string
  active_window?: ActiveWindow
  browser: BrowserState
  target_paper: TargetPaper
  pdf: PdfState
  current_knowledge: string
  prerequisites: string[]
  resources: WorldResource[]
  ui_summary?: UiSummary
  summary?: MissionSummary | null
  pending_confirmation?: string | null
}

export type Profile = {
  id: string
  display_name: string | null
  created_at: string
}

export type Mission = {
  id: string
  user_id: string
  goal: string
  target_title: string | null
  status: MissionStatus
  created_at: string
  updated_at: string
}

export type WorldState = {
  mission_id: string
  state: WorldStateData
  updated_at: string
}

export type Concept = {
  id: string
  mission_id: string
  name: string
  level: ConceptLevel
  explanation: string
  order_index: number
  status: ConceptStatus
}

export type Resource = {
  id: string
  mission_id: string
  concept_id: string | null
  title: string
  url: string
  source: string | null
  score: number | null
  selected: boolean
}

export type AgentEvent = {
  id: number
  mission_id: string
  type: string
  message: string
  payload: Record<string, unknown>
  created_at: string
}

export type CharacterState = {
  user_id: string
  mood: string
  animation: string
  speech: string
  updated_at: string
}

export type Database = {
  public: {
    Tables: {
      profiles: { Row: Profile }
      missions: { Row: Mission }
      world_state: { Row: WorldState }
      concepts: { Row: Concept }
      resources: { Row: Resource }
      agent_events: { Row: AgentEvent }
      character_state: { Row: CharacterState }
    }
  }
}
