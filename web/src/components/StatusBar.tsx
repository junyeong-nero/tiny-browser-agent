import { SessionStatus } from '../types/api';

interface StatusBarProps {
  sessionId: string | null;
  status: SessionStatus | undefined;
  currentUrl: string | null | undefined;
  latestStepId: number | null | undefined;
  expiresAt?: number | null;
  onCreateSession: () => void;
  onInterruptSession: () => void;
  onCloseSession: () => void;
  stopPending?: boolean;
  interruptPending?: boolean;
  closePending?: boolean;
}

function formatExpiry(expiresAt?: number | null): string | null {
  if (!expiresAt) {
    return null;
  }
  const remainingSeconds = Math.max(0, Math.ceil(expiresAt - Date.now() / 1000));
  if (remainingSeconds === 0) {
    return 'expiring now';
  }
  if (remainingSeconds < 60) {
    return `expires in ${remainingSeconds}s`;
  }
  return `expires in ${Math.ceil(remainingSeconds / 60)}m`;
}

function getStatusLabel(
  status: SessionStatus | undefined,
  stopPending: boolean,
  interruptPending: boolean,
  closePending: boolean,
): string {
  if (closePending) {
    return 'Closing';
  }
  if (interruptPending) {
    return 'Interrupting';
  }
  if (stopPending) {
    return 'Stopping';
  }
  if (status === 'waiting_for_input') {
    return 'Ready';
  }
  return status || 'No Session';
}

export function StatusBar({
  sessionId,
  status,
  currentUrl,
  latestStepId,
  expiresAt,
  onCreateSession,
  onInterruptSession,
  onCloseSession,
  stopPending = false,
  interruptPending = false,
  closePending = false,
}: StatusBarProps) {
  const badgeStatus = closePending ? 'closing' : interruptPending ? 'interrupting' : stopPending ? 'stopping' : status || 'none';
  const statusLabel = getStatusLabel(status, stopPending, interruptPending, closePending);
  const expiryLabel = status === 'waiting_for_input' ? formatExpiry(expiresAt) : null;

  return (
    <div className="status-bar">
      <div className="status-info">
        <span className="status-badge" data-status={badgeStatus}>
          {statusLabel}
        </span>
        {sessionId && <span className="session-id">ID: {sessionId}</span>}
        {latestStepId != null && <span className="step-id">Step: {latestStepId}</span>}
        {currentUrl && <span className="current-url" title={currentUrl}>{currentUrl}</span>}
        {expiryLabel && <span className="step-id">{expiryLabel}</span>}
      </div>
      <div className="status-actions">
        {!sessionId && (
          <button type="button" onClick={onCreateSession} className="btn-primary">
            New Session
          </button>
        )}
        {sessionId && status === 'running' && !interruptPending && (
          <button type="button" onClick={onInterruptSession} className="btn-danger">
            Interrupt
          </button>
        )}
        {sessionId && status !== 'running' && !closePending && (
          <button type="button" onClick={onCloseSession} className="btn-secondary">
            Close Session
          </button>
        )}
      </div>
    </div>
  );
}
