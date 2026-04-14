import { useCallback, useRef } from 'react';

import { useSessionClient } from '../api/SessionClientContext';
import type { SessionStatus, StepRecord } from '../types/api';
import {
  ACTIVE_POLL_INTERVAL_MS,
  TERMINAL_POLL_INTERVAL_MS,
  isTerminalSessionStatus,
  usePollingResource,
} from './usePollingResource';

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Failed to load session steps';
}

export function useSessionSteps(sessionId: string | null, status?: SessionStatus | null) {
  const sessionClient = useSessionClient();
  const lastStepIdRef = useRef<number | null>(null);
  const createInitialState = useCallback(() => [] as StepRecord[], []);
  const handleReset = useCallback(() => {
    lastStepIdRef.current = null;
  }, []);
  const fetchResource = useCallback(async () => {
    if (!sessionId) {
      throw new Error('Session id is required');
    }
    return sessionClient.getSteps(sessionId, lastStepIdRef.current ?? undefined);
  }, [sessionClient, sessionId]);
  const mergeState = useCallback((currentSteps: StepRecord[], nextSteps: StepRecord[]) => {
    if (nextSteps.length === 0) {
      return currentSteps;
    }
    lastStepIdRef.current = nextSteps[nextSteps.length - 1].step_id;
    return [...currentSteps, ...nextSteps];
  }, []);
  const getPollIntervalMs = useCallback(
    (_nextSteps: StepRecord[]) =>
      isTerminalSessionStatus(status) ? TERMINAL_POLL_INTERVAL_MS : ACTIVE_POLL_INTERVAL_MS,
    [status],
  );
  const {
    data: steps,
    error,
    refresh,
    reset,
  } = usePollingResource<StepRecord[], StepRecord[]>({
    enabled: !!sessionId,
    createInitialState,
    fetchResource,
    mergeState,
    getErrorMessage,
    getPollIntervalMs,
    onReset: handleReset,
  });

  const refreshSteps = useCallback(async () => {
    if (!sessionId) {
      return [];
    }
    return refresh();
  }, [refresh, sessionId]);

  const resetSteps = useCallback(() => {
    reset();
  }, [reset]);

  return { steps, error, refreshSteps, resetSteps };
}
