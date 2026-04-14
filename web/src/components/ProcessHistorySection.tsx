import { useArtifactClient } from '../api/ArtifactClientContext';
import { groupProcessGroupsByRun, type PreviewMode } from '../reviewPanel';
import type { StepRecord, VerificationGroup } from '../types/api';
import { AccessibilityTreeView } from './AccessibilityTreeView';

interface ProcessHistorySectionProps {
  steps: StepRecord[];
  groupedSteps?: VerificationGroup[] | null;
  previewMode: PreviewMode;
  onSelectStepPreview: (stepId: number) => void;
  sessionId: string | null | undefined;
}

export function ProcessHistorySection({
  steps,
  groupedSteps,
  previewMode,
  onSelectStepPreview,
  sessionId,
}: ProcessHistorySectionProps) {
  const artifactClient = useArtifactClient();
  const runGroups = groupProcessGroupsByRun(groupedSteps, steps);

  return (
    <section className="verification-section process-history-section">
      <h2>과정 기록</h2>
      {runGroups.length === 0 ? (
        <div className="empty-state">아직 기록된 단계가 없습니다.</div>
      ) : (
        <div className="process-history-groups">
          {runGroups.map((runGroup) => (
            <section key={runGroup.id} className="process-run-group" data-run-id={runGroup.runId ?? 'none'}>
              <h3>{runGroup.label}</h3>
              {runGroup.groups.map((group) => (
                <details key={group.id} className="process-group" open>
                  <summary>
                    <span>{group.label}</span>
                    {group.summary && <span className="process-group-summary">{group.summary}</span>}
                  </summary>
                    <div className="steps-list">
                      {group.steps.map((step) => {
                        const stepHtmlPath = step.html_path ?? null;
                        const stepMetadataPath = step.metadata_path ?? null;
                        const isSelected =
                          previewMode.kind === 'step' && previewMode.stepId === step.step_id;
                        const displayedSummary =
                          step.action_summary ?? step.user_visible_label ?? `Step ${step.step_id}`;
                        const displayedReason = step.reason ?? step.reasoning ?? null;
                        const rawReasoning =
                          step.reason && step.reasoning && step.reason !== step.reasoning
                            ? step.reasoning
                            : null;
                        const summarySourceLabel =
                          step.summary_source === 'openrouter'
                            ? 'OpenRouter 요약'
                            : step.summary_source
                              ? '기본 요약'
                              : null;

                      return (
                        <article
                          key={step.step_id}
                          className={`step-item status-${step.status} ${isSelected ? 'selected' : ''}`}
                        >
                          <div className="step-header">
                            <div className="step-header-main">
                              <span className="step-id">{displayedSummary}</span>
                              {summarySourceLabel && (
                                <span className={`step-summary-badge source-${step.summary_source ?? 'fallback'}`}>
                                  {summarySourceLabel}
                                </span>
                              )}
                            </div>
                            <span className="step-status">{step.status}</span>
                          </div>
                          {displayedReason && (
                            <div className="step-summary-block">
                              <div className="step-summary-label">이유</div>
                              <div className="step-reasoning">{displayedReason}</div>
                            </div>
                          )}
                          {rawReasoning && (
                            <details className="step-raw-reasoning">
                              <summary>원문 reasoning 보기</summary>
                              <div className="step-raw-reasoning-text">{rawReasoning}</div>
                            </details>
                          )}
                          {step.ambiguity_message && (
                            <div className="step-ambiguity">{step.ambiguity_message}</div>
                          )}
                          {step.review_evidence && step.review_evidence.length > 0 && (
                            <div className="step-evidence">Evidence: {step.review_evidence.join(', ')}</div>
                          )}
                          {step.function_calls.length > 0 && (
                            <div className="step-actions">
                              {step.function_calls.map((call, index) => (
                                <div key={`${call.name}-${index}`} className="step-action">
                                  <code>{call.name}</code>
                                </div>
                              ))}
                            </div>
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
                            {stepHtmlPath && sessionId && (
                              <button type="button" className="btn-secondary preview-button" onClick={() => void artifactClient.openArtifact(sessionId, stepHtmlPath)}>
                                HTML
                              </button>
                            )}
                            {stepMetadataPath && sessionId && (
                              <button type="button" className="btn-secondary preview-button" onClick={() => void artifactClient.openArtifact(sessionId, stepMetadataPath)}>
                                Metadata
                              </button>
                            )}
                            <AccessibilityTreeView
                              sessionId={sessionId}
                              artifactName={step.a11y_path}
                              label={`Step ${step.step_id}`}
                            />
                          </div>
                        </article>
                      );
                    })}
                  </div>
                </details>
              ))}
            </section>
          ))}
        </div>
      )}
    </section>
  );
}
