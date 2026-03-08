'use strict'

const { app, BrowserWindow, dialog, Menu, shell } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const net = require('net')
const http = require('http')

let mainWindow = null
let backendProcess = null
let backendPort = 18765

// ---------------------------------------------------------------------------
// 사용 가능한 TCP 포트 탐색
// ---------------------------------------------------------------------------
function findFreePort(startPort) {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.listen(startPort, '127.0.0.1', () => {
      server.close(() => resolve(startPort))
    })
    server.on('error', () => resolve(findFreePort(startPort + 1)))
  })
}

// ---------------------------------------------------------------------------
// 백엔드 서버 준비 대기 (health check 폴링)
// ---------------------------------------------------------------------------
function waitForBackend(port, retries = 40) {
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(`http://127.0.0.1:${port}/api/health`, (res) => {
        if (res.statusCode === 200) {
          resolve()
        } else {
          retry()
        }
        res.resume()
      })
      req.on('error', retry)
      req.setTimeout(1000, () => { req.destroy(); retry() })
    }
    const retry = () => {
      if (--retries > 0) setTimeout(attempt, 500)
      else reject(new Error('백엔드 서버가 시작되지 않았습니다.'))
    }
    setTimeout(attempt, 500)
  })
}

// ---------------------------------------------------------------------------
// 백엔드 프로세스 시작
// ---------------------------------------------------------------------------
function startBackend(port) {
  const isDev = !app.isPackaged

  if (isDev) {
    // 개발 모드: uvicorn 직접 실행
    const backendDir = path.join(__dirname, '..', 'backend')
    backendProcess = spawn(
      'uvicorn',
      ['app.main:app', '--host', '127.0.0.1', '--port', String(port)],
      {
        cwd: backendDir,
        env: { ...process.env },
        shell: process.platform === 'win32',
      }
    )
  } else {
    // 패키징 모드: PyInstaller 바이너리 실행
    const binaryName = process.platform === 'win32'
      ? 'coworker-server.exe'
      : 'coworker-server'
    const binaryPath = path.join(process.resourcesPath, 'backend', binaryName)
    backendProcess = spawn(binaryPath, ['--port', String(port)], {
      env: { ...process.env },
    })
  }

  backendProcess.stdout?.on('data', (d) =>
    console.log('[Backend]', d.toString().trim())
  )
  backendProcess.stderr?.on('data', (d) =>
    console.error('[Backend]', d.toString().trim())
  )
  backendProcess.on('exit', (code) => {
    if (code !== 0 && code !== null) {
      console.error(`[Backend] 비정상 종료: code=${code}`)
    }
  })
}

// ---------------------------------------------------------------------------
// BrowserWindow 생성
// ---------------------------------------------------------------------------
function createWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 360,
    minHeight: 500,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
    },
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    trafficLightPosition: process.platform === 'darwin' ? { x: 16, y: 14 } : undefined,
    title: 'Coworker',
  })

  mainWindow.loadURL(`http://127.0.0.1:${port}`)

  // 외부 링크는 기본 브라우저로 열기
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// ---------------------------------------------------------------------------
// macOS 메뉴 (최소한)
// ---------------------------------------------------------------------------
function buildMenu() {
  const template = [
    {
      label: 'Coworker',
      submenu: [
        { label: 'Coworker 정보', role: 'about' },
        { type: 'separator' },
        { label: '종료', accelerator: 'CmdOrCtrl+Q', click: () => app.quit() },
      ],
    },
    {
      label: '편집',
      submenu: [
        { role: 'undo' }, { role: 'redo' }, { type: 'separator' },
        { role: 'cut' }, { role: 'copy' }, { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
  ]
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

// ---------------------------------------------------------------------------
// 앱 생명주기
// ---------------------------------------------------------------------------
app.whenReady().then(async () => {
  buildMenu()

  try {
    backendPort = await findFreePort(18765)
    startBackend(backendPort)
    await waitForBackend(backendPort)
    createWindow(backendPort)
  } catch (err) {
    dialog.showErrorBox(
      'Coworker 시작 오류',
      `백엔드 서버를 시작할 수 없습니다.\n\n${err.message}\n\n` +
      'Claude CLI 또는 Gemini CLI가 설치되어 있는지 확인하세요.'
    )
    app.quit()
  }
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (mainWindow === null) createWindow(backendPort)
})

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
})
