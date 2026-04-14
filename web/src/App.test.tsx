import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import {
  clearDesktopBridge,
  clearDesktopHost,
  installDesktopBridge,
  markDesktopHost,
  type DesktopBridge,
} from './api/desktopBridge';
import { httpSessionClient } from './api/httpSessionClient';
import { SessionClientProvider } from './api/SessionClientContext';


describe('App focus shortcuts', () => {
  afterEach(() => {
    clearDesktopBridge();
    clearDesktopHost();
    vi.restoreAllMocks();
  });

  it('routes Ctrl/Cmd+1/2/3 across browser, verification, and chat regions', async () => {
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
        interruptSession: vi.fn().mockResolvedValue(undefined),
        closeSession: vi.fn().mockResolvedValue(undefined),
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
        focus: vi.fn(),
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

    fireEvent.keyDown(window, { ctrlKey: true, key: '1' });
    await waitFor(() => {
      expect(screen.getByLabelText('Browser surface')).toHaveFocus();
      expect(screen.getByLabelText('Browser surface')).toHaveAttribute('data-focus-active', 'true');
    });

    fireEvent.keyDown(window, { ctrlKey: true, key: '2' });
    await waitFor(() => {
      expect(screen.getByText('지금 상태').closest('.verification-sidebar')).toHaveFocus();
      expect(screen.getByText('지금 상태').closest('.verification-sidebar')).toHaveAttribute('data-focus-active', 'true');
    });

    fireEvent.keyDown(window, { metaKey: true, key: '3' });
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type a message...')).toHaveFocus();
    });
  });

  it('routes desktop focus-region events back into the renderer panes', async () => {
    installDesktopBridge({
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
        interruptSession: vi.fn().mockResolvedValue(undefined),
        closeSession: vi.fn().mockResolvedValue(undefined),
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
        focus: vi.fn(),
        setBounds: vi.fn(),
      },
      artifacts: {
        open: vi.fn().mockResolvedValue(undefined),
        readBinary: vi.fn().mockResolvedValue(''),
        readText: vi.fn().mockResolvedValue(''),
      },
    });

    render(
      <SessionClientProvider>
        <App />
      </SessionClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'New Session' }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type a message...')).toBeInTheDocument();
    });

    act(() => {
      window.dispatchEvent(new CustomEvent('computer-use:focus-region', { detail: 'verification' }));
    });
    await waitFor(() => {
      expect(screen.getByText('지금 상태').closest('.verification-sidebar')).toHaveFocus();
    });

    act(() => {
      window.dispatchEvent(new CustomEvent('computer-use:focus-region', { detail: 'chat' }));
    });
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type a message...')).toHaveFocus();
    });

    act(() => {
      window.dispatchEvent(new CustomEvent('computer-use:focus-region', { detail: 'browser' }));
    });
    await waitFor(() => {
      expect(screen.getByLabelText('Browser surface')).toHaveFocus();
    });
  });

  it('creates a session through the HTTP fallback when no desktop bridge is available', async () => {
    vi.spyOn(httpSessionClient, 'createSession').mockResolvedValue({
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
        <App />
      </SessionClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'New Session' }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type a message...')).toBeInTheDocument();
    });

    expect(httpSessionClient.createSession).toHaveBeenCalledTimes(1);
  });

  it('uses a desktop bridge installed after initial render when creating a new session', async () => {
    const httpCreateSessionSpy = vi.spyOn(httpSessionClient, 'createSession');
    const desktopCreateSessionSpy = vi.fn().mockResolvedValue({
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
        <App />
      </SessionClientProvider>,
    );

    installDesktopBridge({
      sessions: {
        createSession: desktopCreateSessionSpy,
        startSession: vi.fn().mockResolvedValue(undefined),
        stopSession: vi.fn().mockResolvedValue(undefined),
        interruptSession: vi.fn().mockResolvedValue(undefined),
        closeSession: vi.fn().mockResolvedValue(undefined),
        sendMessage: vi.fn().mockResolvedValue(undefined),
        getSession: vi.fn().mockResolvedValue({
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
        }),
        getSteps: vi.fn().mockResolvedValue([]),
        getVerification: vi.fn().mockResolvedValue({
          session_id: 'ses_desktop',
          verification_items: [],
          grouped_steps: [],
        }),
      },
    });

    fireEvent.click(screen.getByRole('button', { name: 'New Session' }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type a message...')).toBeInTheDocument();
    });

    expect(desktopCreateSessionSpy).toHaveBeenCalledTimes(1);
    expect(httpCreateSessionSpy).not.toHaveBeenCalled();
  });

  it('does not fall back to HTTP when running in a desktop host without a bridge', async () => {
    const httpCreateSessionSpy = vi.spyOn(httpSessionClient, 'createSession');
    markDesktopHost();

    render(
      <SessionClientProvider>
        <App />
      </SessionClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'New Session' }));

    await waitFor(() => {
      expect(screen.getAllByText(/Desktop bridge unavailable\./i).length).toBeGreaterThan(0);
    });

    expect(httpCreateSessionSpy).not.toHaveBeenCalled();
  });
});
