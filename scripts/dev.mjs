import { spawn } from 'node:child_process'
import { runtimeEnv } from './env.mjs'

const { root, env } = runtimeEnv()

const backend = spawn(process.execPath, ['scripts/backend.mjs'], {
  cwd: root,
  env,
  stdio: 'inherit',
})

const widget = spawn('npm run dev --prefix widget', {
  cwd: root,
  env,
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
