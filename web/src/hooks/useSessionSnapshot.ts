import { useCallback } from 'react';

import { useSessionClient } from '../api/SessionClientContext';
import type { SessionSnapshot } from '../types/api';
import {
  ACTIVE_POLL_INTERVAL_MS,
  TERMINAL_POLL_INTERVAL_MS,
  usePollingResource,
} from './usePollingResource';

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Failed to load session snapshot';
}

export function useSessionSnapshot(sessionId: string | null) {
  const sessionClient = useSessionClient();
  const createInitialState = useCallback(() => null as SessionSnapshot | null, []);
  const fetchResource = useCallback(async () => {
    if (!sessionId) {
      throw new Error('Session id is required');
    }
    return sessionClient.getSession(sessionId);
  }, [sessionClient, sessionId]);
  const mergeState = useCallback(
    (_currentSnapshot: SessionSnapshot | null, nextSnapshot: SessionSnapshot) => nextSnapshot,
    [],
  );
  const getPollIntervalMs = useCallback((nextSnapshot: SessionSnapshot) => {
    return ['complete', 'error', 'stopped', 'waiting_for_input'].includes(nextSnapshot.status)
      ? TERMINAL_POLL_INTERVAL_MS
      : ACTIVE_POLL_INTERVAL_MS;
  }, []);
  const {
    data: snapshot,
    error,
    refresh,
  } = usePollingResource<SessionSnapshot | null, SessionSnapshot>({
    enabled: !!sessionId,
    createInitialState,
    fetchResource,
    mergeState,
    getErrorMessage,
    getPollIntervalMs,
  });

  const refreshSnapshot = useCallback(async () => {
    if (!sessionId) {
      return null;
    }
    return refresh();
  }, [refresh, sessionId]);

  return { snapshot, error, refreshSnapshot };
}
