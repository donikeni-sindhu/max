import { app, BrowserWindow, ipcMain, screen } from 'electron'
import { spawn, type ChildProcess } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { existsSync } from 'node:fs'
import { join } from 'node:path'

let backend: ChildProcess | null = null

function launchToken(): string {
  if (!app.isPackaged) {
    return process.env.VITE_REBORN_TOKEN || process.env.REBORN_TOKEN || ''
  }
  return randomBytes(32).toString('hex')
}

function startPackagedBackend(token: string): void {
  if (!app.isPackaged) return
  const resources = process.resourcesPath
  const python = join(resources, 'python', 'python.exe')
  const backendDir = join(resources, 'backend')
  if (!existsSync(python) || !existsSync(join(backendDir, 'app', 'main.py'))) return
  backend = spawn(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], {
    cwd: backendDir,
    windowsHide: true,
    stdio: 'ignore',
    env: {
      ...process.env,
      REBORN_TOKEN: token,
      DEMO_MODE: 'true',
      PLAYWRIGHT_FALLBACK: 'false',
    },
  })
}

async function waitForBackend(token: string): Promise<void> {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch('http://127.0.0.1:8000/health', {
        headers: { 'X-REBORN-Token': token },
      })
      if (response.ok) return
    } catch {
      // The companion process is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
}

function createWindow(token: string): void {
  const area = screen.getPrimaryDisplay().workArea
  const height = 390
  const win = new BrowserWindow({
    width: area.width,
    height,
    x: area.x,
    y: area.y + area.height - height,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    hasShadow: false,
    title: 'REBORN Widget',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      additionalArguments: token ? [`--reborn-token=${token}`] : [],
    },
  })

  win.setIgnoreMouseEvents(true, { forward: true })
  ipcMain.on('set-interactive', (_event, interactive: boolean) => {
    win.setIgnoreMouseEvents(!interactive, { forward: true })
  })
  ipcMain.on('quit', () => app.quit())

  const devUrl = process.env['ELECTRON_RENDERER_URL']
  if (devUrl) {
    void win.loadURL(devUrl)
  } else {
    void win.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.setName('REBORN Widget')

void app.whenReady().then(async () => {
  const token = launchToken()
  startPackagedBackend(token)
  if (app.isPackaged) await waitForBackend(token)
  createWindow(token)
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow(token)
  })
})

app.on('before-quit', () => {
  if (backend && !backend.killed) backend.kill()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
