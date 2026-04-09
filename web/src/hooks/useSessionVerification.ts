import { useCallback, useEffect, useRef, useState } from 'react';

import { apiClient } from '../api/client';
import type { SessionStatus, VerificationPayload } from '../types/api';

const ACTIVE_POLL_INTERVAL_MS = 500;
const TERMINAL_POLL_INTERVAL_MS = 2000;

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Failed to load verification payload';
}

export function useSessionVerification(sessionId: string | null, status?: SessionStatus | null) {
  const [verification, setVerification] = useState<VerificationPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timeoutRef = useRef<number | null>(null);

  const refreshVerification = useCallback(async () => {
    if (!sessionId) {
      return null;
    }
    const nextVerification = await apiClient.getVerification(sessionId);
    setVerification(nextVerification);
    setError(null);
    return nextVerification;
  }, [sessionId]);

  useEffect(() => {
    setVerification(null);
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
        const nextVerification = await apiClient.getVerification(sessionId);
        if (cancelled) {
          return;
        }
        setVerification(nextVerification);
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
  }, [sessionId, status]);

  return { verification, error, refreshVerification };
}
