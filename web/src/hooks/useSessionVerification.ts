import { useCallback } from 'react';

import { useSessionClient } from '../api/SessionClientContext';
import type { SessionStatus, VerificationPayload } from '../types/api';
import {
  ACTIVE_POLL_INTERVAL_MS,
  TERMINAL_POLL_INTERVAL_MS,
  isTerminalSessionStatus,
  usePollingResource,
} from './usePollingResource';

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Failed to load verification payload';
}

export function useSessionVerification(sessionId: string | null, status?: SessionStatus | null) {
  const sessionClient = useSessionClient();
  const createInitialState = useCallback(() => null as VerificationPayload | null, []);
  const fetchResource = useCallback(async () => {
    if (!sessionId) {
      throw new Error('Session id is required');
    }
    return sessionClient.getVerification(sessionId);
  }, [sessionClient, sessionId]);
  const mergeState = useCallback(
    (_currentVerification: VerificationPayload | null, nextVerification: VerificationPayload) =>
      nextVerification,
    [],
  );
  const getPollIntervalMs = useCallback(
    (_nextVerification: VerificationPayload) =>
      isTerminalSessionStatus(status) ? TERMINAL_POLL_INTERVAL_MS : ACTIVE_POLL_INTERVAL_MS,
    [status],
  );
  const {
    data: verification,
    error,
    refresh,
  } = usePollingResource<VerificationPayload | null, VerificationPayload>({
    enabled: !!sessionId,
    createInitialState,
    fetchResource,
    mergeState,
    getErrorMessage,
    getPollIntervalMs,
  });

  const refreshVerification = useCallback(async () => {
    if (!sessionId) {
      return null;
    }
    return refresh();
  }, [refresh, sessionId]);

  return { verification, error, refreshVerification };
}
