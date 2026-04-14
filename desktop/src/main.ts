import { app, BrowserWindow, ipcMain, shell } from 'electron';
import type { View } from 'electron';

import { BrowserCommandServer } from './browserCommandServer';
import {
  BrowserSurfaceManager,
  createElectronBrowserSurfaceView,
  getManagedBrowserSurfaceAttachmentTarget,
} from './browserSurfaceManager';
import { BRIDGE_CHANNELS, type BrowserSurfaceBounds } from './bridge/channels';
import {
  ELECTRON_RENDERER_URL,
  WEB_DIST_INDEX
} from './config';
import { createDesktopMainWindow } from './mainLifecycle';
import { startPythonRuntime, type PythonRuntime } from './python';
import { MAIN_WINDOW_WEB_PREFERENCES } from './windowConfig';


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

type BridgeHandlerPayload = Record<string, unknown> | undefined;

interface BridgeHandlerRegistration {
  channel: string;
  handle: (payload: BridgeHandlerPayload) => Promise<unknown>;
}

function registerBridgeHandler({ channel, handle }: BridgeHandlerRegistration): void {
  ipcMain.handle(channel, async (_event, payload) => handle(payload as BridgeHandlerPayload));
}


function registerBridgeHandlers(): void {
  const handlers: BridgeHandlerRegistration[] = [
    {
      channel: BRIDGE_CHANNELS.createSession,
      async handle() {
        return getBridgeClientOrThrow().createSession();
      },
    },
    {
      channel: BRIDGE_CHANNELS.startSession,
      async handle(payload) {
        const { query, sessionId } = payload as { query: string; sessionId: string };
        await getBridgeClientOrThrow().startSession(sessionId, query);
        return null;
      },
    },
    {
      channel: BRIDGE_CHANNELS.stopSession,
      async handle(payload) {
        await getBridgeClientOrThrow().stopSession((payload as { sessionId: string }).sessionId);
        return null;
      },
    },
    {
      channel: BRIDGE_CHANNELS.interruptSession,
      async handle(payload) {
        await getBridgeClientOrThrow().interruptSession((payload as { sessionId: string }).sessionId);
        return null;
      },
    },
    {
      channel: BRIDGE_CHANNELS.closeSession,
      async handle(payload) {
        await getBridgeClientOrThrow().closeSession((payload as { sessionId: string }).sessionId);
        return null;
      },
    },
    {
      channel: BRIDGE_CHANNELS.sendMessage,
      async handle(payload) {
        const { sessionId, text } = payload as { sessionId: string; text: string };
        await getBridgeClientOrThrow().sendMessage(sessionId, text);
        return null;
      },
    },
    {
      channel: BRIDGE_CHANNELS.getSession,
      async handle(payload) {
        return getBridgeClientOrThrow().getSession((payload as { sessionId: string }).sessionId);
      },
    },
    {
      channel: BRIDGE_CHANNELS.getSteps,
      async handle(payload) {
        const { afterStepId, sessionId } = payload as { afterStepId?: number; sessionId: string };
        return getBridgeClientOrThrow().getSteps(sessionId, afterStepId);
      },
    },
    {
      channel: BRIDGE_CHANNELS.getVerification,
      async handle(payload) {
        return getBridgeClientOrThrow().getVerification((payload as { sessionId: string }).sessionId);
      },
    },
    {
      channel: BRIDGE_CHANNELS.getArtifactText,
      async handle(payload) {
        const { name, sessionId } = payload as { name: string; sessionId: string };
        return getBridgeClientOrThrow().readArtifactText(sessionId, name);
      },
    },
    {
      channel: BRIDGE_CHANNELS.getArtifactBinary,
      async handle(payload) {
        const { name, sessionId } = payload as { name: string; sessionId: string };
        return getBridgeClientOrThrow().readArtifactBinary(sessionId, name);
      },
    },
    {
      channel: BRIDGE_CHANNELS.openArtifact,
      async handle(payload) {
        const { name, sessionId } = payload as { name: string; sessionId: string };
        const artifactPath = await getBridgeClientOrThrow().resolveArtifactPath(sessionId, name);
        const errorMessage = await shell.openPath(artifactPath);
        if (errorMessage) {
          throw new Error(errorMessage);
        }
        return null;
      },
    },
    {
      channel: BRIDGE_CHANNELS.focusBrowserSurface,
      async handle() {
        await browserSurfaceManager.focus();
        return null;
      },
    },
    {
      channel: BRIDGE_CHANNELS.setBrowserSurfaceBounds,
      async handle(payload) {
        const bounds = (payload as { bounds: BrowserSurfaceBounds }).bounds;
        await browserSurfaceManager.setBounds(bounds);
        return bounds;
      },
    },
  ];

  handlers.forEach(registerBridgeHandler);
}


async function createMainWindow(): Promise<void> {
  mainWindow = await createDesktopMainWindow({
    browserSurfaceManager,
    createWindow: (options) => new BrowserWindow(options),
    getAttachmentTarget: (view) => getManagedBrowserSurfaceAttachmentTarget(view) as View,
    mainWindowWebPreferences: MAIN_WINDOW_WEB_PREFERENCES,
    onClosed: () => {
      mainWindow = null;
    },
    rendererUrl: ELECTRON_RENDERER_URL,
    webDistIndex: WEB_DIST_INDEX,
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
