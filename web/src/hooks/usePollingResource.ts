import { useCallback, useEffect, useRef, useState } from 'react';

import type { SessionStatus } from '../types/api';

export const ACTIVE_POLL_INTERVAL_MS = 500;
export const TERMINAL_POLL_INTERVAL_MS = 2000;

export function isTerminalSessionStatus(status?: SessionStatus | null): boolean {
  return !!status && ['complete', 'error', 'stopped', 'waiting_for_input'].includes(status);
}

interface UsePollingResourceOptions<TState, TFetched> {
  enabled: boolean;
  createInitialState: () => TState;
  fetchResource: () => Promise<TFetched>;
  mergeState: (currentState: TState, fetched: TFetched) => TState;
  getErrorMessage: (error: unknown) => string;
  getPollIntervalMs: (fetched: TFetched) => number;
  onReset?: () => void;
}

export function usePollingResource<TState, TFetched>({
  enabled,
  createInitialState,
  fetchResource,
  mergeState,
  getErrorMessage,
  getPollIntervalMs,
  onReset,
}: UsePollingResourceOptions<TState, TFetched>) {
  const [data, setData] = useState<TState>(createInitialState);
  const [error, setError] = useState<string | null>(null);
  const timeoutRef = useRef<number | null>(null);

  const reset = useCallback(() => {
    onReset?.();
    setData(createInitialState());
    setError(null);
  }, [createInitialState, onReset]);

  const refresh = useCallback(async () => {
    const fetched = await fetchResource();
    setData((currentState) => mergeState(currentState, fetched));
    setError(null);
    return fetched;
  }, [fetchResource, mergeState]);

  useEffect(() => {
    reset();

    if (!enabled) {
      return undefined;
    }

    let cancelled = false;

    const schedulePoll = (delayMs: number) => {
      timeoutRef.current = window.setTimeout(runPoll, delayMs);
    };

    const runPoll = async () => {
      try {
        const fetched = await fetchResource();
        if (cancelled) {
          return;
        }
        setData((currentState) => mergeState(currentState, fetched));
        setError(null);
        schedulePoll(getPollIntervalMs(fetched));
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
  }, [enabled, fetchResource, getErrorMessage, getPollIntervalMs, mergeState, reset]);

  return { data, error, refresh, reset };
}
