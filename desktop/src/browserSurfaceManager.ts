import {
  WebContentsView,
  type View,
} from 'electron';

import type { BrowserSurfaceBounds } from './bridge/channels';
import { captureBrowserSurfaceState } from './browserSurfaceCapture';
import { attachSameTabPopupHandling, createSameTabWindowOpenHandler } from './browserSurfacePopups';


export interface ManagedBrowserSurfaceWindow {
  contentView: {
    addChildView(view: View | ManagedBrowserSurfaceView): void;
  };
  focus(): void;
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
  close(): void;
  focus(): void;
  getURL(): string;
  insertText(text: string): Promise<void> | void;
  loadURL(url: string): Promise<void>;
  observeTopLevelNavigations(listener: (url: string) => void): () => void;
  runScript(code: string): Promise<unknown>;
  sendKeyEvent(event: BrowserKeyEvent): void;
  sendMouseEvent(event: BrowserMouseEvent): void;
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

export class BrowserSurfaceManager {
  private browserSurfaceBounds: BrowserSurfaceBounds | null = null;
  private browserSurfaceUrl: string | null = null;
  private browserSurfaceView: ManagedBrowserSurfaceView | null = null;
  private browserSurfaceWindow: ManagedBrowserSurfaceWindow | null = null;
  private lastVisibleBrowserSurfaceBounds: BrowserSurfaceBounds | null = null;
  private stopObservingTopLevelNavigations: (() => void) | null = null;

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

  async setBounds(bounds: BrowserSurfaceBounds): Promise<void> {
    this.browserSurfaceBounds = bounds;
    if (bounds.width > 0 && bounds.height > 0) {
      this.lastVisibleBrowserSurfaceBounds = bounds;
    }
    await this.sync();
  }

  async setUrl(url: string | null): Promise<void> {
    this.browserSurfaceUrl = url;
    await this.sync();
  }

  getScreenSize(): { width: number; height: number } {
    const bounds = this.lastVisibleBrowserSurfaceBounds ?? this.browserSurfaceBounds;
    if (!bounds || bounds.width <= 0 || bounds.height <= 0) {
      return { width: 0, height: 0 };
    }
    return { width: bounds.width, height: bounds.height };
  }

  async captureState(): Promise<BrowserSurfaceState> {
    const browserSurfaceView = this.getViewOrThrow();
    const { width, height } = this.getScreenSize();
    const state = await captureBrowserSurfaceState(browserSurfaceView, { width, height });
    this.browserSurfaceUrl = state.url;
    return state;
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

    const browserSurfaceBounds = this.browserSurfaceBounds;
    const browserSurfaceUrl = this.browserSurfaceUrl;

    if (shouldHideBrowserSurface(browserSurfaceBounds, browserSurfaceUrl)) {
      browserSurfaceView.setBounds(getHiddenBrowserSurfaceBounds());
      if (browserSurfaceView.webContents.getURL() !== 'about:blank') {
        await browserSurfaceView.webContents.loadURL('about:blank');
      }
      return;
    }

    if (browserSurfaceBounds == null || browserSurfaceUrl == null) {
      return;
    }

    browserSurfaceView.setBounds(browserSurfaceBounds);
    if (browserSurfaceView.webContents.getURL() !== browserSurfaceUrl) {
      await browserSurfaceView.webContents.loadURL(browserSurfaceUrl);
    }
  }

  destroy(): void {
    this.stopObservingTopLevelNavigations?.();
    this.stopObservingTopLevelNavigations = null;
    if (this.browserSurfaceView) {
      this.browserSurfaceView.webContents.close();
    }

    this.browserSurfaceBounds = null;
    this.lastVisibleBrowserSurfaceBounds = null;
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
      sandbox: true,
    },
  });
  const popupSupport = attachSameTabPopupHandling(browserSurfaceView);

  return {
    nativeView: browserSurfaceView,
    setBounds(bounds) {
      browserSurfaceView.setBounds(bounds);
    },
    webContents: {
      async captureScreenshot() {
        const screenshot = await browserSurfaceView.webContents.capturePage();
        return screenshot.toPNG();
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
      runScript(code) {
        return browserSurfaceView.webContents.executeJavaScript(code);
      },
      sendKeyEvent(event) {
        browserSurfaceView.webContents.sendInputEvent(event);
      },
      sendMouseEvent(event) {
        browserSurfaceView.webContents.sendInputEvent(event);
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


export function shouldHideBrowserSurface(
  browserSurfaceBounds: BrowserSurfaceBounds | null,
  browserSurfaceUrl: string | null,
): boolean {
  return (
    browserSurfaceBounds == null ||
    browserSurfaceBounds.width <= 0 ||
    browserSurfaceBounds.height <= 0 ||
    !browserSurfaceUrl
  );
}


function normalizeElectronKey(key: string): string {
  return KEY_CODE_MAP[key.toLowerCase()] ?? key;
}
