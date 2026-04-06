import { useCallback, useMemo, useState } from 'react';

import { apiClient } from './api/client';
import { ArtifactLinks } from './components/ArtifactLinks';
import { BrowserPane } from './components/BrowserPane';
import { ChatPanel } from './components/ChatPanel';
import { Layout } from './components/Layout';
import { StatusBar } from './components/StatusBar';
import { StepTimeline } from './components/StepTimeline';
import { useSendMessage } from './hooks/useSendMessage';
import { useSessionControls } from './hooks/useSessionControls';
import { useSessionSnapshot } from './hooks/useSessionSnapshot';
import { useSessionSteps } from './hooks/useSessionSteps';
import type { SessionSnapshot } from './types/api';
import './styles/app.css';

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [seedSnapshot, setSeedSnapshot] = useState<SessionSnapshot | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const { snapshot, error: snapshotError, refreshSnapshot } = useSessionSnapshot(sessionId);
  const displaySnapshot = snapshot ?? seedSnapshot;
  const {
    steps,
    error: stepsError,
    refreshSteps,
    resetSteps,
  } = useSessionSteps(sessionId, displaySnapshot?.status ?? null);
  const {
    sendMessage,
    error: sendMessageError,
    isSending,
  } = useSendMessage(sessionId);
  const {
    startSession,
    stopSession,
    error: controlsError,
    isStarting,
    isStopping,
  } = useSessionControls(sessionId);

  const error = useMemo(
    () => sessionError ?? controlsError ?? sendMessageError ?? stepsError ?? snapshotError,
    [controlsError, sendMessageError, sessionError, snapshotError, stepsError],
  );

  const createSession = useCallback(async () => {
    try {
      const response = await apiClient.createSession();
      setSessionId(response.session_id);
      setSeedSnapshot(response.snapshot);
      resetSteps();
      setSessionError(null);
    } catch (err) {
      setSessionError(err instanceof Error ? err.message : 'Failed to create session');
    }
  }, [resetSteps]);

  const handleStartSession = useCallback(
    async (query: string) => {
      try {
        await startSession(query);
        await refreshSnapshot();
        await refreshSteps();
        setSessionError(null);
      } catch (err) {
        setSessionError(err instanceof Error ? err.message : 'Failed to start session');
      }
    },
    [refreshSnapshot, refreshSteps, startSession],
  );

  const handleSendMessage = useCallback(
    async (text: string) => {
      try {
        await sendMessage(text);
        await refreshSnapshot();
        await refreshSteps();
        setSessionError(null);
      } catch (err) {
        setSessionError(err instanceof Error ? err.message : 'Failed to send message');
      }
    },
    [refreshSnapshot, refreshSteps, sendMessage],
  );

  const handleStopSession = useCallback(async () => {
    try {
      await stopSession();
      await refreshSnapshot();
      setSessionError(null);
    } catch (err) {
      setSessionError(err instanceof Error ? err.message : 'Failed to stop session');
    }
  }, [refreshSnapshot, stopSession]);

  return (
    <Layout
      statusBar={
        <StatusBar
          sessionId={sessionId}
          status={displaySnapshot?.status}
          currentUrl={displaySnapshot?.current_url}
          latestStepId={displaySnapshot?.latest_step_id}
          onCreateSession={createSession}
          onStopSession={handleStopSession}
        />
      }
      browserPane={
        <BrowserPane
          screenshotB64={displaySnapshot?.latest_screenshot_b64}
          status={displaySnapshot?.status}
          updatedAt={displaySnapshot?.updated_at}
        />
      }
      chatPanel={
        <ChatPanel
          messages={displaySnapshot?.messages ?? []}
          onSendMessage={handleSendMessage}
          onStartSession={handleStartSession}
          isSessionActive={
            displaySnapshot?.status === 'running' ||
            displaySnapshot?.status === 'waiting_for_input'
          }
          hasSession={!!sessionId}
          isBusy={isSending || isStarting || isStopping}
        />
      }
      sidebar={
        <div className="sidebar-content">
          {error && <div className="error-banner">{error}</div>}
          <StepTimeline steps={steps} />
          <ArtifactLinks snapshot={displaySnapshot} />
        </div>
      }
    />
  );
}

export default App;
