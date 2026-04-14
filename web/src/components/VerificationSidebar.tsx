import type { Ref } from 'react';

import {
  filterVerificationItemsForRun,
  getRelevantRunId,
  getRequestText,
  type PreviewMode,
} from '../reviewPanel';
import type { SessionSnapshot, StepRecord, VerificationPayload } from '../types/api';
import { CompletionBanner } from './CompletionBanner';
import { CurrentStatusSection } from './CurrentStatusSection';
import { ProcessHistorySection } from './ProcessHistorySection';

interface VerificationSidebarProps {
  snapshot: SessionSnapshot | null;
  steps: StepRecord[];
  error: string | null;
  previewMode: PreviewMode;
  requestText?: string | null;
  verificationPayload?: VerificationPayload | null;
  sidebarRef?: Ref<HTMLDivElement>;
  onSelectStepPreview: (stepId: number) => void;
  isFocused?: boolean;
  bridgeError?: string | null;
  stopPending?: boolean;
}

export function VerificationSidebar({
  snapshot,
  steps,
  error,
  previewMode,
  requestText,
  verificationPayload,
  sidebarRef,
  onSelectStepPreview,
  isFocused = false,
  bridgeError = null,
  stopPending = false,
}: VerificationSidebarProps) {
  if (!snapshot && steps.length === 0 && !error) {
    return <div className="sidebar-content empty-state">세션을 시작하면 검증 패널이 표시됩니다.</div>;
  }

  const resolvedRequestText = requestText ?? getRequestText(snapshot);
  const relevantRunId = getRelevantRunId(snapshot, verificationPayload, steps);
  const verificationItems = filterVerificationItemsForRun(
    verificationPayload?.verification_items ?? snapshot?.verification_items,
    relevantRunId,
  );

  return (
    <div
      className="sidebar-content verification-sidebar"
      data-preview-mode={previewMode.kind}
      data-focus-active={isFocused ? 'true' : 'false'}
      role="region"
      aria-label="Verification pane"
      ref={sidebarRef}
      tabIndex={-1}
    >
      {error && <div className="error-banner">{error}</div>}
      {bridgeError && <div className="error-banner bridge-error-banner">Bridge error: {bridgeError}</div>}
      {stopPending && <div className="error-banner stop-pending-banner">Stopping session...</div>}
      <CompletionBanner
        status={snapshot?.status}
        verificationCount={verificationItems.length}
        waitingReason={snapshot?.waiting_reason}
        lastRunStatus={snapshot?.last_run_status}
        errorMessage={snapshot?.error_message}
      />
      <CurrentStatusSection
        requestText={resolvedRequestText}
        status={snapshot?.status}
      />
      <ProcessHistorySection
        steps={steps}
        groupedSteps={verificationPayload?.grouped_steps}
        previewMode={previewMode}
        onSelectStepPreview={onSelectStepPreview}
        sessionId={verificationPayload?.session_id ?? snapshot?.session_id}
      />
    </div>
  );
}
