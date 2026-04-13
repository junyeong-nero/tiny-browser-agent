import { renderHook, waitFor } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SessionClientProvider } from '../api/SessionClientContext';
import type { SessionClient } from '../api/sessionClient';
import { useSessionSnapshot } from './useSessionSnapshot';

describe('useSessionSnapshot', () => {
  const mockClient: SessionClient = {
    createSession: vi.fn(),
    startSession: vi.fn(),
    stopSession: vi.fn(),
    sendMessage: vi.fn(),
    getSession: vi.fn(),
    getSteps: vi.fn(),
    getVerification: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads the snapshot for the provided session id', async () => {
    vi.mocked(mockClient.getSession).mockResolvedValue({
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
    });

    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(SessionClientProvider, { client: mockClient, children });

    const { result } = renderHook(() => useSessionSnapshot('ses_test'), { wrapper });

    await waitFor(() => {
      expect(result.current.snapshot?.session_id).toBe('ses_test');
    });

    expect(mockClient.getSession).toHaveBeenCalledWith('ses_test');
    expect(result.current.error).toBeNull();
  });
});
