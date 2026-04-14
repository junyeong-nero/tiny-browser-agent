import { useId, useState } from 'react';

import { useArtifactClient } from '../api/ArtifactClientContext';
import {
  getProcessGroups,
  groupProcessGroupsByRun,
  type PreviewMode,
  type StepGroup,
} from '../reviewPanel';
import type { StepRecord, VerificationGroup } from '../types/api';
import { AccessibilityTreeView } from './AccessibilityTreeView';
import { CollapsibleSection } from './CollapsibleSection';

interface ProcessHistorySectionProps {
  steps: StepRecord[];
  groupedSteps?: VerificationGroup[] | null;
  previewMode: PreviewMode;
  onSelectStepPreview: (stepId: number) => void;
  sessionId: string | null | undefined;
}

interface StepCardProps {
  step: StepRecord;
  previewMode: PreviewMode;
  onSelectStepPreview: (stepId: number) => void;
  sessionId: string | null | undefined;
  compact?: boolean;
}

function getStepTitle(step: StepRecord): string {
  return step.action_summary ?? step.user_visible_label ?? `Step ${step.step_id}`;
}

function getStepReason(step: StepRecord): string | null {
  if (!step.reason) {
    return null;
  }
  const normalizedReason = step.reason.trim();
  if (!normalizedReason) {
    return null;
  }
  const lowerReason = normalizedReason.toLowerCase();
  const looksLikeVerboseMetaReason =
    normalizedReason.length > 180
    || normalizedReason.includes('`')
    || /\b(i|i'm|i’ve|i'll|i’d)\b/i.test(normalizedReason)
    || lowerReason.includes('press_enter')
    || lowerReason.includes('the page now')
    || lowerReason.includes('as intended')
    || lowerReason.includes('i will now')
    || lowerReason.includes('i have evaluated');

  if (looksLikeVerboseMetaReason) {
    return null;
  }

  return normalizedReason;
}

function getRawReasoning(step: StepRecord): string | null {
  if (!step.reasoning || !step.reason || step.reason === step.reasoning) {
    return null;
  }
  return step.reasoning;
}

function getSummarySourceLabel(step: StepRecord): string | null {
  if (step.summary_source === 'openrouter') {
    return 'OpenRouter 요약';
  }
  if (step.summary_source) {
    return '기본 요약';
  }
  return null;
}

function hasHiddenDetails(step: StepRecord): boolean {
  return Boolean(
    getRawReasoning(step)
      || step.function_calls.length > 0
      || step.review_evidence?.length
      || step.html_path
      || step.metadata_path
      || step.a11y_path
      || step.url
      || getSummarySourceLabel(step),
  );
}

function trimLatestStepFromGroups(groups: StepGroup[]): StepGroup[] {
  if (groups.length === 0) {
    return [];
  }

  return groups
    .map((group, index) => {
      const nextSteps =
        index === groups.length - 1 ? group.steps.slice(0, -1) : [...group.steps];
      return {
        ...group,
        steps: nextSteps,
      };
    })
    .filter((group) => group.steps.length > 0);
}

function shouldShowGroupHeader(group: StepGroup, groupCount: number): boolean {
  return group.label !== '전체 과정 보기' || Boolean(group.summary) || groupCount > 1;
}

