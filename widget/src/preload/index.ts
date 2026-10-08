import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('reborn', {
  platform: process.platform,
  setInteractive: (interactive: boolean) => ipcRenderer.send('set-interactive', interactive),
  quit: () => ipcRenderer.send('quit'),
})
