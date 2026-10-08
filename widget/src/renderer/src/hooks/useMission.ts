import { useEffect, useState } from 'react'
import { readMission, type MissionBundle } from '../lib/api'
import { supabase } from '../lib/supabase'

export function useMission(missionId: string | null) {
  const [bundle, setBundle] = useState<MissionBundle | null>(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    if (!missionId) return
    let stop = false
    const refresh = () => {
      readMission(missionId)
        .then((next) => {
          if (!stop) setBundle(next)
        })
        .catch(() => undefined)
    }
    refresh()
    const timer = window.setInterval(refresh, 1500)
    return () => {
      stop = true
      window.clearInterval(timer)
    }
  }, [missionId])

  useEffect(() => {
    const client = supabase
    if (!missionId || !client) return
    const channel = client
      .channel(`mission-${missionId}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'concepts', filter: `mission_id=eq.${missionId}` },
        () => setConnected(true),
      )
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'world_state', filter: `mission_id=eq.${missionId}` },
        () => setConnected(true),
      )
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'agent_events', filter: `mission_id=eq.${missionId}` },
        () => setConnected(true),
      )
      .subscribe((status) => setConnected(status === 'SUBSCRIBED'))
    return () => {
      void client.removeChannel(channel)
    }
  }, [missionId])

  return { bundle, connected }
}
