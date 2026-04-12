import { describe, expect, it, vi } from 'vitest';

import { createDesktopSessionClient } from './desktopSessionClient';
import type { DesktopBridge } from './desktopBridge';


describe('createDesktopSessionClient', () => {
  it('maps session client calls onto the desktop bridge', async () => {
    const bridge: DesktopBridge = {
      sessions: {
        createSession: vi.fn().mockResolvedValue({
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
            artifacts_base_url: null,
            updated_at: 1,
          },
        }),
        startSession: vi.fn().mockResolvedValue(undefined),
        stopSession: vi.fn().mockResolvedValue(undefined),
        sendMessage: vi.fn().mockResolvedValue(undefined),
        getSession: vi.fn().mockResolvedValue({
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
          artifacts_base_url: null,
          updated_at: 1,
        }),
        getSteps: vi.fn().mockResolvedValue([]),
        getVerification: vi.fn().mockResolvedValue({
          session_id: 'ses_test',
          verification_items: [],
          grouped_steps: [],
        }),
      },
    };

    const client = createDesktopSessionClient(bridge);

    await client.createSession();
    await client.startSession('ses_test', { query: 'visit example' });
    await client.stopSession('ses_test');
    await client.sendMessage('ses_test', { text: 'follow up' });
    await client.getSession('ses_test');
    await client.getSteps('ses_test', 7);
    await client.getVerification('ses_test');

    expect(bridge.sessions.createSession).toHaveBeenCalledTimes(1);
    expect(bridge.sessions.startSession).toHaveBeenCalledWith('ses_test', 'visit example');
    expect(bridge.sessions.stopSession).toHaveBeenCalledWith('ses_test');
    expect(bridge.sessions.sendMessage).toHaveBeenCalledWith('ses_test', 'follow up');
    expect(bridge.sessions.getSession).toHaveBeenCalledWith('ses_test');
    expect(bridge.sessions.getSteps).toHaveBeenCalledWith('ses_test', 7);
    expect(bridge.sessions.getVerification).toHaveBeenCalledWith('ses_test');
  });
});
