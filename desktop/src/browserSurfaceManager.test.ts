import test from 'node:test';
import assert from 'node:assert/strict';

import {
  BrowserSurfaceManager,
  FALLBACK_BROWSER_SURFACE_HEIGHT,
  FALLBACK_BROWSER_SURFACE_WIDTH,
  createSameTabWindowOpenHandler,
  getHiddenBrowserSurfaceBounds,
  getManagedBrowserSurfaceAttachmentTarget,
  shouldHideBrowserSurface,
} from './browserSurfaceManager';
import type {
  ManagedBrowserSurfaceView,
  ManagedBrowserSurfaceWebContents,
  ManagedBrowserSurfaceWindow,
} from './browserSurfaceManager';
import type { BrowserWindowConstructorOptions, WebContents } from 'electron';


function createMockEnvironment(currentUrl = 'about:blank') {
  const addedViews: Array<ManagedBrowserSurfaceView | ManagedBrowserSurfaceView['nativeView']> = [];
  const recordedBounds: Array<{ x: number; y: number; width: number; height: number }> = [];
  const loadedUrls: string[] = [];
  const beforeInputListeners = new Set<(event: {
    alt: boolean;
    control: boolean;
    key: string;
    meta: boolean;
    preventDefault(): void;
    shift: boolean;
    type: string;
  }) => void>();
  const topLevelNavigationListeners = new Set<(url: string) => void>();
  let focused = 0;
  let prevented = 0;
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
      topLevelNavigationListeners.forEach((listener) => listener(nextUrl));
    },
    observeTopLevelNavigations(listener) {
      topLevelNavigationListeners.add(listener);
      return () => {
        topLevelNavigationListeners.delete(listener);
      };
    },
    observeBeforeInputEvents(listener) {
      beforeInputListeners.add(listener);
      return () => {
        beforeInputListeners.delete(listener);
      };
    },
    sendKeyEvent() {
      return undefined;
    },
    sendMouseEvent() {
      return undefined;
    },
    async setFileInputAtLocation() {
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
    emitBeforeInput(input: { alt?: boolean; control?: boolean; key: string; meta?: boolean; shift?: boolean; type?: string }) {
      beforeInputListeners.forEach((listener) =>
        listener({
          alt: input.alt ?? false,
          control: input.control ?? false,
          key: input.key,
          meta: input.meta ?? false,
          preventDefault() {
            prevented += 1;
          },
          shift: input.shift ?? false,
          type: input.type ?? 'keyDown',
        }),
      );
    },
    navigateTo(nextUrl: string) {
      url = nextUrl;
      topLevelNavigationListeners.forEach((listener) => listener(nextUrl));
    },
    prevented: () => prevented,
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


test('BrowserSurfaceManager hides the view until both bounds and URL are set', async () => {
  const environment = createMockEnvironment();

  await environment.manager.attachWindow(environment.window);

  assert.equal(environment.addedViews.length, 1);
  assert.deepEqual(environment.recordedBounds.at(-1), getHiddenBrowserSurfaceBounds());
  assert.deepEqual(environment.loadedUrls, []);

  await environment.manager.setBounds({ x: 10, y: 20, width: 300, height: 200 });

  // Bounds alone do not reveal the view; URL is still missing.
  assert.deepEqual(environment.recordedBounds.at(-1), getHiddenBrowserSurfaceBounds());
  assert.deepEqual(environment.loadedUrls, []);

  await environment.manager.setUrl('https://example.com');

  assert.deepEqual(environment.recordedBounds.at(-1), { x: 10, y: 20, width: 300, height: 200 });
  assert.deepEqual(environment.loadedUrls, ['https://example.com']);
});


test('BrowserSurfaceManager reports the renderer-provided pane size to the agent', async () => {
  const environment = createMockEnvironment();

  await environment.manager.attachWindow(environment.window);
  await environment.manager.setBounds({ x: 0, y: 0, width: 640, height: 480 });

  assert.deepEqual(environment.manager.getScreenSize(), {
    width: 640,
    height: 480,
  });
});


test('BrowserSurfaceManager falls back to a default screen size before bounds arrive', async () => {
  const environment = createMockEnvironment();
  await environment.manager.attachWindow(environment.window);

  assert.deepEqual(environment.manager.getScreenSize(), {
    width: FALLBACK_BROWSER_SURFACE_WIDTH,
    height: FALLBACK_BROWSER_SURFACE_HEIGHT,
  });
});


test('BrowserSurfaceManager focuses the hosted browser surface and window', async () => {
  const environment = createMockEnvironment();

  await environment.manager.attachWindow(environment.window);
  await environment.manager.focus();

  assert.equal(environment.windowFocused(), 1);
  assert.equal(environment.focused(), 1);
});


test('BrowserSurfaceManager forwards before-input events from the hosted browser surface', async () => {
  const environment = createMockEnvironment();
  let observedKey: string | null = null;

  await environment.manager.attachWindow(environment.window);
  const stopObserving = environment.manager.observeBeforeInputEvents((event) => {
    observedKey = event.key;
    event.preventDefault();
  });

  environment.emitBeforeInput({ control: true, key: '2' });

  assert.equal(observedKey, '2');
  assert.equal(environment.prevented(), 1);

  stopObserving();
  observedKey = null;
  environment.emitBeforeInput({ control: true, key: '3' });
  assert.equal(observedKey, null);
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


test('BrowserSurfaceManager attaches the native Electron view when available', async () => {
  const environment = createMockEnvironment();
  const nativeView = { tag: 'native-view' } as unknown as ManagedBrowserSurfaceView['nativeView'];
  environment.view.nativeView = nativeView;

  await environment.manager.attachWindow(environment.window);

  assert.equal(environment.addedViews.length, 1);
  assert.equal(environment.addedViews[0], nativeView);
});


test('shouldHideBrowserSurface hides when the URL is missing', () => {
  assert.equal(shouldHideBrowserSurface(null), true);
  assert.equal(shouldHideBrowserSurface(''), true);
  assert.equal(shouldHideBrowserSurface('https://example.com'), false);
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


test('BrowserSurfaceManager preserves click-triggered same-tab navigations that commit after capture', async () => {
  const environment = createMockEnvironmentWithA11y('https://example.com/original');
  let delayedNavigationUrl: string | null = null;
  environment.view.webContents.sendMouseEvent = ({ type }) => {
    if (type === 'mouseUp' && delayedNavigationUrl) {
      setTimeout(() => {
        environment.navigateTo(delayedNavigationUrl as string);
      }, 0);
    }
  };

  await environment.manager.attachWindow(environment.window);
  await environment.manager.setBounds({ x: 10, y: 20, width: 300, height: 200 });
  await environment.manager.setUrl('https://example.com/original');
  environment.loadedUrls.length = 0;
  delayedNavigationUrl = 'https://example.com/next';

  await environment.manager.clickAt(50, 60);
  const immediateState = await environment.manager.captureState();

  assert.equal(immediateState.url, 'https://example.com/original');

  await new Promise((resolve) => setTimeout(resolve, 0));
  await environment.manager.sync();

  assert.deepEqual(environment.loadedUrls, []);
});


test('BrowserSurfaceManager preserves popup redirects that load directly into the hosted surface', async () => {
  const environment = createMockEnvironmentWithA11y('https://example.com/original');

  await environment.manager.attachWindow(environment.window);
  await environment.manager.setBounds({ x: 10, y: 20, width: 300, height: 200 });
  await environment.manager.setUrl('https://example.com/original');
  environment.loadedUrls.length = 0;

  await environment.view.webContents.loadURL('https://example.com/popup-target');
  await environment.manager.sync();

  assert.deepEqual(environment.loadedUrls, ['https://example.com/popup-target']);
});


test('BrowserSurfaceManager retries empty screenshot captures before succeeding', async () => {
  const environment = createMockEnvironmentWithA11y('https://example.com');
  const capturedScreenshots = [Buffer.alloc(0), Buffer.alloc(0), Buffer.from('png')];
  environment.view.webContents.captureScreenshot = async () => {
    const nextScreenshot = capturedScreenshots.shift();
    assert.ok(nextScreenshot);
    return nextScreenshot;
  };

  await environment.manager.attachWindow(environment.window);
  await environment.manager.setBounds({ x: 10, y: 20, width: 300, height: 200 });
  await environment.manager.setUrl('https://example.com');

  const state = await environment.manager.captureState();

  assert.equal(state.screenshotBase64, Buffer.from('png').toString('base64'));
  assert.equal(capturedScreenshots.length, 0);
});


test('BrowserSurfaceManager throws when screenshot capture stays empty', async () => {
  const environment = createMockEnvironmentWithA11y('https://example.com');
  environment.view.webContents.captureScreenshot = async () => Buffer.alloc(0);

  await environment.manager.attachWindow(environment.window);
  await environment.manager.setBounds({ x: 10, y: 20, width: 300, height: 200 });
  await environment.manager.setUrl('https://example.com');

  await assert.rejects(
    () => environment.manager.captureState(),
    /empty PNG buffer/,
  );
});


test('getManagedBrowserSurfaceAttachmentTarget falls back to the managed wrapper without a native view', () => {
  const environment = createMockEnvironment();

  assert.equal(getManagedBrowserSurfaceAttachmentTarget(environment.view), environment.view);
});


test('createSameTabWindowOpenHandler redirects popup URLs into the hosted browser surface', async () => {
  const loadedUrls: string[] = [];
  const handler = createSameTabWindowOpenHandler(async (url) => {
    loadedUrls.push(url);
  });

  const result = handler({ url: 'https://example.com/docs' });

  assert.deepEqual(result, { action: 'deny' });
  assert.deepEqual(loadedUrls, ['https://example.com/docs']);
});


test('createSameTabWindowOpenHandler ignores about:blank popups', async () => {
  let loadCalls = 0;
  const handler = createSameTabWindowOpenHandler(async () => {
    loadCalls += 1;
  });

  const result = handler({ url: 'about:blank' });

  assert.deepEqual(result, { action: 'deny' });
  assert.equal(loadCalls, 0);
});


test('createSameTabWindowOpenHandler creates a popup proxy for about:blank popups when requested', async () => {
  const loadedUrls: string[] = [];
  let popupNavigationHandler: (url: string) => void = () => {
    throw new Error('Expected popup navigation handler to be replaced.');
  };
  let receivedOptions: BrowserWindowConstructorOptions | null = null;
  const popupWebContents = { kind: 'popup-proxy' } as unknown as WebContents;

  const handler = createSameTabWindowOpenHandler(
    async (url) => {
      loadedUrls.push(url);
    },
    (options, onPopupNavigate) => {
      receivedOptions = options;
      popupNavigationHandler = onPopupNavigate;
      return popupWebContents;
    },
  );

  const result = handler({ url: 'about:blank' });

  assert.equal(result.action, 'allow');
  assert.ok(result.createWindow);
  assert.equal(
    result.createWindow?.({ webPreferences: { sandbox: true } } as BrowserWindowConstructorOptions),
    popupWebContents,
  );
  assert.deepEqual(receivedOptions, { webPreferences: { sandbox: true } });
  assert.deepEqual(loadedUrls, []);

  popupNavigationHandler('about:blank');
  popupNavigationHandler('https://example.com/oauth');

  assert.deepEqual(loadedUrls, ['https://example.com/oauth']);
});
