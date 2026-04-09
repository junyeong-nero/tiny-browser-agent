import { useCallback, useMemo, useRef, useState } from 'react';

import { apiClient } from './api/client';
import { BrowserPane } from './components/BrowserPane';
import { ChatPanel } from './components/ChatPanel';
import { Layout } from './components/Layout';
import { StatusBar } from './components/StatusBar';
import { VerificationSidebar } from './components/VerificationSidebar';
import { useSendMessage } from './hooks/useSendMessage';
import { useSessionControls } from './hooks/useSessionControls';
import { useSessionSnapshot } from './hooks/useSessionSnapshot';
import { useSessionSteps } from './hooks/useSessionSteps';
import { useSessionVerification } from './hooks/useSessionVerification';
import {
  getFinalResultSummary,
  getRequestText,
  getRunSummary,
  type PreviewMode,
} from './reviewPanel';
import type { SessionSnapshot } from './types/api';
import './styles/app.css';

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [seedSnapshot, setSeedSnapshot] = useState<SessionSnapshot | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState<PreviewMode>({ kind: 'current' });
  const browserPaneRef = useRef<HTMLDivElement | null>(null);
  const verificationPanelRef = useRef<HTMLDivElement | null>(null);

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
  const {
    verification,
    error: verificationError,
    refreshVerification,
  } = useSessionVerification(sessionId, displaySnapshot?.status ?? null);

  const error = useMemo(
    () => sessionError ?? controlsError ?? sendMessageError ?? stepsError ?? snapshotError ?? verificationError,
    [controlsError, sendMessageError, sessionError, snapshotError, stepsError, verificationError],
  );
  const selectedStep = useMemo(
    () =>
      previewMode.kind === 'step'
        ? steps.find((step) => step.step_id === previewMode.stepId) ?? null
        : null,
    [previewMode, steps],
  );
  const requestText = useMemo(() => getRequestText(displaySnapshot), [displaySnapshot]);
  const runSummary = useMemo(() => getRunSummary(displaySnapshot), [displaySnapshot]);
  const finalResultSummary = useMemo(
    () => getFinalResultSummary(displaySnapshot),
    [displaySnapshot],
  );

  const createSession = useCallback(async () => {
    try {
      const response = await apiClient.createSession();
      setSessionId(response.session_id);
      setSeedSnapshot(response.snapshot);
      setPreviewMode({ kind: 'current' });
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
        await refreshVerification();
        setPreviewMode({ kind: 'current' });
        setSessionError(null);
      } catch (err) {
        setSessionError(err instanceof Error ? err.message : 'Failed to start session');
      }
    },
    [refreshSnapshot, refreshSteps, refreshVerification, startSession],
  );

  const handleSendMessage = useCallback(
    async (text: string) => {
      try {
        await sendMessage(text);
        await refreshSnapshot();
        await refreshSteps();
        await refreshVerification();
        setPreviewMode({ kind: 'current' });
        setSessionError(null);
      } catch (err) {
        setSessionError(err instanceof Error ? err.message : 'Failed to send message');
      }
    },
    [refreshSnapshot, refreshSteps, refreshVerification, sendMessage],
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
          paneRef={browserPaneRef}
          currentScreenshotB64={displaySnapshot?.latest_screenshot_b64}
          currentUpdatedAt={displaySnapshot?.updated_at}
          selectedStep={selectedStep}
          artifactsBaseUrl={displaySnapshot?.artifacts_base_url}
          status={displaySnapshot?.status}
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
        <VerificationSidebar
          sidebarRef={verificationPanelRef}
          snapshot={displaySnapshot}
          steps={steps}
          error={error}
          previewMode={previewMode}
          requestText={requestText}
          runSummary={runSummary}
          finalResultSummary={finalResultSummary}
          verificationPayload={verification}
          onSelectCurrentPreview={() => setPreviewMode({ kind: 'current' })}
          onSelectStepPreview={(stepId) => setPreviewMode({ kind: 'step', stepId })}
          onFocusBrowserPane={() => browserPaneRef.current?.focus()}
          onFocusVerificationPanel={() => verificationPanelRef.current?.focus()}
        />
      }
    />
  );
}

export default App;
