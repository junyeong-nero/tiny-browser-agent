import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  SessionClientProvider,
  useSessionClient,
} from './SessionClientContext';
import {
  clearDesktopBridge,
  clearDesktopHost,
  installDesktopBridge,
  markDesktopHost,
} from './desktopBridge';
import { httpSessionClient } from './httpSessionClient';

function SessionClientProbe() {
  const sessionClient = useSessionClient();
  const [error, setError] = useState<string | null>(null);

  return (
    <>
      <button
        type="button"
        onClick={() => {
          void sessionClient.createSession().catch((sessionError) => {
            setError(
              sessionError instanceof Error ? sessionError.message : 'Failed to create session',
            );
          });
        }}
      >
        Create session
      </button>
      {error && <div>{error}</div>}
    </>
  );
}

describe('SessionClientProvider', () => {
  afterEach(() => {
    clearDesktopBridge();
    clearDesktopHost();
    vi.restoreAllMocks();
  });

  it('uses the HTTP session client when no desktop bridge is available', async () => {
    const httpCreateSpy = vi.spyOn(httpSessionClient, 'createSession').mockResolvedValue({
      session_id: 'ses_http',
      snapshot: {
        session_id: 'ses_http',
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

    render(
      <SessionClientProvider>
        <SessionClientProbe />
      </SessionClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Create session' }));

    await waitFor(() => {
      expect(httpCreateSpy).toHaveBeenCalledTimes(1);
    });
  });

  it('uses a desktop session bridge installed after initial render', async () => {
    const httpCreateSpy = vi.spyOn(httpSessionClient, 'createSession');
    const desktopCreateSpy = vi.fn().mockResolvedValue({
      session_id: 'ses_desktop',
      snapshot: {
        session_id: 'ses_desktop',
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

    render(
      <SessionClientProvider>
        <SessionClientProbe />
      </SessionClientProvider>,
    );

    installDesktopBridge({
      sessions: {
        createSession: desktopCreateSpy,
        startSession: vi.fn(),
        stopSession: vi.fn(),
        interruptSession: vi.fn(),
        closeSession: vi.fn(),
        sendMessage: vi.fn(),
        getSession: vi.fn(),
        getSteps: vi.fn(),
        getVerification: vi.fn(),
      },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Create session' }));

    await waitFor(() => {
      expect(desktopCreateSpy).toHaveBeenCalledTimes(1);
    });
    expect(httpCreateSpy).not.toHaveBeenCalled();
  });

  it('does not fall back to HTTP sessions when running in a desktop host without a bridge', async () => {
    const httpCreateSpy = vi.spyOn(httpSessionClient, 'createSession');
    markDesktopHost();

    render(
      <SessionClientProvider>
        <SessionClientProbe />
      </SessionClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Create session' }));

    await waitFor(() => {
      expect(screen.getByText(/Desktop bridge unavailable\./i)).toBeInTheDocument();
    });

    expect(httpCreateSpy).not.toHaveBeenCalled();
  });
});
