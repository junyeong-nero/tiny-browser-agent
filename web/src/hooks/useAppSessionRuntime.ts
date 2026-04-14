import { useCallback, useEffect, useMemo, useState } from 'react';

import { useSessionClient } from '../api/SessionClientContext';
import { useSendMessage } from './useSendMessage';
import { useSessionControls } from './useSessionControls';
import { useSessionSnapshot } from './useSessionSnapshot';
import { useSessionSteps } from './useSessionSteps';
import { useSessionVerification } from './useSessionVerification';
import {
  getFinalResultSummary,
  getRequestText,
  getRunSummary,
  type PreviewMode,
} from '../reviewPanel';
import type { SessionSnapshot } from '../types/api';

function getActionErrorMessage(error: unknown, fallbackMessage: string): string {
  return error instanceof Error ? error.message : fallbackMessage;
}

export function useAppSessionRuntime() {
  const sessionClient = useSessionClient();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [seedSnapshot, setSeedSnapshot] = useState<SessionSnapshot | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [bridgeError, setBridgeError] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState<PreviewMode>({ kind: 'current' });
  const [stopRequested, setStopRequested] = useState(false);
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
    interruptSession,
    closeSession,
    error: controlsError,
    isStarting,
    isStopping,
    isInterrupting,
    isClosing,
  } = useSessionControls(sessionId);
  const {
    verification,
    error: verificationError,
    refreshVerification,
  } = useSessionVerification(sessionId, displaySnapshot?.status ?? null);

  const error = useMemo(
    () =>
      sessionError ??
      controlsError ??
      sendMessageError ??
      stepsError ??
      snapshotError ??
      verificationError,
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

  const refreshSessionResources = useCallback(async () => {
    await refreshSnapshot();
    await refreshSteps();
    await refreshVerification();
  }, [refreshSnapshot, refreshSteps, refreshVerification]);

  const resetInteractiveState = useCallback(() => {
    setPreviewMode({ kind: 'current' });
    setSessionError(null);
    setStopRequested(false);
  }, []);

  const createSession = useCallback(async () => {
    try {
      const response = await sessionClient.createSession();
      setSessionId(response.session_id);
      setSeedSnapshot(response.snapshot);
      resetSteps();
      resetInteractiveState();
    } catch (error) {
      const message = getActionErrorMessage(error, 'Failed to create session');
      setSessionError(message);
      setBridgeError(message);
    }
  }, [resetInteractiveState, resetSteps, sessionClient]);

  const handleStartSession = useCallback(
    async (query: string) => {
      try {
        setBridgeError(null);
        await startSession(query);
        await refreshSessionResources();
        resetInteractiveState();
      } catch (error) {
        const message = getActionErrorMessage(error, 'Failed to start session');
        setSessionError(message);
        setBridgeError(message);
      }
    },
    [refreshSessionResources, resetInteractiveState, startSession],
  );

  const handleSendMessage = useCallback(
    async (text: string) => {
      try {
        setBridgeError(null);
        await sendMessage(text);
        await refreshSessionResources();
        resetInteractiveState();
      } catch (error) {
        const message = getActionErrorMessage(error, 'Failed to send message');
        setSessionError(message);
        setBridgeError(message);
      }
    },
    [refreshSessionResources, resetInteractiveState, sendMessage],
  );

  const handleInterruptSession = useCallback(async () => {
    try {
      setBridgeError(null);
      setStopRequested(true);
      await interruptSession();
      await refreshSessionResources();
      setSessionError(null);
    } catch (error) {
      const message = getActionErrorMessage(error, 'Failed to interrupt session');
      setSessionError(message);
      setBridgeError(message);
      setStopRequested(false);
    }
  }, [interruptSession, refreshSessionResources]);

  const handleCloseSession = useCallback(async () => {
    if (!sessionId) {
      return;
    }
    try {
      setBridgeError(null);
      await closeSession();
      setSessionId(null);
      setSeedSnapshot(null);
      resetSteps();
      resetInteractiveState();
    } catch (error) {
      const message = getActionErrorMessage(error, 'Failed to close session');
      setSessionError(message);
      setBridgeError(message);
    }
  }, [closeSession, resetInteractiveState, resetSteps, sessionId]);

  useEffect(() => {
    if (!stopRequested) {
      return;
    }

    const status = displaySnapshot?.status;
    if (status === 'waiting_for_input' || status === 'stopped' || status === 'error' || status === 'complete') {
      setStopRequested(false);
    }
  }, [displaySnapshot?.status, stopRequested]);

  return {
    sessionId,
    displaySnapshot,
    steps,
    verification,
    error,
    bridgeError,
    previewMode,
    selectedStep,
    requestText,
    runSummary,
    finalResultSummary,
    stopRequested,
    hasSession: !!sessionId,
    isSessionActive:
      displaySnapshot?.status === 'running' || displaySnapshot?.status === 'waiting_for_input',
    isBusy: isSending || isStarting || isStopping || isInterrupting || isClosing,
    isStopping,
    isInterrupting,
    isClosing,
    setPreviewMode,
    createSession,
    handleStartSession,
    handleSendMessage,
    handleInterruptSession,
    handleCloseSession,
  };
}
