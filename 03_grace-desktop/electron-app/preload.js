// electron-app/preload.js – Secure bridge between renderer and main
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electron', {
  // Window controls
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  quit: () => ipcRenderer.send('window-quit'),

  // Info
  getPlatform: () => ipcRenderer.invoke('get-platform'),
  getVersion: () => ipcRenderer.invoke('get-version'),

  // Backend logs (for debug panel)
  onBackendLog: (cb) => ipcRenderer.on('backend-log', (_, msg) => cb(msg)),
  removeBackendLog: () => ipcRenderer.removeAllListeners('backend-log'),
})
