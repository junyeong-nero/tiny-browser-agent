import assert from 'node:assert/strict';
import test from 'node:test';

import { BrowserCommandServer } from './browserCommandServer';
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


test('BrowserCommandServer exposes health and screen size endpoints', async () => {
  const { manager } = createMockManager();
  const server = new BrowserCommandServer(manager);
  const baseUrl = await server.start();

  const healthResponse = await fetch(`${baseUrl}/health`);
  const sizeResponse = await fetch(`${baseUrl}/computer/screen-size`);

  assert.deepEqual(await healthResponse.json(), { status: 'ok' });
  assert.deepEqual(await sizeResponse.json(), { width: 640, height: 480 });

  await server.stop();
});


test('BrowserCommandServer returns current state after navigation commands', async () => {
  const { manager, state } = createMockManager();
  const navigateCalls: string[] = [];
  manager.navigate = async (url: string) => {
    navigateCalls.push(url);
  };

  const server = new BrowserCommandServer(manager);
  const baseUrl = await server.start();

  const response = await fetch(`${baseUrl}/computer/navigate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: 'https://example.com/tasks' }),
  });

  assert.deepEqual(navigateCalls, ['https://example.com/tasks']);
  assert.deepEqual(await response.json(), state);

  await server.stop();
});
