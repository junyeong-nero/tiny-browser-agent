import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useSessionClient } from './api/SessionClientContext';
import { useBrowserSurfaceHost } from './api/browserSurfaceBridge';
import { BrowserPane } from './components/BrowserPane';
import { ChatPanel } from './components/ChatPanel';
import { Layout } from './components/Layout';
import { StatusBar } from './components/StatusBar';
import { VerificationSidebar } from './components/VerificationSidebar';
import { getFocusShortcutRegion } from './focus/focusManager';
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
  const sessionClient = useSessionClient();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [seedSnapshot, setSeedSnapshot] = useState<SessionSnapshot | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [bridgeError, setBridgeError] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState<PreviewMode>({ kind: 'current' });
  const [focusedRegion, setFocusedRegion] = useState<'browser' | 'verification' | 'chat' | null>(null);
  const [stopRequested, setStopRequested] = useState(false);
  const browserPaneRef = useRef<HTMLElement | null>(null);
  const verificationPanelRef = useRef<HTMLDivElement | null>(null);
  const chatInputRef = useRef<HTMLInputElement | null>(null);
  const { snapshot, error: snapshotError, refreshSnapshot } = useSessionSnapshot(sessionId);
  const displaySnapshot = snapshot ?? seedSnapshot;
  const isLiveBrowserSurfaceVisible = previewMode.kind === 'current';
  const {
    focusBrowserSurface,
    hasBrowserSurfaceBridge,
  } = useBrowserSurfaceHost(browserPaneRef, {
    isVisible: isLiveBrowserSurfaceVisible,
  });
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
      const response = await sessionClient.createSession();
      setSessionId(response.session_id);
      setSeedSnapshot(response.snapshot);
      setPreviewMode({ kind: 'current' });
      resetSteps();
      setSessionError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create session';
      setSessionError(message);
      setBridgeError(message);
    }
  }, [resetSteps, sessionClient]);

  const handleStartSession = useCallback(
    async (query: string) => {
      try {
        setBridgeError(null);
        await startSession(query);
        await refreshSnapshot();
        await refreshSteps();
        await refreshVerification();
        setPreviewMode({ kind: 'current' });
        setSessionError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to start session';
        setSessionError(message);
        setBridgeError(message);
      }
    },
    [refreshSnapshot, refreshSteps, refreshVerification, startSession],
  );

  const handleSendMessage = useCallback(
    async (text: string) => {
      try {
        setBridgeError(null);
        await sendMessage(text);
        await refreshSnapshot();
        await refreshSteps();
        await refreshVerification();
        setPreviewMode({ kind: 'current' });
        setSessionError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to send message';
        setSessionError(message);
        setBridgeError(message);
      }
    },
    [refreshSnapshot, refreshSteps, refreshVerification, sendMessage],
  );

  const handleStopSession = useCallback(async () => {
    try {
      setBridgeError(null);
      setStopRequested(true);
      await stopSession();
      await refreshSnapshot();
      setSessionError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to stop session';
      setSessionError(message);
      setBridgeError(message);
      setStopRequested(false);
    }
  }, [refreshSnapshot, stopSession]);

  useEffect(() => {
    if (!stopRequested) {
      return;
    }

    const status = displaySnapshot?.status;
    if (status === 'stopped' || status === 'error' || status === 'complete') {
      setStopRequested(false);
    }
  }, [displaySnapshot?.status, stopRequested]);

  const focusBrowserPane = useCallback(() => {
    setFocusedRegion('browser');
    void focusBrowserSurface();
  }, [focusBrowserSurface]);

  const focusVerificationPanel = useCallback(() => {
    setFocusedRegion('verification');
    verificationPanelRef.current?.focus();
  }, []);

  const focusChatInput = useCallback(() => {
    setFocusedRegion('chat');
    chatInputRef.current?.focus();
  }, []);

  useEffect(() => {
    const browserElement = browserPaneRef.current;
    const verificationElement = verificationPanelRef.current;
    const chatElement = chatInputRef.current;

    const handleBrowserFocus = () => setFocusedRegion('browser');
    const handleVerificationFocus = () => setFocusedRegion('verification');
    const handleChatFocus = () => setFocusedRegion('chat');

    browserElement?.addEventListener('focusin', handleBrowserFocus);
    verificationElement?.addEventListener('focusin', handleVerificationFocus);
    chatElement?.addEventListener('focus', handleChatFocus);

    return () => {
      browserElement?.removeEventListener('focusin', handleBrowserFocus);
      verificationElement?.removeEventListener('focusin', handleVerificationFocus);
      chatElement?.removeEventListener('focus', handleChatFocus);
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const region = getFocusShortcutRegion(event);
      if (!region) {
        return;
      }

      event.preventDefault();
      if (region === 'browser') {
        focusBrowserPane();
        return;
      }
      if (region === 'verification') {
        focusVerificationPanel();
        return;
      }
      focusChatInput();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [focusBrowserPane, focusChatInput, focusVerificationPanel]);

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
          stopPending={stopRequested}
        />
      }
      browserPane={
        <BrowserPane
          paneRef={browserPaneRef}
          currentScreenshotB64={displaySnapshot?.latest_screenshot_b64}
          currentUpdatedAt={displaySnapshot?.updated_at}
          selectedStep={selectedStep}
          sessionId={displaySnapshot?.session_id}
          status={displaySnapshot?.status}
          hasBrowserSurfaceBridge={hasBrowserSurfaceBridge}
          isFocused={focusedRegion === 'browser'}
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
          inputRef={chatInputRef}
          isFocused={focusedRegion === 'chat'}
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
          onFocusBrowserPane={focusBrowserPane}
          onFocusVerificationPanel={focusVerificationPanel}
          onFocusChatInput={focusChatInput}
          isFocused={focusedRegion === 'verification'}
          bridgeError={bridgeError}
          stopPending={stopRequested}
        />
      }
    />
  );
}

export default App;
