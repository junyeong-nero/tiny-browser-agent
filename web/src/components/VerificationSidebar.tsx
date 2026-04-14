import type { Ref } from 'react';

import {
  filterVerificationItemsForRun,
  getFinalResultSummary,
  getRelevantRunId,
  getRequestText,
  getRunSummary,
  type PreviewMode,
} from '../reviewPanel';
import type { SessionSnapshot, StepRecord, VerificationPayload } from '../types/api';
import { ArtifactLinks } from './ArtifactLinks';
import { CompletionBanner } from './CompletionBanner';
import { ConfirmationNeededSection } from './ConfirmationNeededSection';
import { FinalResultSection } from './FinalResultSection';
import { ProcessHistorySection } from './ProcessHistorySection';
import { RequestSummaryHeader } from './RequestSummaryHeader';
import { TaskSummarySection } from './TaskSummarySection';

interface VerificationSidebarProps {
  snapshot: SessionSnapshot | null;
  steps: StepRecord[];
  error: string | null;
  previewMode: PreviewMode;
  requestText?: string | null;
  runSummary?: string | null;
  finalResultSummary?: string | null;
  verificationPayload?: VerificationPayload | null;
  sidebarRef?: Ref<HTMLDivElement>;
  onSelectCurrentPreview: () => void;
  onSelectStepPreview: (stepId: number) => void;
  onFocusBrowserPane: () => void;
  onFocusVerificationPanel: () => void;
  onFocusChatInput: () => void;
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
  runSummary,
  finalResultSummary,
  verificationPayload,
  sidebarRef,
  onSelectCurrentPreview,
  onSelectStepPreview,
  onFocusBrowserPane,
  onFocusVerificationPanel,
  onFocusChatInput,
  isFocused = false,
  bridgeError = null,
  stopPending = false,
}: VerificationSidebarProps) {
  if (!snapshot && steps.length === 0 && !error) {
    return <div className="sidebar-content empty-state">세션을 시작하면 검증 패널이 표시됩니다.</div>;
  }

  const resolvedRequestText = requestText ?? getRequestText(snapshot);
  const summary = runSummary ?? verificationPayload?.run_summary ?? getRunSummary(snapshot);
  const finalSummary =
    finalResultSummary ?? verificationPayload?.final_result_summary ?? getFinalResultSummary(snapshot);
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
      <section className="verification-section focus-controls-section">
        <h2>패널 이동</h2>
        <div className="focus-controls">
          <button type="button" className="btn-secondary preview-button" onClick={onFocusBrowserPane}>
            브라우저 영역으로 이동
          </button>
          <button type="button" className="btn-secondary preview-button" onClick={onFocusVerificationPanel}>
            검증 패널 상단으로 이동
          </button>
          <button type="button" className="btn-secondary preview-button" onClick={onFocusChatInput}>
            채팅 입력으로 이동
          </button>
        </div>
      </section>
      <RequestSummaryHeader requestText={resolvedRequestText} />
      <TaskSummarySection summary={summary} />
      <ConfirmationNeededSection
        items={verificationItems}
        onSelectStepPreview={onSelectStepPreview}
        sessionId={verificationPayload?.session_id ?? snapshot?.session_id}
      />
      <ProcessHistorySection
        steps={steps}
        groupedSteps={verificationPayload?.grouped_steps}
        previewMode={previewMode}
        onSelectStepPreview={onSelectStepPreview}
        sessionId={verificationPayload?.session_id ?? snapshot?.session_id}
      />
      <FinalResultSection summary={finalSummary} onSelectCurrentPreview={onSelectCurrentPreview} />
      <section className="verification-section debug-artifacts-section">
        <h2>Debug Artifacts</h2>
        <ArtifactLinks snapshot={snapshot} />
      </section>
    </div>
  );
}
