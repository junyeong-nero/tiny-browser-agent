import type { View } from 'electron';

import type { BrowserSurfaceManager, ManagedBrowserSurfaceWindow } from './browserSurfaceManager';
import type { MAIN_WINDOW_WEB_PREFERENCES } from './windowConfig';


type MainWindowWebPreferences = typeof MAIN_WINDOW_WEB_PREFERENCES;

export interface MainWindowLike {
  contentView: {
    addChildView(view: View): void;
  };
  focus(): void;
  loadFile(filePath: string): Promise<void>;
  loadURL(url: string): Promise<void>;
  on(event: 'closed' | 'resize', listener: () => void): void;
  webContents: {
    openDevTools(options: { mode: 'detach' }): void;
  };
}

export type MainWindowFactory<TWindow extends MainWindowLike = MainWindowLike> = (options: {
  width: number;
  height: number;
  webPreferences: MainWindowWebPreferences;
}) => TWindow;

interface CreateDesktopMainWindowOptions<TWindow extends MainWindowLike> {
  browserSurfaceManager: BrowserSurfaceManager;
  createWindow: MainWindowFactory<TWindow>;
  getAttachmentTarget: (view: View) => View;
  mainWindowWebPreferences: MainWindowWebPreferences;
  rendererUrl: string | null;
  webDistIndex: string;
  onClosed?: () => void;
}

export async function createDesktopMainWindow<TWindow extends MainWindowLike>({
  browserSurfaceManager,
  createWindow,
  getAttachmentTarget,
  mainWindowWebPreferences,
  onClosed,
  rendererUrl,
  webDistIndex,
}: CreateDesktopMainWindowOptions<TWindow>): Promise<TWindow> {
  const mainWindow = createWindow({
    width: 1600,
    height: 1000,
    webPreferences: mainWindowWebPreferences,
  });

  await browserSurfaceManager.attachWindow({
    contentView: {
      addChildView(view) {
        mainWindow.contentView.addChildView(getAttachmentTarget(view as View));
      },
    },
    focus() {
      mainWindow.focus();
    },
  } satisfies ManagedBrowserSurfaceWindow);

  if (rendererUrl) {
    await mainWindow.loadURL(rendererUrl);
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    await mainWindow.loadFile(webDistIndex);
  }

  mainWindow.on('closed', () => {
    browserSurfaceManager.destroy();
    onClosed?.();
  });

  mainWindow.on('resize', () => {
    void browserSurfaceManager.sync();
  });

  return mainWindow;
}
