import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { runtimeEnv } from './env.mjs'

const { root, port, env } = runtimeEnv()
const backendDir = path.join(root, 'backend')
const venvPython =
  process.platform === 'win32'
    ? path.join(backendDir, '.venv', 'Scripts', 'python.exe')
    : path.join(backendDir, '.venv', 'bin', 'python')
const python = fs.existsSync(venvPython) ? venvPython : 'python'

const child = spawn(
  python,
  ['-m', 'uvicorn', 'app.main:app', '--reload', '--host', '127.0.0.1', '--port', port],
  {
    cwd: backendDir,
    env,
    stdio: 'inherit',
  },
)

child.on('exit', (code, signal) => {
  if (signal) process.exit(1)
  process.exit(code ?? 0)
})
