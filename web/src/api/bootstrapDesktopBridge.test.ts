import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  bootstrapDesktopBridge,
  shouldEnableDesktopStub,
} from './bootstrapDesktopBridge';
import {
  clearDesktopBridge,
  installDesktopBridge,
  type DesktopBridge,
  type DesktopBridgeHost,
} from './desktopBridge';
import { httpArtifactClient } from './httpArtifactClient';
import { httpSessionClient } from './httpSessionClient';


function makeHost(search = ''): DesktopBridgeHost {
  return {
    location: { search } as Location,
  } as DesktopBridgeHost;
}


describe('bootstrapDesktopBridge', () => {
  afterEach(() => {
    clearDesktopBridge();
    vi.restoreAllMocks();
  });

  it('keeps browser mode when no desktop stub is enabled', () => {
    const host = makeHost();

    expect(shouldEnableDesktopStub(host)).toBe(false);
    expect(bootstrapDesktopBridge(host)).toBeNull();
  });

  it('enables the desktop stub from a global flag', () => {
    const host = makeHost();
    host.__COMPUTER_USE_ENABLE_DESKTOP_STUB__ = true;

    const bridge = bootstrapDesktopBridge(host);

    expect(bridge).not.toBeNull();
    expect(host.__COMPUTER_USE_DESKTOP_BRIDGE__).toBe(bridge);
  });

  it('wires the stub bridge to the HTTP clients when enabled', async () => {
    const host = makeHost('?desktopBridgeStub=1');
    const createSessionSpy = vi.spyOn(httpSessionClient, 'createSession').mockResolvedValue({
      session_id: 'ses_test',
      snapshot: {
        session_id: 'ses_test',
        status: 'idle',
        current_url: null,
        latest_screenshot_b64: null,
        latest_step_id: null,
        last_reasoning: null,
        last_actions: [],
        messages: [],
        final_reasoning: null,
        error_message: null,
        updated_at: 1,
      },
    });
    const readArtifactTextSpy = vi
      .spyOn(httpArtifactClient, 'readArtifactText')
      .mockResolvedValue('artifact-text');

    const bridge = bootstrapDesktopBridge(host);

    await expect(bridge?.sessions.createSession()).resolves.toMatchObject({ session_id: 'ses_test' });
    await expect(bridge?.artifacts?.readText('ses_test', 'step-0001.a11y.yaml')).resolves.toBe('artifact-text');
    expect(createSessionSpy).toHaveBeenCalledTimes(1);
    expect(readArtifactTextSpy).toHaveBeenCalledWith('ses_test', 'step-0001.a11y.yaml');
  });

  it('enables the desktop stub from a query parameter', () => {
    const host = makeHost('?desktopBridgeStub=1');

    expect(shouldEnableDesktopStub(host)).toBe(true);
    expect(bootstrapDesktopBridge(host)).not.toBeNull();
  });

  it('preserves an already installed bridge', () => {
    const host = makeHost('?desktopBridgeStub=1');
    const existingBridge = { sessions: {} } as DesktopBridge;
    installDesktopBridge(existingBridge, host);

    expect(bootstrapDesktopBridge(host)).toBe(existingBridge);
  });
});
