import { renderHook, waitFor } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SessionClientProvider } from '../api/SessionClientContext';
import type { SessionClient } from '../api/sessionClient';
import { useSessionVerification } from './useSessionVerification';

describe('useSessionVerification', () => {
  const mockClient: SessionClient = {
    createSession: vi.fn(),
    startSession: vi.fn(),
    stopSession: vi.fn(),
    interruptSession: vi.fn(),
    closeSession: vi.fn(),
    sendMessage: vi.fn(),
    getSession: vi.fn(),
    getSteps: vi.fn(),
    getVerification: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads verification payload for the provided session id', async () => {
    vi.mocked(mockClient.getVerification).mockResolvedValue({
      session_id: 'ses_test',
      verification_items: [],
      grouped_steps: [
        {
          id: 'group-1',
          label: '페이지 이동',
          step_ids: [1],
          steps: [],
        },
      ],
    });

    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(SessionClientProvider, { client: mockClient, children });

    const { result } = renderHook(() => useSessionVerification('ses_test', 'running'), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.verification?.session_id).toBe('ses_test');
    });

    expect(result.current.verification?.grouped_steps).toHaveLength(1);
    expect(mockClient.getVerification).toHaveBeenCalledWith('ses_test');
    expect(result.current.error).toBeNull();
  });
});
