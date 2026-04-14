import assert from 'node:assert/strict';
import test from 'node:test';

import { MAIN_WINDOW_WEB_PREFERENCES } from './windowConfig';

test('desktop main window keeps the preload bridge enabled in Electron', () => {
  assert.equal(MAIN_WINDOW_WEB_PREFERENCES.contextIsolation, true);
  assert.equal(MAIN_WINDOW_WEB_PREFERENCES.nodeIntegration, false);
  assert.equal(MAIN_WINDOW_WEB_PREFERENCES.sandbox, false);
  assert.match(MAIN_WINDOW_WEB_PREFERENCES.preload, /preload\.js$/);
});
