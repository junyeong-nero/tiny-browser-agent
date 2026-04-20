import {
  WebContentsView,
  type View,
} from 'electron';

import type { BrowserSurfaceBounds } from './bridge/channels';
import { captureAccessibilitySnapshot, captureBrowserSurfaceState } from './browserSurfaceCapture';
import { attachSameTabPopupHandling, createSameTabWindowOpenHandler } from './browserSurfacePopups';


export const FIXED_BROWSER_SURFACE_WIDTH = 1920;
export const FIXED_BROWSER_SURFACE_HEIGHT = 1080;

// Position the view below the visible window area so it does not cover renderer
// UI. Chromium still renders the attached WebContentsView at its bound size, so
// captures return the full 1920x1080 frame.
const OFFSCREEN_BROWSER_SURFACE_Y_OFFSET = 4000;


export interface ManagedBrowserSurfaceWindow {
  contentView: {
    addChildView(view: View | ManagedBrowserSurfaceView): void;
  };
  focus(): void;
}

export interface BrowserSurfaceBeforeInputEvent {
  alt: boolean;
  control: boolean;
  key: string;
  meta: boolean;
  preventDefault(): void;
  shift: boolean;
  type: string;
}


type BrowserMouseEvent =
  | { type: 'mouseMove'; x: number; y: number }
  | { type: 'mouseDown' | 'mouseUp'; x: number; y: number; button: 'left'; clickCount: number }
  | { type: 'mouseWheel'; x: number; y: number; deltaX: number; deltaY: number };

type BrowserKeyModifier = 'alt' | 'command' | 'control' | 'meta' | 'shift';

interface BrowserKeyEvent {
  type: 'keyDown' | 'keyUp';
  keyCode: string;
  modifiers: BrowserKeyModifier[];
}


export interface ManagedBrowserSurfaceWebContents {
  captureScreenshot(): Promise<Buffer>;
  captureFrameJpeg?(quality: number): Promise<Buffer>;
  close(): void;
  focus(): void;
  getURL(): string;
  insertText(text: string): Promise<void> | void;
  loadURL(url: string): Promise<void>;
  observeTopLevelNavigations(listener: (url: string) => void): () => void;
  observeBeforeInputEvents(listener: (event: BrowserSurfaceBeforeInputEvent) => void): () => void;
  runScript(code: string): Promise<unknown>;
  sendKeyEvent(event: BrowserKeyEvent): void;
  sendMouseEvent(event: BrowserMouseEvent): void;
  setFileInputAtLocation(x: number, y: number, paths: string[]): Promise<void>;
  setWindowOpenHandler(handler: (details: { url: string }) => { action: 'allow' | 'deny' }): void;
}


export interface ManagedBrowserSurfaceView {
  nativeView?: View;
  setBounds(bounds: BrowserSurfaceBounds): void;
  webContents: ManagedBrowserSurfaceWebContents;
}


export interface BrowserSurfaceState {
  screenshotBase64: string;
  url: string;
  html: string | null;
  a11yText: string | null;
  a11ySource: string;
  a11yCaptureStatus: 'captured' | 'error';
  a11yCaptureError: string | null;
  width: number;
  height: number;
}


const KEY_CODE_MAP: Record<string, string> = {
  alt: 'Alt',
  backspace: 'Backspace',
  command: 'Meta',
  control: 'Control',
  delete: 'Backspace',
  down: 'ArrowDown',
  enter: 'Enter',
  escape: 'Escape',
  left: 'ArrowLeft',
  pagedown: 'PageDown',
  pageup: 'PageUp',
  return: 'Enter',
  right: 'ArrowRight',
  shift: 'Shift',
  space: 'Space',
  tab: 'Tab',
  up: 'ArrowUp',
};

const MODIFIER_KEY_MAP: Record<string, string> = {
  alt: 'alt',
  command: 'meta',
  control: 'control',
  shift: 'shift',
};

export interface BrowserSurfaceFramePayload {
  url: string;
  base64: string;
}

export class BrowserSurfaceManager {
  private browserSurfaceUrl: string | null = null;
  private browserSurfaceView: ManagedBrowserSurfaceView | null = null;
  private browserSurfaceWindow: ManagedBrowserSurfaceWindow | null = null;
  private stopObservingTopLevelNavigations: (() => void) | null = null;
  private frameStreamTimer: ReturnType<typeof setInterval> | null = null;
  private frameStreamBusy = false;
  private lastFrameBuffer: Buffer | null = null;

