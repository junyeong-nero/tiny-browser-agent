import path from 'node:path';


export const REPO_ROOT = path.resolve(__dirname, '../..');
export const WEB_DIST_INDEX = path.join(REPO_ROOT, 'web', 'dist', 'index.html');
export const ELECTRON_RENDERER_URL = process.env.ELECTRON_RENDERER_URL ?? null;
export const ELECTRON_PRELOAD_PATH = path.join(__dirname, 'preload.js');
