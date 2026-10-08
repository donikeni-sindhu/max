import { spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { runtimeEnv } from './env.mjs'

const { root, env } = runtimeEnv()
// Mint a fresh credential per launcher session; never put it in .env or a checked-in file.
const launchToken = randomBytes(32).toString('hex')
env.REBORN_TOKEN = launchToken
env.VITE_REBORN_TOKEN = launchToken

const backend = spawn(process.execPath, ['scripts/backend.mjs'], {
  cwd: root,
  env,
  stdio: 'inherit',
})

const widgetEnv = { ...env }
// The widget only needs VITE-prefixed public settings plus its launch token; do not copy server
// credentials into Electron's process environment where renderer tooling can inspect them.
for (const secretName of ['GROQ_API_KEY', 'SUPABASE_SERVICE_ROLE_KEY']) {
  delete widgetEnv[secretName]
}

const widget = spawn('npm run dev --prefix widget', {
  cwd: root,
  env: widgetEnv,
  stdio: 'inherit',
  shell: true,
})

let shuttingDown = false

function shutdown() {
  if (shuttingDown) return
  shuttingDown = true
  for (const child of [backend, widget]) {
    if (!child.pid || child.killed) continue
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], { stdio: 'ignore' })
    } else {
      child.kill('SIGTERM')
    }
  }
}

process.on('SIGINT', () => {
  shutdown()
  process.exit(0)
})
process.on('SIGTERM', () => {
  shutdown()
  process.exit(0)
})

for (const child of [backend, widget]) {
  child.on('exit', (code, signal) => {
    if (shuttingDown) return
    if (signal || (code && code !== 0)) {
      shutdown()
      process.exit(code ?? 1)
    }
  })
}