  constructor(
    private readonly createView: () => ManagedBrowserSurfaceView,
  ) {}

  async attachWindow(window: ManagedBrowserSurfaceWindow): Promise<void> {
    this.browserSurfaceWindow = window;
    await this.sync();
  }

  async focus(): Promise<void> {
    this.browserSurfaceWindow?.focus();
    this.ensureView()?.webContents.focus();
  }

  observeBeforeInputEvents(
    listener: (event: BrowserSurfaceBeforeInputEvent) => void,
  ): () => void {
    const browserSurfaceView = this.ensureView();
    if (!browserSurfaceView) {
      return () => {};
    }

    return browserSurfaceView.webContents.observeBeforeInputEvents(listener);
  }

  async setBounds(_bounds: BrowserSurfaceBounds): Promise<void> {
    // The hosted browser surface is fixed at 1920x1080 so that the agent
    // always operates against a stable viewport. Renderer-reported bounds are
    // ignored; the desktop app shows a scaled screenshot instead of the live
    // native overlay.
    await this.sync();
  }

  async setUrl(url: string | null): Promise<void> {
    this.browserSurfaceUrl = url;
    await this.sync();
  }

  getScreenSize(): { width: number; height: number } {
    return {
      width: FIXED_BROWSER_SURFACE_WIDTH,
      height: FIXED_BROWSER_SURFACE_HEIGHT,
    };
  }

  async captureState(): Promise<BrowserSurfaceState> {
    const browserSurfaceView = this.getViewOrThrow();
    const state = await captureBrowserSurfaceState(browserSurfaceView, this.getScreenSize());
    this.browserSurfaceUrl = state.url;
    return state;
  }

  async captureAccessibilityTree(): Promise<{
    tree: string | null;
    url: string;
    source: string;
    status: 'captured' | 'error';
    error: string | null;
  }> {
    const browserSurfaceView = this.getViewOrThrow();
    const snapshot = await captureAccessibilitySnapshot(browserSurfaceView);
    return {
      tree: snapshot.text,
      url: browserSurfaceView.webContents.getURL(),
      source: snapshot.source,
      status: snapshot.status,
      error: snapshot.error,
    };
  }

  async navigate(url: string): Promise<void> {
    await this.setUrl(url);
  }

  async goBack(): Promise<void> {
    const browserSurfaceView = this.getViewOrThrow();
    await browserSurfaceView.webContents.runScript('window.history.back()');
  }

  async goForward(): Promise<void> {
    const browserSurfaceView = this.getViewOrThrow();
    await browserSurfaceView.webContents.runScript('window.history.forward()');
  }

  async reloadPage(): Promise<void> {
    const browserSurfaceView = this.getViewOrThrow();
    await browserSurfaceView.webContents.runScript('location.reload()');
  }

  async clickAt(x: number, y: number): Promise<void> {
    const browserSurfaceView = this.getViewOrThrow();
    browserSurfaceView.webContents.sendMouseEvent({ type: 'mouseMove', x, y });
    browserSurfaceView.webContents.sendMouseEvent({ button: 'left', clickCount: 1, type: 'mouseDown', x, y });
    browserSurfaceView.webContents.sendMouseEvent({ button: 'left', clickCount: 1, type: 'mouseUp', x, y });
  }

  async hoverAt(x: number, y: number): Promise<void> {
    this.getViewOrThrow().webContents.sendMouseEvent({ type: 'mouseMove', x, y });
  }

  async typeTextAt(
    x: number,
    y: number,
    text: string,
    pressEnter: boolean,
    clearBeforeTyping: boolean,
  ): Promise<void> {
    const browserSurfaceView = this.getViewOrThrow();
    await this.clickAt(x, y);
    await browserSurfaceView.webContents.runScript(`
      (() => {
        const element = document.elementFromPoint(${x}, ${y});
        if (!(element instanceof HTMLElement)) {
          return;
        }

        element.focus();
        if (!${JSON.stringify(clearBeforeTyping)}) {
          return;
        }

        if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
          element.value = '';
          element.dispatchEvent(new Event('input', { bubbles: true }));
          return;
        }

        if (element.isContentEditable) {
          element.textContent = '';
        }
      })();
    `);
    await Promise.resolve(browserSurfaceView.webContents.insertText(text));
    if (pressEnter) {
      await this.keyCombination(['Enter']);
    }
  }

