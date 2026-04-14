import assert from 'node:assert/strict';
import test from 'node:test';

import { createDesktopMainWindow, type MainWindowLike } from './mainLifecycle';


function createMockMainWindow() {
  const addedViews: unknown[] = [];
  const eventHandlers = new Map<string, () => void>();
  const loadFileCalls: string[] = [];
  const loadURLCalls: string[] = [];
  const devToolsModes: string[] = [];
  let focusCalls = 0;

  const mainWindow: MainWindowLike = {
    contentView: {
      addChildView(view) {
        addedViews.push(view);
      },
    },
    focus() {
      focusCalls += 1;
    },
    async loadFile(filePath) {
      loadFileCalls.push(filePath);
    },
    async loadURL(url) {
      loadURLCalls.push(url);
    },
    on(event, listener) {
      eventHandlers.set(event, listener);
    },
    webContents: {
      openDevTools(options) {
        devToolsModes.push(options.mode);
      },
    },
  };

  return {
    addedViews,
    devToolsModes,
    emit(event: 'closed' | 'resize') {
      eventHandlers.get(event)?.();
    },
    focusCalls: () => focusCalls,
    loadFileCalls,
    loadURLCalls,
    mainWindow,
  };
}


function createMockBrowserSurfaceManager() {
  let destroyCalls = 0;
  let syncCalls = 0;
  let attachedWindowFocusCalls = 0;
  const attachedViews: unknown[] = [];

  return {
    attachWindow: async (window: {
      contentView: { addChildView(view: unknown): void };
      focus(): void;
    }) => {
      window.contentView.addChildView({ kind: 'managed-surface' });
      attachedViews.push({ kind: 'managed-surface' });
      window.focus();
      attachedWindowFocusCalls += 1;
    },
    destroy: () => {
      destroyCalls += 1;
    },
    sync: async () => {
      syncCalls += 1;
    },
    attachedViews,
    attachedWindowFocusCalls: () => attachedWindowFocusCalls,
    destroyCalls: () => destroyCalls,
    syncCalls: () => syncCalls,
  };
}


test('createDesktopMainWindow loads the dev renderer URL and opens devtools in development', async () => {
  const mockWindow = createMockMainWindow();
  const browserSurfaceManager = createMockBrowserSurfaceManager();

  await createDesktopMainWindow({
    browserSurfaceManager: browserSurfaceManager as never,
    createWindow: () => mockWindow.mainWindow,
    getAttachmentTarget: (view) => view,
    mainWindowWebPreferences: {
      preload: '/tmp/preload.js',
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    rendererUrl: 'http://127.0.0.1:5173',
    webDistIndex: '/tmp/index.html',
  });

  assert.deepEqual(mockWindow.loadURLCalls, ['http://127.0.0.1:5173']);
  assert.deepEqual(mockWindow.loadFileCalls, []);
  assert.deepEqual(mockWindow.devToolsModes, ['detach']);
  assert.equal(browserSurfaceManager.attachedWindowFocusCalls(), 1);
});


test('createDesktopMainWindow loads the built renderer file in production', async () => {
  const mockWindow = createMockMainWindow();
  const browserSurfaceManager = createMockBrowserSurfaceManager();

  await createDesktopMainWindow({
    browserSurfaceManager: browserSurfaceManager as never,
    createWindow: () => mockWindow.mainWindow,
    getAttachmentTarget: (view) => view,
    mainWindowWebPreferences: {
      preload: '/tmp/preload.js',
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    rendererUrl: null,
    webDistIndex: '/tmp/index.html',
  });

  assert.deepEqual(mockWindow.loadURLCalls, []);
  assert.deepEqual(mockWindow.loadFileCalls, ['/tmp/index.html']);
  assert.deepEqual(mockWindow.devToolsModes, []);
});


test('createDesktopMainWindow wires closed and resize lifecycle handlers', async () => {
  const mockWindow = createMockMainWindow();
  const browserSurfaceManager = createMockBrowserSurfaceManager();
  let closedCalls = 0;

  await createDesktopMainWindow({
    browserSurfaceManager: browserSurfaceManager as never,
    createWindow: () => mockWindow.mainWindow,
    getAttachmentTarget: (view) => view,
    mainWindowWebPreferences: {
      preload: '/tmp/preload.js',
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    rendererUrl: null,
    webDistIndex: '/tmp/index.html',
    onClosed: () => {
      closedCalls += 1;
    },
  });

  mockWindow.emit('resize');
  mockWindow.emit('closed');

  assert.equal(browserSurfaceManager.syncCalls(), 1);
  assert.equal(browserSurfaceManager.destroyCalls(), 1);
  assert.equal(closedCalls, 1);
});
