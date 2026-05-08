/**
 * Soil Mineralogy AI - Electron Main Process
 * =============================================
 * Gerencia a janela do app e o ciclo de vida do backend Python FastAPI.
 */

const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const net = require('net');

let mainWindow;
let backendProcess = null;
const BACKEND_PORT = 8765;
const isDev = process.argv.includes('--dev');

// ─── Caminho para os recursos ──────────────────────────────────────────────

function getBackendPath() {
  if (isDev) {
    return path.join(__dirname, '..');
  }
  return path.join(process.resourcesPath, 'backend');
}

function getPythonPath() {
  const basePath = path.join(__dirname, '..', 'venv', 'bin', 'python3');
  if (require('fs').existsSync(basePath)) {
    return basePath;
  }
  // Fallback: usar python do sistema
  return process.platform === 'win32' ? 'python' : 'python3';
}

// ─── Iniciar Backend Python ─────────────────────────────────────────────────

function startBackend() {
  return new Promise((resolve, reject) => {
    let executable, args, cwd;

    if (isDev) {
      executable = getPythonPath();
      args = [
        '-m', 'uvicorn', 'app:app',
        '--host', '127.0.0.1',
        '--port', String(BACKEND_PORT),
        '--log-level', 'info'
      ];
      cwd = path.join(getBackendPath(), 'src');
    } else {
      // Produção: Executar o binário do PyInstaller empacotado nos recursos
      executable = path.join(process.resourcesPath, 'backend', process.platform === 'win32' ? 'soil_backend.exe' : 'soil_backend');
      args = []; // o executável do PyInstaller roda o uvicorn internamente em 127.0.0.1:8765
      cwd = path.join(process.resourcesPath, 'backend');
    }
    
    console.log(`[Backend] Iniciando: ${executable}`);
    console.log(`[Backend] Diretório: ${cwd}`);

    backendProcess = spawn(executable, args, {
      cwd: cwd,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      stdio: ['pipe', 'pipe', 'pipe']
    });

    backendProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log(`[Backend] ${output}`);
      if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
        resolve();
      }
    });

    backendProcess.stderr.on('data', (data) => {
      const output = data.toString();
      console.error(`[Backend ERR] ${output}`);
      if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
        resolve();
      }
    });

    backendProcess.on('error', (err) => {
      console.error('[Backend] Falha ao iniciar:', err);
      reject(err);
    });

    backendProcess.on('exit', (code) => {
      console.log(`[Backend] Processo encerrado com código: ${code}`);
      backendProcess = null;
    });

    // Timeout: se não iniciar em 30s, resolver mesmo assim
    setTimeout(() => resolve(), 30000);
  });
}

function stopBackend() {
  if (backendProcess) {
    console.log('[Backend] Encerrando...');
    backendProcess.kill('SIGTERM');
    backendProcess = null;
  }
}

// ─── Esperar pela porta do backend ──────────────────────────────────────────

function waitForPort(port, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    
    function tryConnect() {
      const socket = new net.Socket();
      socket.setTimeout(1000);
      
      socket.on('connect', () => {
        socket.destroy();
        resolve();
      });
      
      socket.on('error', () => {
        socket.destroy();
        if (Date.now() - start > timeout) {
          reject(new Error('Timeout aguardando backend'));
        } else {
          setTimeout(tryConnect, 500);
        }
      });
      
      socket.on('timeout', () => {
        socket.destroy();
        if (Date.now() - start > timeout) {
          reject(new Error('Timeout aguardando backend'));
        } else {
          setTimeout(tryConnect, 500);
        }
      });
      
      socket.connect(port, '127.0.0.1');
    }
    
    tryConnect();
  });
}

// ─── Criar Janela Principal ─────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 680,
    backgroundColor: '#0D0E12',
    titleBarStyle: 'hiddenInset',
    frame: process.platform === 'darwin' ? true : false,
    icon: path.join(__dirname, 'src', 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));

  // if (isDev && !app.isPackaged) {
  //   mainWindow.webContents.openDevTools({ mode: 'detach' });
  // }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ─── IPC Handlers ───────────────────────────────────────────────────────────

ipcMain.handle('get-backend-url', () => {
  return `http://127.0.0.1:${BACKEND_PORT}`;
});

ipcMain.handle('select-files', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Selecionar documentos para importar',
    filters: [{ name: 'Documentos compatíveis', extensions: ['pdf', 'docx', 'txt'] }],
    properties: ['openFile', 'multiSelections']
  });
  return result.filePaths;
});

ipcMain.handle('open-docs-folder', () => {
  const docsPath = path.join(getBackendPath(), 'docs');
  shell.openPath(docsPath);
});

ipcMain.handle('get-platform', () => {
  return process.platform;
});

// ─── Ciclo de Vida do App ───────────────────────────────────────────────────

app.whenReady().then(async () => {
  try {
    console.log('[App] Iniciando backend Python...');
    await startBackend();
    await waitForPort(BACKEND_PORT);
    console.log('[App] Backend pronto! Abrindo janela...');
  } catch (err) {
    console.error('[App] Erro ao iniciar backend:', err);
  }
  
  createWindow();
});

app.on('window-all-closed', () => {
  stopBackend();
  app.quit();
});

app.on('before-quit', () => {
  stopBackend();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
