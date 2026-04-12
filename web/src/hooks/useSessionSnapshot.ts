import { useCallback, useEffect, useRef, useState } from 'react';

import { useSessionClient } from '../api/SessionClientContext';
import type { SessionSnapshot } from '../types/api';

const ACTIVE_POLL_INTERVAL_MS = 500;
const TERMINAL_POLL_INTERVAL_MS = 2000;

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Failed to load session snapshot';
}

export function useSessionSnapshot(sessionId: string | null) {
  const sessionClient = useSessionClient();
  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timeoutRef = useRef<number | null>(null);

  const refreshSnapshot = useCallback(async () => {
    if (!sessionId) {
      return null;
    }
    const nextSnapshot = await sessionClient.getSession(sessionId);
    setSnapshot(nextSnapshot);
    setError(null);
    return nextSnapshot;
  }, [sessionId, sessionClient]);

  useEffect(() => {
    setSnapshot(null);
    setError(null);

    if (!sessionId) {
      return undefined;
    }

    let cancelled = false;

    const schedulePoll = (delayMs: number) => {
      timeoutRef.current = window.setTimeout(runPoll, delayMs);
    };

    const runPoll = async () => {
      try {
        const nextSnapshot = await sessionClient.getSession(sessionId);
        if (cancelled) {
          return;
        }
        setSnapshot(nextSnapshot);
        setError(null);

        const delayMs = ['complete', 'error', 'stopped'].includes(nextSnapshot.status)
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
  }, [sessionClient, sessionId]);

  return { snapshot, error, refreshSnapshot };
}
