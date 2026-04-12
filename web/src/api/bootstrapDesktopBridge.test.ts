import { afterEach, describe, expect, it } from 'vitest';

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


function makeHost(search = ''): DesktopBridgeHost {
  return {
    location: { search } as Location,
  } as DesktopBridgeHost;
}


describe('bootstrapDesktopBridge', () => {
  afterEach(() => {
    clearDesktopBridge();
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
