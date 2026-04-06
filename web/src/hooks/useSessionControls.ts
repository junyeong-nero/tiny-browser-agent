import { useCallback, useState } from 'react';

import { apiClient } from '../api/client';

function getErrorMessage(error: unknown, fallbackMessage: string): string {
  return error instanceof Error ? error.message : fallbackMessage;
}

export function useSessionControls(sessionId: string | null) {
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  const startSession = useCallback(
    async (query: string) => {
      if (!sessionId) {
        return;
      }
      setIsStarting(true);
      try {
        await apiClient.startSession(sessionId, { query });
        setError(null);
      } catch (startError) {
        const message = getErrorMessage(startError, 'Failed to start session');
        setError(message);
        throw new Error(message);
      } finally {
        setIsStarting(false);
      }
    },
    [sessionId],
  );

  const stopSession = useCallback(async () => {
    if (!sessionId) {
      return;
    }
    setIsStopping(true);
    try {
      await apiClient.stopSession(sessionId);
      setError(null);
    } catch (stopError) {
      const message = getErrorMessage(stopError, 'Failed to stop session');
      setError(message);
      throw new Error(message);
    } finally {
      setIsStopping(false);
    }
  }, [sessionId]);

  return { startSession, stopSession, error, isStarting, isStopping };
}
