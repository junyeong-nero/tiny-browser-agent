import { describe, expect, it } from 'vitest';

import { getDesktopBridge, hasDesktopBridge, type DesktopBridge } from './desktopBridge';


describe('desktopBridge', () => {
  it('returns null when no desktop bridge is registered', () => {
    const host = {} as typeof globalThis & { __COMPUTER_USE_DESKTOP_BRIDGE__?: DesktopBridge };

    expect(getDesktopBridge(host)).toBeNull();
    expect(hasDesktopBridge(host)).toBe(false);
  });

  it('returns the registered desktop bridge', () => {
    const bridge: DesktopBridge = {
      sessions: {
        createSession: async () => ({ session_id: 'ses_test', snapshot: {} as never }),
        startSession: async () => undefined,
        stopSession: async () => undefined,
        sendMessage: async () => undefined,
        getSession: async () => ({ session_id: 'ses_test' } as never),
        getSteps: async () => [],
        getVerification: async () => ({ session_id: 'ses_test', verification_items: [], grouped_steps: [] }),
      },
    };
    const host = {
      __COMPUTER_USE_DESKTOP_BRIDGE__: bridge,
    } as typeof globalThis & { __COMPUTER_USE_DESKTOP_BRIDGE__?: DesktopBridge };

    expect(getDesktopBridge(host)).toBe(bridge);
    expect(hasDesktopBridge(host)).toBe(true);
  });
});
