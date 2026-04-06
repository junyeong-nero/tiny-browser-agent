import { useCallback, useEffect, useRef, useState } from 'react';

import { apiClient } from '../api/client';
import type { SessionStatus, StepRecord } from '../types/api';

const ACTIVE_POLL_INTERVAL_MS = 500;
const TERMINAL_POLL_INTERVAL_MS = 2000;

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Failed to load session steps';
}

export function useSessionSteps(sessionId: string | null, status?: SessionStatus | null) {
  const [steps, setSteps] = useState<StepRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const lastStepIdRef = useRef<number | null>(null);

  const resetSteps = useCallback(() => {
    setSteps([]);
    setError(null);
    lastStepIdRef.current = null;
  }, []);

  const refreshSteps = useCallback(async () => {
    if (!sessionId) {
      return [];
    }
    const nextSteps = await apiClient.getSteps(sessionId, lastStepIdRef.current ?? undefined);
    if (nextSteps.length > 0) {
      lastStepIdRef.current = nextSteps[nextSteps.length - 1].step_id;
      setSteps((currentSteps) => [...currentSteps, ...nextSteps]);
    }
    setError(null);
    return nextSteps;
  }, [sessionId]);

  useEffect(() => {
    resetSteps();

    if (!sessionId) {
      return undefined;
    }

    let cancelled = false;

    const schedulePoll = (delayMs: number) => {
      timeoutRef.current = window.setTimeout(runPoll, delayMs);
    };

    const runPoll = async () => {
      try {
        const nextSteps = await apiClient.getSteps(sessionId, lastStepIdRef.current ?? undefined);
        if (cancelled) {
          return;
        }
        if (nextSteps.length > 0) {
          lastStepIdRef.current = nextSteps[nextSteps.length - 1].step_id;
          setSteps((currentSteps) => [...currentSteps, ...nextSteps]);
        }
        setError(null);

        const delayMs = status && ['complete', 'error', 'stopped'].includes(status)
          ? TERMINAL_POLL_INTERVAL_MS
          : ACTIVE_POLL_INTERVAL_MS;
        schedulePoll(delayMs);
      } catch (pollError) {
        if (cancelled) {
          return;
        }
        setError(getErrorMessage(pollError));
        schedulePoll(TERMINAL_POLL_INTERVAL_MS);
      }
    };

    void runPoll();

    return () => {
      cancelled = true;
      if (timeoutRef.current != null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, [resetSteps, sessionId, status]);

  return { steps, error, refreshSteps, resetSteps };
}
