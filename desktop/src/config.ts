import path from 'node:path';


export const REPO_ROOT = path.resolve(__dirname, '../..');
export const WEB_DIST_INDEX = path.join(REPO_ROOT, 'web', 'dist', 'index.html');
export const DEFAULT_BACKEND_HOST = process.env.COMPUTER_USE_BACKEND_HOST ?? '127.0.0.1';
export const DEFAULT_BACKEND_PORT = Number(process.env.COMPUTER_USE_BACKEND_PORT ?? '8000');
export const ELECTRON_RENDERER_URL = process.env.ELECTRON_RENDERER_URL ?? null;
export const ELECTRON_PRELOAD_PATH = path.join(__dirname, 'preload.js');


export function getBackendBaseUrl(): string {
  return `http://${DEFAULT_BACKEND_HOST}:${DEFAULT_BACKEND_PORT}`;
}
