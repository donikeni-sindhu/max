import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase: SupabaseClient | null = url && key ? createClient(url, key) : null

export async function signInAnonymously(): Promise<string | null> {
  if (!supabase) return null
  const existing = await supabase.auth.getSession()
  if (existing.data.session?.user.id) return existing.data.session.user.id
  const { data, error } = await supabase.auth.signInAnonymously()
  if (error || !data.session) return null
  return data.session.user.id
}
