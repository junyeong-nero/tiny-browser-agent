import { app, BrowserWindow, ipcMain, shell } from 'electron';

import { BrowserCommandServer } from './browserCommandServer';
import { BrowserSurfaceManager, createElectronBrowserSurfaceView } from './browserSurfaceManager';
import { BRIDGE_CHANNELS, type BrowserSurfaceBounds } from './bridge/channels';
import {
  ELECTRON_PRELOAD_PATH,
  ELECTRON_RENDERER_URL,
  WEB_DIST_INDEX
} from './config';
import { startPythonRuntime, type PythonRuntime } from './python';


let mainWindow: BrowserWindow | null = null;
let pythonRuntime: PythonRuntime | null = null;
let browserCommandServer: BrowserCommandServer | null = null;

const browserSurfaceManager = new BrowserSurfaceManager(() => {
  return createElectronBrowserSurfaceView();
});


function getBridgeClientOrThrow() {
  if (!pythonRuntime) {
    throw new Error('Python bridge runtime is not ready.');
  }
  return pythonRuntime.client;
}


function registerBridgeHandlers(): void {
  ipcMain.handle(BRIDGE_CHANNELS.createSession, async () => getBridgeClientOrThrow().createSession());
  ipcMain.handle(BRIDGE_CHANNELS.startSession, async (_event, payload: { sessionId: string; query: string }) => {
    await getBridgeClientOrThrow().startSession(payload.sessionId, payload.query);
  });
  ipcMain.handle(BRIDGE_CHANNELS.stopSession, async (_event, payload: { sessionId: string }) => {
    await getBridgeClientOrThrow().stopSession(payload.sessionId);
  });
  ipcMain.handle(BRIDGE_CHANNELS.sendMessage, async (_event, payload: { sessionId: string; text: string }) => {
    await getBridgeClientOrThrow().sendMessage(payload.sessionId, payload.text);
  });
  ipcMain.handle(BRIDGE_CHANNELS.getSession, async (_event, payload: { sessionId: string }) =>
    getBridgeClientOrThrow().getSession(payload.sessionId)
  );
  ipcMain.handle(BRIDGE_CHANNELS.getSteps, async (_event, payload: { sessionId: string; afterStepId?: number }) =>
    getBridgeClientOrThrow().getSteps(payload.sessionId, payload.afterStepId)
  );
  ipcMain.handle(BRIDGE_CHANNELS.getVerification, async (_event, payload: { sessionId: string }) =>
    getBridgeClientOrThrow().getVerification(payload.sessionId)
  );
  ipcMain.handle(BRIDGE_CHANNELS.getArtifactText, async (_event, payload: { sessionId: string; name: string }) =>
    getBridgeClientOrThrow().readArtifactText(payload.sessionId, payload.name)
  );
  ipcMain.handle(BRIDGE_CHANNELS.getArtifactBinary, async (_event, payload: { sessionId: string; name: string }) =>
    getBridgeClientOrThrow().readArtifactBinary(payload.sessionId, payload.name)
  );
  ipcMain.handle(BRIDGE_CHANNELS.openArtifact, async (_event, payload: { sessionId: string; name: string }) => {
    const artifactPath = await getBridgeClientOrThrow().resolveArtifactPath(payload.sessionId, payload.name);
    const errorMessage = await shell.openPath(artifactPath);
    if (errorMessage) {
      throw new Error(errorMessage);
    }
  });
  ipcMain.handle(BRIDGE_CHANNELS.focusBrowserSurface, async () => {
    await browserSurfaceManager.focus();
    return null;
  });
  ipcMain.handle(BRIDGE_CHANNELS.setBrowserSurfaceBounds, async (_event, payload: { bounds: BrowserSurfaceBounds }) => {
    await browserSurfaceManager.setBounds(payload.bounds);
    return payload.bounds;
  });
}


async function createMainWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 1000,
    webPreferences: {
      preload: ELECTRON_PRELOAD_PATH,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  await browserSurfaceManager.attachWindow({
    contentView: {
      addChildView(view) {
        mainWindow?.contentView.addChildView(view as never);
      }
    },
    focus() {
      mainWindow?.focus();
    }
  });

  if (ELECTRON_RENDERER_URL) {
    await mainWindow.loadURL(ELECTRON_RENDERER_URL);
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    await mainWindow.loadFile(WEB_DIST_INDEX);
  }

  mainWindow.on('closed', () => {
    browserSurfaceManager.destroy();
    mainWindow = null;
  });

  mainWindow.on('resize', () => {
    void browserSurfaceManager.sync();
  });
}


app.whenReady().then(async () => {
  registerBridgeHandlers();
  browserCommandServer = new BrowserCommandServer(browserSurfaceManager);
  const electronCommandUrl = await browserCommandServer.start();
  pythonRuntime = await startPythonRuntime(electronCommandUrl);
  await createMainWindow();

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createMainWindow();
    }
  });
}).catch((error) => {
  console.error(error);
  app.quit();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  void browserCommandServer?.stop();
  browserSurfaceManager.destroy();
  pythonRuntime?.stop();
});
