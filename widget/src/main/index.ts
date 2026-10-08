import { app, BrowserWindow, ipcMain, screen } from 'electron'
import { join } from 'node:path'

function createWindow(): void {
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

void app.whenReady().then(() => {
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
