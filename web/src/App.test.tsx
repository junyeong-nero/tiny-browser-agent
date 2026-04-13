import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import { installDesktopBridge, clearDesktopBridge, type DesktopBridge } from './api/desktopBridge';
import { SessionClientProvider } from './api/SessionClientContext';


describe('App focus shortcuts', () => {
  afterEach(() => {
    clearDesktopBridge();
    vi.restoreAllMocks();
  });

  it('routes Alt+1/2/3 across browser, verification, and chat regions', async () => {
    const focusBrowserSurface = vi.fn();
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
          updated_at: 1,
        }),
        getSteps: vi.fn().mockResolvedValue([]),
        getVerification: vi.fn().mockResolvedValue({
          session_id: 'ses_test',
          verification_items: [],
          grouped_steps: [],
        }),
      },
      browserSurface: {
        focus: focusBrowserSurface,
        setBounds: vi.fn(),
      },
      artifacts: {
        open: vi.fn().mockResolvedValue(undefined),
        readBinary: vi.fn().mockResolvedValue(''),
        readText: vi.fn().mockResolvedValue(''),
      },
    };
    installDesktopBridge(bridge);

    render(
      <SessionClientProvider>
        <App />
      </SessionClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'New Session' }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type a message...')).toBeInTheDocument();
    });

    fireEvent.keyDown(window, { altKey: true, key: '1' });
    await waitFor(() => {
      expect(focusBrowserSurface).toHaveBeenCalledTimes(1);
    });

    fireEvent.keyDown(window, { altKey: true, key: '2' });
    await waitFor(() => {
      expect(screen.getByText('패널 이동').closest('.verification-sidebar')).toHaveFocus();
      expect(screen.getByText('패널 이동').closest('.verification-sidebar')).toHaveAttribute('data-focus-active', 'true');
    });

    fireEvent.keyDown(window, { altKey: true, key: '3' });
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type a message...')).toHaveFocus();
    });
  });

  it('shows a structured bridge error when no desktop bridge is available', async () => {
    render(
      <SessionClientProvider>
        <App />
      </SessionClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'New Session' }));

    expect(await screen.findByText(/Bridge error:/)).toBeInTheDocument();
  });
});