  async scrollDocument(direction: 'up' | 'down' | 'left' | 'right'): Promise<void> {
    const { width, height } = this.getScreenSize();
    const horizontalDelta = Math.max(Math.floor(width / 2), 1);
    const verticalDelta = Math.max(Math.floor(height / 2), 1);
    const deltaX = direction === 'left' ? -horizontalDelta : direction === 'right' ? horizontalDelta : 0;
    const deltaY = direction === 'up' ? -verticalDelta : direction === 'down' ? verticalDelta : 0;

    await this.getViewOrThrow().webContents.runScript(`window.scrollBy(${deltaX}, ${deltaY});`);
  }

  async scrollAt(
    x: number,
    y: number,
    direction: 'up' | 'down' | 'left' | 'right',
    magnitude: number,
  ): Promise<void> {
    const deltaX = direction === 'left' ? -magnitude : direction === 'right' ? magnitude : 0;
    const deltaY = direction === 'up' ? -magnitude : direction === 'down' ? magnitude : 0;
    this.getViewOrThrow().webContents.sendMouseEvent({ deltaX, deltaY, type: 'mouseWheel', x, y });
  }

  async keyCombination(keys: string[]): Promise<void> {
    const browserSurfaceView = this.getViewOrThrow();
    const normalizedKeys = keys.map((key) => normalizeElectronKey(key));
    const modifiers = normalizedKeys
      .slice(0, -1)
      .map((key) => MODIFIER_KEY_MAP[key.toLowerCase()])
      .filter((key): key is BrowserKeyModifier => Boolean(key));
    const finalKey = normalizedKeys.at(-1);
    if (!finalKey) {
      return;
    }

    browserSurfaceView.webContents.sendKeyEvent({ keyCode: finalKey, modifiers, type: 'keyDown' });
    browserSurfaceView.webContents.sendKeyEvent({ keyCode: finalKey, modifiers, type: 'keyUp' });
  }

  async uploadFile(
    x: number,
    y: number,
    paths: string[],
  ): Promise<void> {
    if (paths.length === 0) {
      throw new Error('uploadFile requires at least one file path');
    }
    const browserSurfaceView = this.getViewOrThrow();
    await browserSurfaceView.webContents.setFileInputAtLocation(x, y, paths);
  }

  async dragAndDrop(
    x: number,
    y: number,
    destinationX: number,
    destinationY: number,
  ): Promise<void> {
    const browserSurfaceView = this.getViewOrThrow();
    browserSurfaceView.webContents.sendMouseEvent({ type: 'mouseMove', x, y });
    browserSurfaceView.webContents.sendMouseEvent({ button: 'left', clickCount: 1, type: 'mouseDown', x, y });
    browserSurfaceView.webContents.sendMouseEvent({ type: 'mouseMove', x: destinationX, y: destinationY });
    browserSurfaceView.webContents.sendMouseEvent({ button: 'left', clickCount: 1, type: 'mouseUp', x: destinationX, y: destinationY });
  }

  async sync(): Promise<void> {
    const browserSurfaceView = this.ensureView();
    if (!browserSurfaceView) {
      return;
    }

    const browserSurfaceUrl = this.browserSurfaceUrl;

    if (shouldHideBrowserSurface(browserSurfaceUrl)) {
      browserSurfaceView.setBounds(getHiddenBrowserSurfaceBounds());
      if (browserSurfaceView.webContents.getURL() !== 'about:blank') {
        await browserSurfaceView.webContents.loadURL('about:blank').catch(ignoreAbortedNavigation);
      }
      return;
    }

    browserSurfaceView.setBounds(getFixedBrowserSurfaceBounds());
    if (browserSurfaceView.webContents.getURL() !== browserSurfaceUrl) {
      await browserSurfaceView.webContents.loadURL(browserSurfaceUrl!).catch(ignoreAbortedNavigation);
    }
  }

