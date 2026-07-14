// electron-app/main.js – Grace Desktop Electron Main Process
const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, shell } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const fs = require('fs')
const isDev = !app.isPackaged
let mainWindow = null
let tray = null
let backendProcess = null

// ── Single Instance Lock ──────────────────────────────────────────────────────
// Prevents multiple instances of the app from running, which causes port conflicts
const gotTheLock = app.requestSingleInstanceLock()

if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })
}

// ── Backend process management ────────────────────────────────────────────────

function startBackend() {
  const backendPath = isDev
    ? path.join(__dirname, '..', 'backend-fastapi')
    : path.join(process.resourcesPath, 'backend')

  let pythonExe = process.env.PYTHON_PATH || 'python'

  // In development, prioritize the local virtual environment for stability
  if (isDev && !process.env.PYTHON_PATH) {
    const venvPython = process.platform === 'win32'
      ? path.join(backendPath, '.venv', 'Scripts', 'python.exe')
      : path.join(backendPath, '.venv', 'bin', 'python')
    if (fs.existsSync(venvPython)) {
      pythonExe = venvPython
    }
  }

  backendProcess = spawn(pythonExe, ['main.py'], {
    cwd: backendPath,
    env: { ...process.env },
    stdio: ['pipe', 'pipe', 'pipe'],
  })

  backendProcess.stdout.on('data', (data) => {
    console.log('[Backend]', data.toString().trim())
    if (mainWindow) {
      mainWindow.webContents.send('backend-log', data.toString())
    }
  })

  backendProcess.stderr.on('data', (data) => {
    console.error('[Backend ERR]', data.toString().trim())
    if (mainWindow) {
      mainWindow.webContents.send('backend-log', `STDERR: ${data.toString()}`)
    }
  })

  backendProcess.on('exit', (code) => {
    console.log(`[Backend] exited with code ${code}`)
  })

  console.log('[Electron] Backend process started')
}

function stopBackend() {
  if (backendProcess) {
    if (process.platform === 'win32') {
      // On Windows, use taskkill to ensure the process and its children (like uvicorn) die
      spawn('taskkill', ['/pid', backendProcess.pid, '/f', '/t'])
      backendProcess = null
    } else {
      backendProcess.kill('SIGTERM')
      backendProcess = null
    }
  }
}

// ── Window creation ───────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    frame: false,           // Custom titlebar
    transparent: false,
    backgroundColor: '#0a0a0f',
    titleBarStyle: 'hidden',
    trafficLightPosition: { x: 16, y: 16 },
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
    },
    icon: path.join(__dirname, 'assets', 'icon.png'),
    show: false,
  })

  // Load the React app
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'frontend-react', 'dist', 'index.html'))
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    mainWindow.focus()
  })

  mainWindow.on('close', (e) => {
    if (!app.isQuiting) {
      e.preventDefault()
      mainWindow.hide()
    }
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

function createTray() {
  const icon = nativeImage.createFromPath(path.join(__dirname, 'assets', 'tray-icon.png'))
  tray = new Tray(icon.resize({ width: 16, height: 16 }))
  tray.setToolTip('Grace AI')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Open Grace', click: () => { mainWindow?.show(); mainWindow?.focus() } },
    { type: 'separator' },
    { label: 'Quit', click: () => { app.isQuiting = true; app.quit() } },
  ]))
  tray.on('double-click', () => { mainWindow?.show(); mainWindow?.focus() })
}

// ── IPC handlers ──────────────────────────────────────────────────────────────

ipcMain.on('window-minimize', () => mainWindow?.minimize())
ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.restore()
  else mainWindow?.maximize()
})
ipcMain.on('window-close', () => mainWindow?.hide())
ipcMain.on('window-quit', () => { app.isQuiting = true; app.quit() })

ipcMain.handle('get-platform', () => process.platform)
ipcMain.handle('get-version', () => app.getVersion())

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  startBackend()
  createWindow()
  createTray()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
  else mainWindow?.show()
})

app.on('before-quit', () => {
  app.isQuiting = true
  stopBackend()
})
