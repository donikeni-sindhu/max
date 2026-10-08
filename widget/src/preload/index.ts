import { contextBridge, ipcRenderer } from 'electron'

function launchToken(): string {
  const arg = process.argv.find((item) => item.startsWith('--reborn-token='))
  return arg ? arg.slice('--reborn-token='.length) : ''
}

contextBridge.exposeInMainWorld('reborn', {
  platform: process.platform,
  token: launchToken(),
  setInteractive: (interactive: boolean) => ipcRenderer.send('set-interactive', interactive),
  quit: () => ipcRenderer.send('quit'),
})
