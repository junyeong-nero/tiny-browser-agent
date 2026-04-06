import { SessionStatus } from '../types/api';

interface StatusBarProps {
  sessionId: string | null;
  status: SessionStatus | undefined;
  currentUrl: string | null | undefined;
  latestStepId: number | null | undefined;
  onCreateSession: () => void;
  onStopSession: () => void;
}

export function StatusBar({
  sessionId,
  status,
  currentUrl,
  latestStepId,
  onCreateSession,
  onStopSession,
}: StatusBarProps) {
  return (
    <div className="status-bar">
      <div className="status-info">
        <span className="status-badge" data-status={status || 'none'}>
          {status || 'No Session'}
        </span>
        {sessionId && <span className="session-id">ID: {sessionId}</span>}
        {latestStepId != null && <span className="step-id">Step: {latestStepId}</span>}
        {currentUrl && <span className="current-url" title={currentUrl}>{currentUrl}</span>}
      </div>
      <div className="status-actions">
        {!sessionId && (
          <button type="button" onClick={onCreateSession} className="btn-primary">
            New Session
          </button>
        )}
        {sessionId && status === 'running' && (
          <button type="button" onClick={onStopSession} className="btn-danger">
            Stop
          </button>
        )}
      </div>
    </div>
  );
}
