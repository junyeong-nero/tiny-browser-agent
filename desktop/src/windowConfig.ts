import { ELECTRON_PRELOAD_PATH } from './config';

export const MAIN_WINDOW_WEB_PREFERENCES = {
  preload: ELECTRON_PRELOAD_PATH,
  contextIsolation: true,
  nodeIntegration: false,
  sandbox: false,
} as const;
