import { getFinalResultSummary, getRequestText, getRunSummary, getValidVerificationItems, type PreviewMode } from '../reviewPanel';
import type { SessionSnapshot, StepRecord } from '../types/api';
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
  onSelectCurrentPreview: () => void;
  onSelectStepPreview: (stepId: number) => void;
}

export function VerificationSidebar({
  snapshot,
  steps,
  error,
  previewMode,
  requestText,
  runSummary,
  finalResultSummary,
  onSelectCurrentPreview,
  onSelectStepPreview,
}: VerificationSidebarProps) {
  if (!snapshot && steps.length === 0 && !error) {
    return <div className="sidebar-content empty-state">세션을 시작하면 검증 패널이 표시됩니다.</div>;
  }

  const resolvedRequestText = requestText ?? getRequestText(snapshot);
  const summary = runSummary ?? getRunSummary(snapshot);
  const finalSummary = finalResultSummary ?? getFinalResultSummary(snapshot);
  const verificationItems = getValidVerificationItems(snapshot?.verification_items);

  return (
    <div className="sidebar-content verification-sidebar" data-preview-mode={previewMode.kind}>
      {error && <div className="error-banner">{error}</div>}
      <CompletionBanner status={snapshot?.status} verificationCount={verificationItems.length} />
      <RequestSummaryHeader requestText={resolvedRequestText} />
      <TaskSummarySection summary={summary} />
      <ConfirmationNeededSection
        items={snapshot?.verification_items}
        onSelectStepPreview={onSelectStepPreview}
      />
      <ProcessHistorySection
        steps={steps}
        previewMode={previewMode}
        onSelectStepPreview={onSelectStepPreview}
        artifactsBaseUrl={snapshot?.artifacts_base_url}
      />
      <FinalResultSection summary={finalSummary} onSelectCurrentPreview={onSelectCurrentPreview} />
      <section className="verification-section debug-artifacts-section">
        <h2>Debug Artifacts</h2>
        <ArtifactLinks snapshot={snapshot} />
      </section>
    </div>
  );
}
