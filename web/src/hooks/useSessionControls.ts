import { useCallback, useState } from 'react';

import { useSessionClient } from '../api/SessionClientContext';

function getErrorMessage(error: unknown, fallbackMessage: string): string {
  return error instanceof Error ? error.message : fallbackMessage;
}

export function useSessionControls(sessionId: string | null) {
  const sessionClient = useSessionClient();
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
        await sessionClient.startSession(sessionId, { query });
        setError(null);
      } catch (startError) {
        const message = getErrorMessage(startError, 'Failed to start session');
        setError(message);
        throw new Error(message);
      } finally {
        setIsStarting(false);
      }
    },
    [sessionClient, sessionId],
  );

  const stopSession = useCallback(async () => {
    if (!sessionId) {
      return;
    }
    setIsStopping(true);
    try {
      await sessionClient.stopSession(sessionId);
      setError(null);
    } catch (stopError) {
      const message = getErrorMessage(stopError, 'Failed to stop session');
      setError(message);
      throw new Error(message);
    } finally {
      setIsStopping(false);
    }
  }, [sessionClient, sessionId]);

  return { startSession, stopSession, error, isStarting, isStopping };
}
