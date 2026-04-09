import { buildArtifactUrl, getProcessGroups, type PreviewMode } from '../reviewPanel';
import type { StepRecord, VerificationGroup } from '../types/api';
import { AccessibilityTreeView } from './AccessibilityTreeView';

interface ProcessHistorySectionProps {
  steps: StepRecord[];
  groupedSteps?: VerificationGroup[] | null;
  previewMode: PreviewMode;
  onSelectStepPreview: (stepId: number) => void;
  artifactsBaseUrl: string | null | undefined;
}

export function ProcessHistorySection({
  steps,
  groupedSteps,
  previewMode,
  onSelectStepPreview,
  artifactsBaseUrl,
}: ProcessHistorySectionProps) {
  const groups = getProcessGroups(groupedSteps, steps);

  return (
    <section className="verification-section process-history-section">
      <h2>과정 기록</h2>
      {groups.length === 0 ? (
        <div className="empty-state">아직 기록된 단계가 없습니다.</div>
      ) : (
        <div className="process-history-groups">
          {groups.map((group) => (
            <details key={group.id} className="process-group" open>
              <summary>
                <span>{group.label}</span>
                {group.summary && <span className="process-group-summary">{group.summary}</span>}
              </summary>
              <div className="steps-list">
                {group.steps.map((step) => {
                  const stepHtmlUrl = buildArtifactUrl(artifactsBaseUrl, step.html_path);
                  const stepMetadataUrl = buildArtifactUrl(artifactsBaseUrl, step.metadata_path);
                  const isSelected =
                    previewMode.kind === 'step' && previewMode.stepId === step.step_id;

                  return (
                    <article
                      key={step.step_id}
                      className={`step-item status-${step.status} ${isSelected ? 'selected' : ''}`}
                    >
                      <div className="step-header">
                        <span className="step-id">
                          {step.user_visible_label ?? `Step ${step.step_id}`}
                        </span>
                        <span className="step-status">{step.status}</span>
                      </div>
                      {step.reasoning && <div className="step-reasoning">{step.reasoning}</div>}
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
                        {stepHtmlUrl && (
                          <a href={stepHtmlUrl} target="_blank" rel="noreferrer">
                            HTML
                          </a>
                        )}
                        {stepMetadataUrl && (
                          <a href={stepMetadataUrl} target="_blank" rel="noreferrer">
                            Metadata
                          </a>
                        )}
                        <AccessibilityTreeView
                          artifactUrl={buildArtifactUrl(artifactsBaseUrl, step.a11y_path)}
                          label={`Step ${step.step_id}`}
                        />
                      </div>
                    </article>
                  );
                })}
              </div>
            </details>
          ))}
        </div>
      )}
    </section>
  );
}