  startFrameStream(
    onFrame: (frame: BrowserSurfaceFramePayload) => void,
    intervalMs = 100,
    jpegQuality = 70,
  ): () => void {
    this.stopFrameStream();

    const tick = async () => {
      if (this.frameStreamBusy) {
        return;
      }
      const view = this.browserSurfaceView;
      if (!view) {
        return;
      }
      const url = view.webContents.getURL();
      if (!url || url === 'about:blank') {
        return;
      }
      const { captureFrameJpeg } = view.webContents;
      if (!captureFrameJpeg) {
        return;
      }

      this.frameStreamBusy = true;
      try {
        const buffer = await captureFrameJpeg.call(view.webContents, jpegQuality);
        if (buffer.length === 0 || this.lastFrameBuffer?.equals(buffer)) {
          return;
        }
        this.lastFrameBuffer = buffer;
        onFrame({ url, base64: buffer.toString('base64') });
      } catch {
        // ignored
      } finally {
        this.frameStreamBusy = false;
      }
    };

    this.frameStreamTimer = setInterval(() => {
      void tick();
    }, intervalMs);

    return () => {
      this.stopFrameStream();
    };
  }

  stopFrameStream(): void {
    if (this.frameStreamTimer) {
      clearInterval(this.frameStreamTimer);
      this.frameStreamTimer = null;
    }
    this.lastFrameBuffer = null;
  }

  destroy(): void {
    this.stopFrameStream();
    this.stopObservingTopLevelNavigations?.();
    this.stopObservingTopLevelNavigations = null;
    if (this.browserSurfaceView) {
      this.browserSurfaceView.webContents.close();
    }

    this.browserSurfaceUrl = null;
    this.browserSurfaceView = null;
    this.browserSurfaceWindow = null;
  }

  private ensureView(): ManagedBrowserSurfaceView | null {
    if (!this.browserSurfaceWindow) {
      return null;
    }

    if (!this.browserSurfaceView) {
      this.browserSurfaceView = this.createView();
      this.stopObservingTopLevelNavigations =
        this.browserSurfaceView.webContents.observeTopLevelNavigations((url) => {
          this.browserSurfaceUrl = url;
        });
      this.browserSurfaceWindow.contentView.addChildView(getManagedBrowserSurfaceAttachmentTarget(this.browserSurfaceView));
    }

    return this.browserSurfaceView;
  }

  private getViewOrThrow(): ManagedBrowserSurfaceView {
    const browserSurfaceView = this.ensureView();
    if (!browserSurfaceView) {
      throw new Error('Browser surface is not attached');
    }
    return browserSurfaceView;
  }

}


