import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

export function loadEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return {}
  const values = {}
  const text = fs.readFileSync(filePath, 'utf8')
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue
    const eq = trimmed.indexOf('=')
    if (eq === -1) continue
    const key = trimmed.slice(0, eq).trim()
    let value = trimmed.slice(eq + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    values[key] = value
  }
  return values
}

export function runtimeEnv() {
  const fromFile = loadEnvFile(path.join(root, '.env'))
  const port = process.env.BACKEND_PORT || fromFile.BACKEND_PORT || '8000'
  return {
    root,
    port,
    env: {
      ...process.env,
      ...fromFile,
      BACKEND_PORT: port,
      VITE_BACKEND_URL:
        process.env.VITE_BACKEND_URL ||
        fromFile.VITE_BACKEND_URL ||
        `http://127.0.0.1:${port}`,
      VITE_SUPABASE_URL: process.env.VITE_SUPABASE_URL || fromFile.VITE_SUPABASE_URL || fromFile.SUPABASE_URL || '',
      VITE_SUPABASE_ANON_KEY:
        process.env.VITE_SUPABASE_ANON_KEY ||
        fromFile.VITE_SUPABASE_ANON_KEY ||
        fromFile.SUPABASE_ANON_KEY ||
        '',
    },
  }
}
