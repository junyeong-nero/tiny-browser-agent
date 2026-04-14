import { act, renderHook, waitFor } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SessionClientProvider } from '../api/SessionClientContext';
import type { SessionClient } from '../api/sessionClient';
import { useSessionSteps } from './useSessionSteps';

describe('useSessionSteps', () => {
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

  it('loads and incrementally appends steps for the provided session id', async () => {
    vi.mocked(mockClient.getSteps)
      .mockResolvedValueOnce([
        {
          step_id: 1,
          timestamp: 1,
          reasoning: 'Open the page',
          function_calls: [],
          url: 'https://example.com',
          status: 'complete',
          screenshot_path: 'step-0001.png',
          html_path: 'step-0001.html',
          metadata_path: 'step-0001.json',
          error_message: null,
        },
      ])
      .mockResolvedValueOnce([
        {
          step_id: 2,
          timestamp: 2,
          reasoning: 'Inspect the result',
          function_calls: [],
          url: 'https://example.com/result',
          status: 'complete',
          screenshot_path: 'step-0002.png',
          html_path: 'step-0002.html',
          metadata_path: 'step-0002.json',
          error_message: null,
        },
      ]);

    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(SessionClientProvider, { client: mockClient, children });

    const { result } = renderHook(() => useSessionSteps('ses_test', 'running'), { wrapper });

    await waitFor(() => {
      expect(result.current.steps).toHaveLength(1);
    });

    let appendedSteps:
      | Awaited<ReturnType<typeof result.current.refreshSteps>>
      | undefined;
    await act(async () => {
      appendedSteps = await result.current.refreshSteps();
    });

    await waitFor(() => {
      expect(result.current.steps).toHaveLength(2);
    });

    expect(appendedSteps).toHaveLength(1);
    expect(result.current.steps.map((step) => step.step_id)).toEqual([1, 2]);
    expect(mockClient.getSteps).toHaveBeenNthCalledWith(1, 'ses_test', undefined);
    expect(mockClient.getSteps).toHaveBeenNthCalledWith(2, 'ses_test', 1);
  });
});
