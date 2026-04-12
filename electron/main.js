'use strict'

const { app, BrowserWindow, Tray, Menu, dialog, nativeImage, net } = require('electron')
const { spawn } = require('child_process')
const path = require('path')

const composePath = path.join(__dirname, '..', 'docker', 'docker-compose.yml')
const POLL_URL = 'http://localhost:8080'
const POLL_INTERVAL_MS = 2000
const TIMEOUT_MS = 60000

let mainWindow = null
let loadingWindow = null
let tray = null
let pollTimer = null
let timeoutTimer = null

// ── Docker helpers ────────────────────────────────────────────────────────────

function spawnCompose(args) {
  return spawn('docker', ['compose', '-f', composePath, ...args], { stdio: 'ignore' })
}

function composeUp() {
  return spawnCompose(['up', '-d'])
}

function composeDown(callback) {
  const proc = spawnCompose(['down'])
  proc.on('close', () => { if (callback) callback() })
}

// ── Loading window ────────────────────────────────────────────────────────────

function createLoadingWindow() {
  loadingWindow = new BrowserWindow({
    width: 480,
    height: 260,
    frame: false,
    resizable: false,
    center: true,
    webPreferences: { nodeIntegration: false, contextIsolation: true }
  })

  const html = `<!DOCTYPE html><html><body style="background:#0f172a;color:#f1f5f9;font-family:monospace;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column;gap:16px">
<div style="font-size:24px">Anti-UAV Control Center</div>
<div id="status" style="color:#94a3b8">Starting Docker stack\u2026</div>
</body></html>`

  loadingWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html))
  loadingWindow.on('closed', () => { loadingWindow = null })
}

// ── Main window ───────────────────────────────────────────────────────────────

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  })

  mainWindow.loadURL(POLL_URL)
  mainWindow.once('ready-to-show', () => {
    if (loadingWindow) { loadingWindow.close() }
    mainWindow.show()
  })

  // Intercept close — ask user: minimize to tray or shut down
  mainWindow.on('close', (e) => {
    e.preventDefault()
    const choice = dialog.showMessageBoxSync(mainWindow, {
      type: 'question',
      title: 'Close Anti-UAV Control Center',
      message: 'What would you like to do?',
      detail: 'Minimizing to tray keeps the Docker stack running.\nShutting down will stop all services.',
      buttons: ['Minimize to Tray', 'Shut Down'],
      defaultId: 0,
      cancelId: 0,
    })
    if (choice === 0) {
      // Minimize to tray — just hide the window
      mainWindow.hide()
    } else {
      // Shut down — stop Docker stack then quit
      mainWindow.hide()
      composeDown(() => {
        mainWindow = null
        app.exit(0)
      })
    }
  })

  mainWindow.on('closed', () => { mainWindow = null })
}

// ── Polling ───────────────────────────────────────────────────────────────────

function pollStack(onReady, onTimeout) {
  const started = Date.now()

  function attempt() {
    // Use Electron's net.request — works correctly inside the Electron sandbox
    const req = net.request(POLL_URL)
    req.on('response', (res) => {
      if (res.statusCode === 200 || res.statusCode === 401 || res.statusCode === 302) {
        clearTimeout(timeoutTimer)
        onReady()
      } else {
        scheduleNext()
      }
    })
    req.on('error', () => { scheduleNext() })
    req.end()
  }

  function scheduleNext() {
    if (Date.now() - started >= TIMEOUT_MS) {
      onTimeout()
      return
    }
    pollTimer = setTimeout(attempt, POLL_INTERVAL_MS)
  }

  timeoutTimer = setTimeout(() => {
    clearTimeout(pollTimer)
    onTimeout()
  }, TIMEOUT_MS)

  attempt()
}

// ── Tray ──────────────────────────────────────────────────────────────────────

function createTray() {
  // Use an empty image if no icon file is present
  const icon = nativeImage.createEmpty()
  tray = new Tray(icon)
  tray.setToolTip('Anti-UAV Control Center')

  const menu = Menu.buildFromTemplate([
    {
      label: 'Open',
      click() {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        }
      }
    },
    {
      label: 'Stop Stack',
      click() {
        composeDown()
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click() {
        composeDown(() => app.quit())
      }
    }
  ])

  tray.setContextMenu(menu)
  tray.on('double-click', () => {
    if (mainWindow) { mainWindow.show(); mainWindow.focus() }
  })
}

// ── App lifecycle ─────────────────────────────────────────────────────────────

function start() {
  createLoadingWindow()
  createTray()

  // Start the stack (no-op if already running)
  composeUp()

  // Give compose a moment to settle, then start polling
  setTimeout(() => {
    pollStack(
      () => { createMainWindow() },
      () => {
        const choice = dialog.showMessageBoxSync({
          type: 'error',
          title: 'Startup failed',
          message: 'Docker stack did not become ready within 60 seconds.',
          buttons: ['Retry', 'Quit']
        })
        if (choice === 0) {
          start()
        } else {
          app.quit()
        }
      }
    )
  }, 500)
}

app.whenReady().then(start)

app.on('window-all-closed', (e) => {
  // Keep running in tray — do not quit when all windows are closed
  e.preventDefault()
})

app.on('before-quit', () => {
  clearTimeout(pollTimer)
  clearTimeout(timeoutTimer)
})
