import type { Ref } from 'react';

import { getFinalResultSummary, getRequestText, getRunSummary, getValidVerificationItems, type PreviewMode } from '../reviewPanel';
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
}: VerificationSidebarProps) {
  if (!snapshot && steps.length === 0 && !error) {
    return <div className="sidebar-content empty-state">세션을 시작하면 검증 패널이 표시됩니다.</div>;
  }

  const resolvedRequestText = requestText ?? getRequestText(snapshot);
  const summary = runSummary ?? verificationPayload?.run_summary ?? getRunSummary(snapshot);
  const finalSummary =
    finalResultSummary ?? verificationPayload?.final_result_summary ?? getFinalResultSummary(snapshot);
  const verificationItems = getValidVerificationItems(
    verificationPayload?.verification_items ?? snapshot?.verification_items,
  );

  return (
    <div
      className="sidebar-content verification-sidebar"
      data-preview-mode={previewMode.kind}
      ref={sidebarRef}
      tabIndex={-1}
    >
      {error && <div className="error-banner">{error}</div>}
      <CompletionBanner status={snapshot?.status} verificationCount={verificationItems.length} />
      <section className="verification-section focus-controls-section">
        <h2>패널 이동</h2>
        <div className="focus-controls">
          <button type="button" className="btn-secondary preview-button" onClick={onFocusBrowserPane}>
            브라우저 영역으로 이동
          </button>
          <button type="button" className="btn-secondary preview-button" onClick={onFocusVerificationPanel}>
            검증 패널 상단으로 이동
          </button>
        </div>
      </section>
      <RequestSummaryHeader requestText={resolvedRequestText} />
      <TaskSummarySection summary={summary} />
      <ConfirmationNeededSection
        items={verificationPayload?.verification_items ?? snapshot?.verification_items}
        onSelectStepPreview={onSelectStepPreview}
        artifactsBaseUrl={verificationPayload?.artifacts_base_url ?? snapshot?.artifacts_base_url}
      />
      <ProcessHistorySection
        steps={steps}
        groupedSteps={verificationPayload?.grouped_steps}
        previewMode={previewMode}
        onSelectStepPreview={onSelectStepPreview}
        artifactsBaseUrl={verificationPayload?.artifacts_base_url ?? snapshot?.artifacts_base_url}
      />
      <FinalResultSection summary={finalSummary} onSelectCurrentPreview={onSelectCurrentPreview} />
      <section className="verification-section debug-artifacts-section">
        <h2>Debug Artifacts</h2>
        <ArtifactLinks snapshot={snapshot} />
      </section>
    </div>
  );
}
