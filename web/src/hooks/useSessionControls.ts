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
  const [isInterrupting, setIsInterrupting] = useState(false);
  const [isClosing, setIsClosing] = useState(false);

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

  const interruptSession = useCallback(async () => {
    if (!sessionId) {
      return;
    }
    setIsInterrupting(true);
    try {
      await sessionClient.interruptSession(sessionId);
      setError(null);
    } catch (interruptError) {
      const message = getErrorMessage(interruptError, 'Failed to interrupt session');
      setError(message);
      throw new Error(message);
    } finally {
      setIsInterrupting(false);
    }
  }, [sessionClient, sessionId]);

  const closeSession = useCallback(async () => {
    if (!sessionId) {
      return;
    }
    setIsClosing(true);
    try {
      await sessionClient.closeSession(sessionId);
      setError(null);
    } catch (closeError) {
      const message = getErrorMessage(closeError, 'Failed to close session');
      setError(message);
      throw new Error(message);
    } finally {
      setIsClosing(false);
    }
  }, [sessionClient, sessionId]);

  return {
    startSession,
    stopSession,
    interruptSession,
    closeSession,
    error,
    isStarting,
    isStopping,
    isInterrupting,
    isClosing,
  };
}
