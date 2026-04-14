import { useRef } from 'react';

import { useBrowserSurfaceHost } from './api/browserSurfaceBridge';
import { BrowserPane } from './components/BrowserPane';
import { ChatPanel } from './components/ChatPanel';
import { Layout } from './components/Layout';
import { StatusBar } from './components/StatusBar';
import { VerificationSidebar } from './components/VerificationSidebar';
import { useAppSessionRuntime } from './hooks/useAppSessionRuntime';
import { useFocusRegions } from './hooks/useFocusRegions';
import './styles/app.css';

function App() {
  const browserPaneRef = useRef<HTMLElement | null>(null);
  const browserSurfaceHostRef = useRef<HTMLDivElement | null>(null);
  const verificationPanelRef = useRef<HTMLDivElement | null>(null);
  const chatInputRef = useRef<HTMLInputElement | null>(null);
  const {
    sessionId,
    displaySnapshot,
    steps,
    verification,
    error,
    bridgeError,
    previewMode,
    selectedStep,
    requestText,
    stopRequested,
    hasSession,
    isSessionActive,
    isBusy,
    isStopping,
    isInterrupting,
    isClosing,
    setPreviewMode,
    createSession,
    handleStartSession,
    handleSendMessage,
    handleInterruptSession,
    handleCloseSession,
  } = useAppSessionRuntime();
  const {
    hasBrowserSurfaceBridge,
  } = useBrowserSurfaceHost(browserSurfaceHostRef, {
    isVisible: previewMode.kind === 'current',
  });
  const {
    focusedRegion,
  } = useFocusRegions({
    browserPaneRef,
    verificationPanelRef,
    chatInputRef,
  });

  return (
    <Layout
      statusBar={
        <StatusBar
          sessionId={sessionId}
          status={displaySnapshot?.status}
          currentUrl={displaySnapshot?.current_url}
          latestStepId={displaySnapshot?.latest_step_id}
          expiresAt={displaySnapshot?.expires_at}
          onCreateSession={createSession}
          onInterruptSession={handleInterruptSession}
          onCloseSession={handleCloseSession}
          stopPending={isStopping}
          interruptPending={stopRequested || isInterrupting}
          closePending={isClosing}
        />
      }
      browserPane={
        <BrowserPane
          paneRef={browserPaneRef}
          surfaceRef={browserSurfaceHostRef}
          currentScreenshotB64={displaySnapshot?.latest_screenshot_b64}
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
          status={displaySnapshot?.status}
          isSessionActive={isSessionActive}
          hasSession={hasSession}
          isBusy={isBusy}
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
          verificationPayload={verification}
          onSelectStepPreview={(stepId) => setPreviewMode({ kind: 'step', stepId })}
          isFocused={focusedRegion === 'verification'}
          bridgeError={bridgeError}
          stopPending={stopRequested}
        />
      }
    />
  );
}

export default App;
