import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../api/client';
import { useSessionSnapshot } from './useSessionSnapshot';

vi.mock('../api/client', () => ({
  apiClient: {
    getSession: vi.fn(),
  },
}));

describe('useSessionSnapshot', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads the snapshot for the provided session id', async () => {
    vi.mocked(apiClient.getSession).mockResolvedValue({
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
      artifacts_base_url: '/api/sessions/ses_test/artifacts',
      updated_at: 1,
    });

    const { result } = renderHook(() => useSessionSnapshot('ses_test'));

    await waitFor(() => {
      expect(result.current.snapshot?.session_id).toBe('ses_test');
    });

    expect(apiClient.getSession).toHaveBeenCalledWith('ses_test');
    expect(result.current.error).toBeNull();
  });
});