export function createElectronBrowserSurfaceView(): ManagedBrowserSurfaceView {
  const browserSurfaceView = new WebContentsView({
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      offscreen: true,
      sandbox: true,
    },
  });
  browserSurfaceView.webContents.setBackgroundThrottling(false);
  try {
    browserSurfaceView.webContents.setFrameRate(30);
  } catch {
    // setFrameRate is only valid for offscreen-rendered contents; ignore if
    // the runtime rejects it.
  }
  // Offscreen-rendered WebContents still need a non-zero viewport for the
  // compositor to produce frames. Keeping the native view at the fixed
  // 1920x1080 size (via setBounds in sync()) ensures capturePage() returns a
  // populated buffer even though the view is not visible to the user.
  const popupSupport = attachSameTabPopupHandling(browserSurfaceView);

  return {
    nativeView: browserSurfaceView,
    setBounds(bounds) {
      browserSurfaceView.setBounds(bounds);
    },
    webContents: {
      async captureScreenshot() {
        // stayHidden keeps the compositor rendering the page even though the
        // WebContentsView is positioned offscreen; otherwise capturePage()
        // returns an empty buffer for fully clipped views.
        const screenshot = await browserSurfaceView.webContents.capturePage(
          undefined,
          { stayHidden: true, stayAwake: true },
        );
        const normalized = screenshot.resize({
          width: FIXED_BROWSER_SURFACE_WIDTH,
          height: FIXED_BROWSER_SURFACE_HEIGHT,
        });
        return normalized.toPNG();
      },
      async captureFrameJpeg(quality) {
        const frame = await browserSurfaceView.webContents.capturePage(
          undefined,
          { stayHidden: true, stayAwake: true },
        );
        if (frame.isEmpty()) {
          return Buffer.alloc(0);
        }
        return frame.toJPEG(quality);
      },
      close() {
        popupSupport.closeAllPopupProxies();
        browserSurfaceView.webContents.close();
      },
      focus() {
        browserSurfaceView.webContents.focus();
      },
      getURL() {
        return browserSurfaceView.webContents.getURL();
      },
      insertText(text) {
        return browserSurfaceView.webContents.insertText(text);
      },
      loadURL(url) {
        return browserSurfaceView.webContents.loadURL(url);
      },
      observeTopLevelNavigations(listener) {
        const handleDidNavigate = (
          _event: Electron.Event,
          url: string,
          _httpResponseCode: number,
          _httpStatusText: string,
        ) => {
          listener(url);
        };
        const handleDidNavigateInPage = (
          _event: Electron.Event,
          url: string,
        ) => {
          listener(url);
        };

        browserSurfaceView.webContents.on('did-navigate', handleDidNavigate);
        browserSurfaceView.webContents.on('did-navigate-in-page', handleDidNavigateInPage);

        return () => {
          browserSurfaceView.webContents.off('did-navigate', handleDidNavigate);
          browserSurfaceView.webContents.off('did-navigate-in-page', handleDidNavigateInPage);
        };
      },
      observeBeforeInputEvents(listener) {
        const handleBeforeInput = (
          event: Electron.Event,
          input: Electron.Input,
        ) => {
          listener({
            alt: input.alt,
            control: input.control,
            key: input.key,
            meta: input.meta,
            preventDefault() {
              event.preventDefault();
            },
            shift: input.shift,
            type: input.type,
          });
        };

        browserSurfaceView.webContents.on('before-input-event', handleBeforeInput);
        return () => {
          browserSurfaceView.webContents.off('before-input-event', handleBeforeInput);
        };
      },
      runScript(code) {
        return browserSurfaceView.webContents.executeJavaScript(code);
      },
      sendKeyEvent(event) {
        browserSurfaceView.webContents.sendInputEvent(event);
      },
      sendMouseEvent(event) {
        browserSurfaceView.webContents.sendInputEvent(event);
      },
      async setFileInputAtLocation(x, y, paths) {
        const dbg = browserSurfaceView.webContents.debugger;
        const detachAfter = !dbg.isAttached();
        if (detachAfter) {
          dbg.attach('1.3');
        }
        try {
          await dbg.sendCommand('DOM.enable');
          const { backendNodeId } = (await dbg.sendCommand('DOM.getNodeForLocation', {
            x,
            y,
            includeUserAgentShadowDOM: true,
          })) as { backendNodeId: number };
          await dbg.sendCommand('DOM.setFileInputFiles', {
            backendNodeId,
            files: paths,
          });
        } finally {
          if (detachAfter && dbg.isAttached()) {
            dbg.detach();
          }
        }
      },
      setWindowOpenHandler(handler) {
        browserSurfaceView.webContents.setWindowOpenHandler(handler);
      },
    },
  };
}

export { createSameTabWindowOpenHandler };


export function getManagedBrowserSurfaceAttachmentTarget(
  browserSurfaceView: ManagedBrowserSurfaceView | View,
): View | ManagedBrowserSurfaceView {
  if (!('webContents' in browserSurfaceView && 'setBounds' in browserSurfaceView)) {
    return browserSurfaceView;
  }

  return browserSurfaceView.nativeView ?? browserSurfaceView;
}


export function getHiddenBrowserSurfaceBounds(): BrowserSurfaceBounds {
  return { x: 0, y: 0, width: 0, height: 0 };
}


export function getFixedBrowserSurfaceBounds(): BrowserSurfaceBounds {
  return {
    x: 0,
    y: OFFSCREEN_BROWSER_SURFACE_Y_OFFSET,
    width: FIXED_BROWSER_SURFACE_WIDTH,
    height: FIXED_BROWSER_SURFACE_HEIGHT,
  };
}


export function shouldHideBrowserSurface(
  browserSurfaceUrl: string | null,
): boolean {
  return !browserSurfaceUrl;
}


function normalizeElectronKey(key: string): string {
  return KEY_CODE_MAP[key.toLowerCase()] ?? key;
}


function ignoreAbortedNavigation(error: unknown): void {
  const isAborted =
    error instanceof Error &&
    (error as { code?: string }).code === 'ERR_ABORTED';
  if (!isAborted) {
    throw error;
  }
}
