import { useCallback, useState } from 'react';

import { apiClient } from '../api/client';

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Failed to send message';
}

export function useSendMessage(sessionId: string | null) {
  const [error, setError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!sessionId) {
        return;
      }
      setIsSending(true);
      try {
        await apiClient.sendMessage(sessionId, { text });
        setError(null);
      } catch (sendError) {
        const message = getErrorMessage(sendError);
        setError(message);
        throw new Error(message);
      } finally {
        setIsSending(false);
      }
    },
    [sessionId],
  );

  return { sendMessage, error, isSending };
}
