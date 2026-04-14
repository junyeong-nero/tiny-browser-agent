import assert from 'node:assert/strict';
import test from 'node:test';

import { handleBrowserCommandRequest } from './browserCommandServer';
import type { BrowserSurfaceManager, BrowserSurfaceState } from './browserSurfaceManager';


function createMockManager() {
  const state: BrowserSurfaceState = {
    a11yCaptureError: null,
    a11yCaptureStatus: 'captured',
    a11ySource: 'dom_accessibility_outline',
    a11yText: '- body',
    html: '<html></html>',
    screenshotBase64: 'Zm9v',
    url: 'https://example.com',
    width: 640,
    height: 480,
  };

  const manager = {
    captureState: async () => state,
    clickAt: async () => undefined,
    dragAndDrop: async () => undefined,
    getScreenSize: () => ({ width: 640, height: 480 }),
    goBack: async () => undefined,
    goForward: async () => undefined,
    hoverAt: async () => undefined,
    keyCombination: async () => undefined,
    navigate: async () => undefined,
    scrollAt: async () => undefined,
    scrollDocument: async () => undefined,
    typeTextAt: async () => undefined,
  } as unknown as BrowserSurfaceManager;

  return { manager, state };
}


test('BrowserCommandServer exposes health and screen size routes', async () => {
  const { manager } = createMockManager();
  const healthResponse = await handleBrowserCommandRequest(manager, 'GET', '/health');
  const sizeResponse = await handleBrowserCommandRequest(manager, 'GET', '/computer/screen-size');

  assert.deepEqual(healthResponse, { status: 200, payload: { status: 'ok' } });
  assert.deepEqual(sizeResponse, { status: 200, payload: { width: 640, height: 480 } });
});


test('BrowserCommandServer returns current state after navigation commands', async () => {
  const { manager, state } = createMockManager();
  const navigateCalls: string[] = [];
  manager.navigate = async (url: string) => {
    navigateCalls.push(url);
  };

  const response = await handleBrowserCommandRequest(
    manager,
    'POST',
    '/computer/navigate',
    { url: 'https://example.com/tasks' },
  );

  assert.deepEqual(navigateCalls, ['https://example.com/tasks']);
  assert.deepEqual(response, { status: 200, payload: state });
});

test('BrowserCommandServer returns 404 for unknown routes', async () => {
  const { manager } = createMockManager();

  const response = await handleBrowserCommandRequest(manager, 'GET', '/missing');

  assert.deepEqual(response, { status: 404, payload: { error: 'Not found' } });
});
