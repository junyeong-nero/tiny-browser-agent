import { afterEach, describe, expect, it, vi } from 'vitest';

import { createStubDesktopBridge } from './stubDesktopBridge';
import { httpSessionClient } from './httpSessionClient';
import { httpArtifactClient } from './httpArtifactClient';


describe('createStubDesktopBridge', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('delegates sessions and artifacts to the existing HTTP clients', async () => {
    vi.spyOn(httpSessionClient, 'createSession').mockResolvedValue({
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
    });
    vi.spyOn(httpSessionClient, 'startSession').mockResolvedValue(undefined);
    vi.spyOn(httpArtifactClient, 'readArtifactText').mockResolvedValue('artifact-text');
    vi.spyOn(httpArtifactClient, 'openArtifact').mockResolvedValue(undefined);
    vi.spyOn(httpArtifactClient, 'getArtifactHref').mockReturnValue('/api/sessions/ses_test/artifacts/step-0001.png');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, arrayBuffer: async () => new Uint8Array([65, 66]).buffer }),
    );

    const onBrowserSurfaceFocus = vi.fn();
    const onBrowserSurfaceBounds = vi.fn();
    const bridge = createStubDesktopBridge({
      onBrowserSurfaceFocus,
      onBrowserSurfaceBounds,
    });

    await bridge.sessions.createSession();
    await bridge.sessions.startSession('ses_test', 'visit example');
    await bridge.artifacts?.readText('ses_test', 'step-0001.a11y.yaml');
    await bridge.artifacts?.open('ses_test', 'step-0001.html');
    const binary = await bridge.artifacts?.readBinary('ses_test', 'step-0001.png');
    bridge.browserSurface?.focus();
    bridge.browserSurface?.setBounds({ x: 1, y: 2, width: 3, height: 4 });

    expect(httpSessionClient.createSession).toHaveBeenCalledTimes(1);
    expect(httpSessionClient.startSession).toHaveBeenCalledWith('ses_test', { query: 'visit example' });
    expect(httpArtifactClient.readArtifactText).toHaveBeenCalledWith('ses_test', 'step-0001.a11y.yaml');
    expect(httpArtifactClient.openArtifact).toHaveBeenCalledWith('ses_test', 'step-0001.html');
    expect(binary).toBe('QUI=');
    expect(onBrowserSurfaceFocus).toHaveBeenCalledTimes(1);
    expect(onBrowserSurfaceBounds).toHaveBeenCalledWith({ x: 1, y: 2, width: 3, height: 4 });
  });
});
