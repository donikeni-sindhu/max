import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export type LiveCharacter = {
  animation: string
  speech: string
}

export function useCharacterState(userId: string | null, animation: string | null, speech: string) {
  const [live, setLive] = useState<LiveCharacter | null>(null)

  useEffect(() => {
    if (!animation) return
    setLive({ animation, speech })
  }, [animation, speech])

  useEffect(() => {
    const client = supabase
    if (!userId || !client) return
    const channel = client
      .channel(`character-${userId}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'character_state', filter: `user_id=eq.${userId}` },
        (payload) => {
          const row = payload.new as { animation?: string; speech?: string }
          if (!row.animation) return
          setLive({ animation: row.animation, speech: row.speech ?? '' })
        },
      )
      .subscribe()
    return () => {
      void client.removeChannel(channel)
    }
  }, [userId])

  return live
}