function StepCard({
  step,
  previewMode,
  onSelectStepPreview,
  sessionId,
  compact = false,
}: StepCardProps) {
  const artifactClient = useArtifactClient();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const detailsId = useId();
  const isSelected = previewMode.kind === 'step' && previewMode.stepId === step.step_id;
  const displayedSummary = getStepTitle(step);
  const displayedReason = getStepReason(step);
  const rawReasoning = getRawReasoning(step);
  const summarySourceLabel = getSummarySourceLabel(step);
  const stepHtmlPath = step.html_path;
  const stepMetadataPath = step.metadata_path;
  const cardClassName = [
    'step-item',
    compact ? 'compact-step-item' : 'latest-step-item',
    `status-${step.status}`,
    isSelected ? 'selected' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <article key={step.step_id} className={cardClassName}>
      <div className="step-header">
        <div className="step-header-main">
          <span className="step-id">{compact ? displayedSummary : `Step ${step.step_id}`}</span>
        </div>
        <span className="step-status">{step.status}</span>
      </div>
      {!compact && (
        <div className="step-summary-block">
          <div className="step-summary-label">행동 요약</div>
          <div className="step-reasoning">{displayedSummary}</div>
        </div>
      )}
      {(compact ? displayedReason : true) && (
        <div className="step-summary-block">
          <div className="step-summary-label">이유</div>
          <div className="step-reasoning">
            {displayedReason ?? '이유 정보가 아직 없습니다.'}
          </div>
        </div>
      )}
      {step.ambiguity_message && (
        <div className="step-ambiguity">{step.ambiguity_message}</div>
      )}
      {step.error_message && <div className="step-error">{step.error_message}</div>}
      <div className="step-footer">
        {step.screenshot_path && (
          <button
            type="button"
            className="btn-secondary preview-button"
            onClick={() => onSelectStepPreview(step.step_id)}
          >
            이 시점 보기
          </button>
        )}
      </div>
      {hasHiddenDetails(step) && (
        <div className="step-disclosure">
          <button
            type="button"
            className="step-disclosure-toggle"
            aria-expanded={detailsOpen}
            aria-controls={detailsId}
            onClick={() => setDetailsOpen((open) => !open)}
          >
            {detailsOpen ? '세부 정보 숨기기' : '세부 정보 보기'}
          </button>
          {detailsOpen && (
            <div id={detailsId} className="step-disclosure-body">
              {summarySourceLabel && (
                <div className="step-detail-line">요약 출처: {summarySourceLabel}</div>
              )}
              {step.url && <div className="step-detail-line">기록된 URL: {step.url}</div>}
              {rawReasoning && (
                <div className="step-summary-block">
                  <div className="step-summary-label">원문 reasoning</div>
                  <div className="step-raw-reasoning-text">{rawReasoning}</div>
                </div>
              )}
              {step.review_evidence && step.review_evidence.length > 0 && (
                <div className="step-detail-line">Evidence: {step.review_evidence.join(', ')}</div>
              )}
              {step.function_calls.length > 0 && (
                <div className="step-summary-block">
                  <div className="step-summary-label">실행된 도구</div>
                  <div className="step-actions">
                    {step.function_calls.map((call, index) => (
                      <div key={`${call.name}-${index}`} className="step-action">
                        <code>{call.name}</code>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {(stepHtmlPath || stepMetadataPath || step.a11y_path) && (
                <div className="step-footer step-detail-actions">
                  {stepHtmlPath && sessionId && (
                    <button
                      type="button"
                      className="btn-secondary preview-button"
                      onClick={() => void artifactClient.openArtifact(sessionId, stepHtmlPath)}
                    >
                      HTML
                    </button>
                  )}
                  {stepMetadataPath && sessionId && (
                    <button
                      type="button"
                      className="btn-secondary preview-button"
                      onClick={() => void artifactClient.openArtifact(sessionId, stepMetadataPath)}
                    >
                      Metadata
                    </button>
                  )}
                  <AccessibilityTreeView
                    sessionId={sessionId}
                    artifactName={step.a11y_path}
                    label={`Step ${step.step_id}`}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

export function ProcessHistorySection({
  steps,
  groupedSteps,
  previewMode,
  onSelectStepPreview,
  sessionId,
}: ProcessHistorySectionProps) {
  const groups = getProcessGroups(groupedSteps, steps);
  const allSteps = groups.flatMap((group) => group.steps);
  const latestStep = allSteps[allSteps.length - 1] ?? null;
  const historyGroups = trimLatestStepFromGroups(groups);
  const historyRunGroups = groupProcessGroupsByRun(historyGroups);
  const allRunGroups = groupProcessGroupsByRun(groups);
  const showRunLabels = allRunGroups.length > 1;

  return (
    <>
      <section className="verification-section process-history-section">
        <h2>최근 행동</h2>
        {!latestStep ? (
          <div className="empty-state">아직 기록된 단계가 없습니다.</div>
        ) : (
          <StepCard
            step={latestStep}
            previewMode={previewMode}
            onSelectStepPreview={onSelectStepPreview}
            sessionId={sessionId}
          />
        )}
      </section>
      <CollapsibleSection
        title="이전 과정 보기"
        className="process-history-archive"
      >
        {historyRunGroups.length === 0 ? (
          <div className="empty-state">이전 과정이 없습니다.</div>
        ) : (
          <div className="process-history-groups">
            {historyRunGroups.map((runGroup) => (
              <section
                key={runGroup.id}
                className="process-run-group"
                data-run-id={runGroup.runId ?? 'none'}
              >
                {showRunLabels && <h3 className="process-run-heading">{runGroup.label}</h3>}
                {runGroup.groups.map((group) => (
                  <section key={group.id} className="process-group-block">
                    {shouldShowGroupHeader(group, runGroup.groups.length) && (
                      <div className="process-group-heading">
                        <h4>{group.steps[0]?.user_visible_label ?? group.steps[0]?.action_summary ?? group.label}</h4>
                      </div>
                    )}
                    <div className="steps-list">
                      {group.steps.map((step) => (
                        <StepCard
                          key={step.step_id}
                          step={step}
                          previewMode={previewMode}
                          onSelectStepPreview={onSelectStepPreview}
                          sessionId={sessionId}
                          compact
                        />
                      ))}
                    </div>
                  </section>
                ))}
              </section>
            ))}
          </div>
        )}
      </CollapsibleSection>
    </>
  );
}
