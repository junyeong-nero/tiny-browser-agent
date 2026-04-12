import test from 'node:test';
import assert from 'node:assert/strict';

import { BrowserSurfaceManager, getHiddenBrowserSurfaceBounds, shouldHideBrowserSurface } from './browserSurfaceManager';
import type {
  ManagedBrowserSurfaceView,
  ManagedBrowserSurfaceWebContents,
  ManagedBrowserSurfaceWindow,
} from './browserSurfaceManager';


function createMockEnvironment(currentUrl = 'about:blank') {
  const addedViews: ManagedBrowserSurfaceView[] = [];
  const recordedBounds: Array<{ x: number; y: number; width: number; height: number }> = [];
  const loadedUrls: string[] = [];
  let focused = 0;
  let windowFocused = 0;
  let closed = 0;
  let url = currentUrl;

  const webContents: ManagedBrowserSurfaceWebContents = {
    async captureScreenshot() {
      return Buffer.from('png');
    },
    close() {
      closed += 1;
    },
    async runScript() {
      return '<html></html>';
    },
    focus() {
      focused += 1;
    },
    getURL() {
      return url;
    },
    async insertText() {
      return undefined;
    },
    async loadURL(nextUrl: string) {
      url = nextUrl;
      loadedUrls.push(nextUrl);
    },
    sendKeyEvent() {
      return undefined;
    },
    sendMouseEvent() {
      return undefined;
    },
    setWindowOpenHandler() {
      return undefined;
    },
  };

  const view: ManagedBrowserSurfaceView = {
    setBounds(bounds) {
      recordedBounds.push(bounds);
    },
    webContents,
  };

  const window: ManagedBrowserSurfaceWindow = {
    contentView: {
      addChildView(viewToAdd) {
        addedViews.push(viewToAdd);
      },
    },
    focus() {
      windowFocused += 1;
    },
  };

  return {
    addedViews,
    closed: () => closed,
    focused: () => focused,
    loadedUrls,
    manager: new BrowserSurfaceManager(() => view),
    recordedBounds,
    view,
    window,
    windowFocused: () => windowFocused,
  };
}


function createMockEnvironmentWithA11y(currentUrl = 'about:blank') {
  const environment = createMockEnvironment(currentUrl);
  environment.view.webContents.runScript = async (code) => {
    if (code.includes('document.documentElement')) {
      return '<html></html>';
    }
    return '- body\n  - button: Continue';
  };
  return environment;
}


test('BrowserSurfaceManager hides the view until both bounds and URL exist', async () => {
  const environment = createMockEnvironment();

  await environment.manager.attachWindow(environment.window);

  assert.equal(environment.addedViews.length, 1);
  assert.deepEqual(environment.recordedBounds.at(-1), getHiddenBrowserSurfaceBounds());
  assert.deepEqual(environment.loadedUrls, []);

  await environment.manager.setBounds({ x: 10, y: 20, width: 300, height: 200 });

  assert.deepEqual(environment.recordedBounds.at(-1), getHiddenBrowserSurfaceBounds());
  assert.deepEqual(environment.loadedUrls, []);

  await environment.manager.setUrl('https://example.com');

  assert.deepEqual(environment.recordedBounds.at(-1), { x: 10, y: 20, width: 300, height: 200 });
  assert.deepEqual(environment.loadedUrls, ['https://example.com']);
});


test('BrowserSurfaceManager focuses the hosted browser surface and window', async () => {
  const environment = createMockEnvironment();

  await environment.manager.attachWindow(environment.window);
  await environment.manager.focus();

  assert.equal(environment.windowFocused(), 1);
  assert.equal(environment.focused(), 1);
});


test('BrowserSurfaceManager destroys and resets the hosted surface state', async () => {
  const environment = createMockEnvironment();

  await environment.manager.attachWindow(environment.window);
  await environment.manager.setBounds({ x: 10, y: 20, width: 300, height: 200 });
  await environment.manager.setUrl('https://example.com');
  environment.manager.destroy();

  assert.equal(environment.closed(), 1);

  await environment.manager.attachWindow(environment.window);

  assert.equal(environment.addedViews.length, 2);
  assert.deepEqual(environment.recordedBounds.at(-1), getHiddenBrowserSurfaceBounds());
});


test('shouldHideBrowserSurface handles missing URL and zero-sized bounds', () => {
  assert.equal(shouldHideBrowserSurface(null, 'https://example.com'), true);
  assert.equal(shouldHideBrowserSurface({ x: 0, y: 0, width: 0, height: 100 }, 'https://example.com'), true);
  assert.equal(shouldHideBrowserSurface({ x: 0, y: 0, width: 100, height: 100 }, null), true);
  assert.equal(shouldHideBrowserSurface({ x: 0, y: 0, width: 100, height: 100 }, 'https://example.com'), false);
});


test('BrowserSurfaceManager captures HTML and accessibility metadata', async () => {
  const environment = createMockEnvironmentWithA11y('https://example.com');

  await environment.manager.attachWindow(environment.window);
  await environment.manager.setBounds({ x: 10, y: 20, width: 300, height: 200 });
  await environment.manager.setUrl('https://example.com');

  const state = await environment.manager.captureState();

  assert.equal(state.html, '<html></html>');
  assert.equal(state.a11yText, '- body\n  - button: Continue');
  assert.equal(state.a11ySource, 'dom_accessibility_outline');
  assert.equal(state.a11yCaptureStatus, 'captured');
  assert.equal(state.a11yCaptureError, null);
});
